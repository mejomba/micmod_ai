"""Controlled policy versioning. No operational workflow changes are made here.

The caller of publish_policy must supply the full registry-aware validator.
Published versions are protected by the PostgreSQL migration; portal views use this service.
"""
from copy import deepcopy
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import (
    WorkflowSchedulePolicy, WorkflowCalendar, WorkflowCalendarException,
    WorkflowStageTiming, WorkflowTimingRule, WorkflowScheduleTransition,
)


def _require(user, permission):
    if not user.is_authenticated or not user.is_active or not user.has_perm('workflow.' + permission):
        raise PermissionDenied


def _locked_family(policy_id):
    """Lock all existing versions in deterministic order.

    The unique version constraint is a second line of defense if an entirely
    new version is inserted concurrently. Callers must not bypass this service.
    """
    source = WorkflowSchedulePolicy.objects.get(pk=policy_id)
    family = list(WorkflowSchedulePolicy.objects.select_for_update().filter(
        workflow_key=source.workflow_key, code=source.code
    ).order_by('pk'))
    source = next((p for p in family if p.pk == policy_id), None)
    if source is None:
        raise ValidationError('Policy no longer belongs to this family.')
    return source, family


@transaction.atomic
def clone_policy(policy_id, *, user):
    """Create an independent draft with a new version and remapped calendars."""
    _require(user, 'add_workflowschedulepolicy')
    source, family = _locked_family(policy_id)
    draft = WorkflowSchedulePolicy.objects.create(
        name=source.name, code=source.code, workflow_key=source.workflow_key,
        version=max(p.version for p in family) + 1, created_by=user,
        description=source.description, unknown_policies=deepcopy(source.unknown_policies),
        route_mode=source.route_mode,
    )
    calendars = {}
    for old in source.calendars.prefetch_related('exceptions').order_by('pk'):
        new = WorkflowCalendar.objects.create(
            policy=draft, name=old.name, code=old.code, timezone=old.timezone,
            working_weekdays=deepcopy(old.working_weekdays), is_active=old.is_active,
        )
        calendars[old.pk] = new
        WorkflowCalendarException.objects.bulk_create([
            WorkflowCalendarException(calendar=new, date=exception.date,
                is_working_day=exception.is_working_day, description=exception.description)
            for exception in old.exceptions.all()
        ])
    for old in source.stage_timings.prefetch_related('rules').order_by('pk'):
        if old.calendar_id not in calendars:
            raise ValidationError('Source stage refers to a different policy calendar.')
        new = WorkflowStageTiming.objects.create(
            policy=draft, workflow_key=old.workflow_key, stage_key=old.stage_key,
            default_duration=old.default_duration, duration_unit=old.duration_unit,
            calendar=calendars[old.calendar_id], remaining_time_strategy=old.remaining_time_strategy,
            overdue_duration=old.overdue_duration, is_active=old.is_active,
        )
        WorkflowTimingRule.objects.bulk_create([
            WorkflowTimingRule(stage_timing=new, name=rule.name, description=rule.description,
                condition_json=deepcopy(rule.condition_json), effect_json=deepcopy(rule.effect_json),
                priority=rule.priority, is_active=rule.is_active)
            for rule in old.rules.all()
        ])
    WorkflowScheduleTransition.objects.bulk_create([
        WorkflowScheduleTransition(
            policy=draft, source_workflow=edge.source_workflow, source_stage=edge.source_stage,
            target_workflow=edge.target_workflow, target_stage=edge.target_stage,
            condition_json=deepcopy(edge.condition_json), priority=edge.priority,
            is_active=edge.is_active,
        )
        for edge in source.transitions.all()
    ])
    return draft


@transaction.atomic
def publish_policy(policy_id, *, user, validate, effective_from=None):
    """Publish a draft after validation; keep all prior version rows intact.

    validate(policy) must raise ValidationError on invalid registry fields,
    ambiguous rules, invalid routes or missing timings. It is mandatory until
    the registry-aware publication service is integrated. Future-effective
    policies do not deactivate the current version.
    """
    _require(user, 'publish_schedule_policy')
    policy, family = _locked_family(policy_id)
    if policy.status != WorkflowSchedulePolicy.Status.DRAFT:
        raise ValidationError('Only draft policies may be published.')
    if any(p.version > policy.version and p.status != WorkflowSchedulePolicy.Status.DRAFT
           for p in family):
        raise ValidationError('A newer version has already been published.')
    if not callable(validate):
        raise ValidationError('A full policy validator is required.')
    if not policy.stage_timings.filter(is_active=True).exists():
        raise ValidationError('At least one active stage timing is required.')
    for calendar in policy.calendars.all():
        calendar.full_clean()
        for exception in calendar.exceptions.all():
            exception.full_clean()
    for timing in policy.stage_timings.select_related('calendar').all():
        timing.full_clean()
        if timing.is_active and not timing.calendar.is_active:
            raise ValidationError('An active stage must use an active calendar.')
        for rule in timing.rules.all():
            rule.full_clean()
    for transition in policy.transitions.all():
        transition.full_clean()
    validate(policy)
    now = timezone.now()
    effective = effective_from if effective_from is not None else now
    if timezone.is_naive(effective):
        raise ValidationError('Effective time must be timezone-aware.')
    policy.status = WorkflowSchedulePolicy.Status.PUBLISHED
    policy.is_active = True
    policy.published_at = now
    policy.published_by = user
    policy.effective_from = effective
    policy.full_clean()
    policy.save(update_fields=['status', 'is_active', 'published_at', 'published_by', 'effective_from'])
    return policy


def select_policy(workflow_key, code, *, as_of=None):
    """Use latest eligible active version within the explicitly chosen family."""
    as_of = as_of if as_of is not None else timezone.now()
    if timezone.is_naive(as_of):
        raise ValidationError('Selection time must be timezone-aware.')
    return WorkflowSchedulePolicy.objects.filter(
        workflow_key=workflow_key, code=code, status=WorkflowSchedulePolicy.Status.PUBLISHED,
        is_active=True,
    ).filter(Q(effective_from__lte=as_of) | Q(effective_from__isnull=True)).order_by('-version').first()
