"""Persist the approved initial configuration without overwriting edits."""
from django.conf import settings
from django.db import transaction
from workflow.scheduling.models import (WorkflowSchedulePolicy, WorkflowCalendar, WorkflowStageTiming,
    WorkflowTimingRule, WorkflowScheduleTransition)
from workflow.scheduling.scheduler import compile_policy, publish_configured_policy
from workflow.scheduling.registry import registry
from .scheduling_rules import initial_policy, POLICY_CODE


@transaction.atomic
def seed_policy(workflow_key, *, user=None, publish=False):
    if workflow_key not in ('order', 'packing'):
        raise ValueError('Unsupported initial policy')
    existing = WorkflowSchedulePolicy.objects.filter(workflow_key=workflow_key, code=POLICY_CODE).order_by('version').first()
    if existing is not None:
        # Never publish or mutate an existing draft automatically.
        return existing, False
    config = initial_policy(workflow_key, settings.TIME_ZONE)
    policy = WorkflowSchedulePolicy.objects.create(
        workflow_key=workflow_key, code=POLICY_CODE, name='Central warehouse arrival',
        version=1, created_by=user, unknown_policies=config.unknown, route_mode=config.route_mode)
    calendars = {}
    for code, calendar in config.calendars.items():
        calendars[code] = WorkflowCalendar.objects.create(policy=policy, code=code, name=code,
            timezone=calendar.timezone, working_weekdays=sorted(calendar.weekdays))
    for key, timing in config.timings.items():
        workflow, stage = key.split('.', 1)
        saved = WorkflowStageTiming.objects.create(policy=policy, workflow_key=workflow, stage_key=stage,
            calendar=calendars[timing.base.calendar], default_duration=timing.base.duration,
            remaining_time_strategy=timing.strategy, overdue_duration=timing.overdue)
        for rule in timing.rules:
            WorkflowTimingRule.objects.create(stage_timing=saved, name=rule.key, condition_json=rule.condition,
                effect_json=rule.effect, priority=rule.priority, is_active=rule.active)
    for edge in config.edges:
        sw, ss = edge.source.split('.', 1)
        tw, ts = edge.target.split('.', 1)
        WorkflowScheduleTransition.objects.create(policy=policy, source_workflow=sw, source_stage=ss,
            target_workflow=tw, target_stage=ts, condition_json=edge.condition, priority=edge.priority, is_active=edge.active)
    compile_policy(policy, registry.by_key(workflow_key))
    if publish:
        policy = publish_configured_policy(policy.pk, user=user)
    return policy, True
