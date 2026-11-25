"""Read configured Django policies and expose a side-effect-free forecast API."""
from django.core.exceptions import ValidationError
from django.utils import timezone
from .configuration import Policy, StageTiming, validate_policy, calculate
from .engine import Calendar, Component, Edge, Rule, SchedulingError
from .registry import registry, StageState
from .policies import select_policy, publish_policy


def stage_key(workflow, stage):
    return stage if stage.startswith(workflow + '.') else workflow + '.' + stage


def compile_policy(row, binding):
    calendars = {}
    for calendar in row.calendars.filter(is_active=True).prefetch_related('exceptions'):
        calendar.full_clean(exclude=['policy'], validate_unique=False, validate_constraints=False)
        calendars[calendar.code] = Calendar(calendar.timezone, frozenset(calendar.working_weekdays),
            {exception.date: exception.is_working_day for exception in calendar.exceptions.all()})
    timings = {}
    for timing in row.stage_timings.filter(is_active=True).select_related('calendar').prefetch_related('rules'):
        key = stage_key(timing.workflow_key, timing.stage_key)
        if key in timings or timing.duration_unit != 'day' or timing.calendar.policy_id != row.pk:
            raise SchedulingError('Duplicate stage, invalid unit or foreign calendar')
        rules = tuple(Rule(str(rule.pk), rule.condition_json, rule.effect_json, rule.priority, rule.is_active)
                      for rule in timing.rules.all())
        timings[key] = StageTiming(Component(timing.default_duration, timing.calendar.code),
                                   rules, timing.remaining_time_strategy, timing.overdue_duration)
    edges = tuple(Edge(stage_key(e.source_workflow, e.source_stage),
                       stage_key(e.target_workflow, e.target_stage),
                       e.condition_json, e.priority, e.is_active) for e in row.transitions.all())
    return validate_policy(Policy(row.workflow_key, calendars, timings, edges,
                                  row.unknown_policies, row.route_mode), binding)


def publish_configured_policy(policy_id, *, user, effective_from=None, context_registry=registry):
    def validate(row):
        try:
            compile_policy(row, context_registry.by_key(row.workflow_key))
        except (SchedulingError, TypeError, KeyError) as exc:
            raise ValidationError(str(exc)) from exc
    return publish_policy(policy_id, user=user, validate=validate, effective_from=effective_from)


class Scheduler:
    def __init__(self, context_registry=registry):
        self.registry = context_registry

    def _calculate(self, instance, policy, target, target_event, as_of):
        binding = self.registry.for_instance(instance)
        compiled = compile_policy(policy, binding)
        state = binding.adapter(instance)
        if not isinstance(state, StageState):
            raise SchedulingError('Adapter must return StageState')
        return calculate(compiled, binding, state, binding.context(instance), target, target_event, as_of)

    def forecast(self, instance, *, policy_code, target, target_event='exit', as_of=None):
        as_of = as_of if as_of is not None else timezone.now()
        binding = self.registry.for_instance(instance)
        policy = select_policy(binding.workflow_key, policy_code, as_of=as_of)
        if policy is None:
            raise SchedulingError('No eligible published policy')
        return self._calculate(instance, policy, target, target_event, as_of)

    def preview(self, instance, *, policy, target, target_event='exit', as_of=None):
        # Authorization for document and policy access belongs to the calling view.
        return self._calculate(instance, policy, target, target_event,
                               as_of if as_of is not None else timezone.now())


scheduler = Scheduler()
