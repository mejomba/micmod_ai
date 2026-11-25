"""Persistence models for the generic workflow scheduler.

Policy and calendar versions are separate rows. Publication and forecast writes
must go through scheduling services; direct bulk edits are not an API.
"""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class WorkflowSchedulePolicy(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=100)
    workflow_key = models.CharField(max_length=100)
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=10, choices=[('draft', 'draft'), ('published', 'published'), ('archived', 'archived')], default='draft')
    is_active = models.BooleanField(default=False)
    effective_from = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name='created_schedule_policies', null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name='published_schedule_policies', null=True, blank=True)
    description = models.TextField(blank=True)
    unknown_policies = models.JSONField(default=dict, blank=True)
    route_mode = models.CharField(max_length=12, choices=[('alternatives', 'alternatives'), ('parallel', 'parallel')], default='alternatives')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["workflow_key","code","version"], name='wf_sched_policy_version'),
            models.CheckConstraint(check=models.Q(version__gt=0), name='wf_sched_policy_version_gt0'),
            models.CheckConstraint(check=models.Q(is_active=False) | models.Q(status='published'), name='wf_sched_active_published'),
            models.CheckConstraint(check=models.Q(status='draft') | models.Q(published_at__isnull=False), name='wf_sched_published_at'),
        ]
        indexes = [
            models.Index(fields=["workflow_key","status","is_active","effective_from"], name='wf_sched_policy_lookup'),
        ]
        permissions = [('publish_schedule_policy', 'Can publish workflow schedule policies')]

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'
        ARCHIVED = 'archived', 'Archived'

    def __str__(self):
        return f'{self.name} (v{self.version})'

    def clean(self):
        super().clean()
        if self.is_active and self.status != self.Status.PUBLISHED:
            raise ValidationError({'is_active': 'Only a published policy can be active.'})
        if self.status != self.Status.DRAFT and not self.published_at:
            raise ValidationError({'published_at': 'Publication time is required.'})
        if not isinstance(self.unknown_policies, dict):
            raise ValidationError({'unknown_policies': 'Expected an object.'})

class WorkflowCalendar(models.Model):
    policy = models.ForeignKey('workflow.workflowschedulepolicy', on_delete=models.PROTECT, related_name='calendars')
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=100)
    timezone = models.CharField(max_length=64, default='Asia/Tehran')
    working_weekdays = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["policy","code"], name='wf_sched_cal_code'),
        ]

    def __str__(self):
        return f'{self.name} ({self.code})'

    def clean(self):
        super().clean()
        try:
            ZoneInfo(self.timezone)
        except (ValueError, TypeError, ZoneInfoNotFoundError):
            raise ValidationError({'timezone': 'Invalid IANA timezone.'})
        days = self.working_weekdays
        if (not isinstance(days, list) or not days or
                any(type(day) is not int or not 0 <= day <= 6 for day in days)
                or len(set(days)) != len(days)):
            raise ValidationError({'working_weekdays': 'Select unique weekdays from 0 through 6.'})

class WorkflowCalendarException(models.Model):
    calendar = models.ForeignKey('workflow.workflowcalendar', on_delete=models.PROTECT, related_name='exceptions')
    date = models.DateField()
    is_working_day = models.BooleanField(default=False)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["calendar","date"], name='wf_sched_cal_exception'),
        ]

class WorkflowStageTiming(models.Model):
    policy = models.ForeignKey('workflow.workflowschedulepolicy', on_delete=models.PROTECT, related_name='stage_timings')
    workflow_key = models.CharField(max_length=100)
    stage_key = models.CharField(max_length=100)
    default_duration = models.PositiveIntegerField(default=0)
    duration_unit = models.CharField(max_length=10, choices=[('day', 'day')], default='day')
    calendar = models.ForeignKey('workflow.workflowcalendar', on_delete=models.PROTECT, related_name='stage_timings')
    remaining_time_strategy = models.CharField(max_length=16, choices=[('elapsed', 'elapsed'), ('restart', 'restart')], default='elapsed')
    overdue_duration = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["policy","workflow_key","stage_key"], name='wf_sched_stage_unique'),
            models.CheckConstraint(check=models.Q(default_duration__lte=36600, overdue_duration__lte=36600), name='wf_sched_duration_max'),
        ]

    def clean(self):
        super().clean()
        if self.policy_id and self.calendar_id and self.calendar.policy_id != self.policy_id:
            raise ValidationError({'calendar': 'Calendar must belong to the same policy version.'})

class WorkflowTimingRule(models.Model):
    stage_timing = models.ForeignKey('workflow.workflowstagetiming', on_delete=models.CASCADE, related_name='rules')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    condition_json = models.JSONField(default=dict, blank=True)
    effect_json = models.JSONField(default=dict, blank=True)
    priority = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["stage_timing","is_active","priority"], name='wf_sched_rule_priority'),
        ]

    def clean(self):
        super().clean()
        if not isinstance(self.condition_json, dict):
            raise ValidationError({'condition_json': 'Expected an object.'})
        if not isinstance(self.effect_json, dict) or self.effect_json.get('operation') not in {
            'set_duration', 'add_duration', 'add_field_duration', 'set_calendar', 'skip_stage'
        }:
            raise ValidationError({'effect_json': 'Unknown rule operation.'})
        if self.effect_json.get('operation') in {'set_duration', 'add_duration'}:
            from .engine import days, SchedulingError
            try:
                days(self.effect_json.get('value'))
            except SchedulingError as exc:
                raise ValidationError({'effect_json': str(exc)})

class WorkflowScheduleTransition(models.Model):
    policy = models.ForeignKey('workflow.workflowschedulepolicy', on_delete=models.PROTECT, related_name='transitions')
    source_workflow = models.CharField(max_length=100)
    source_stage = models.CharField(max_length=100)
    target_workflow = models.CharField(max_length=100)
    target_stage = models.CharField(max_length=100)
    condition_json = models.JSONField(default=dict, blank=True)
    priority = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["policy","source_workflow","source_stage"], name='wf_sched_route_source'),
        ]

    def clean(self):
        super().clean()
        if not isinstance(self.condition_json, dict):
            raise ValidationError({'condition_json': 'Expected an object.'})
        if (self.source_workflow, self.source_stage) == (self.target_workflow, self.target_stage):
            raise ValidationError({'target_stage': 'A transition cannot target itself.'})

class WorkflowForecast(models.Model):
    content_type = models.ForeignKey('contenttypes.contenttype', on_delete=models.PROTECT, related_name='workflow_forecasts')
    object_id = models.PositiveBigIntegerField()
    policy = models.ForeignKey('workflow.workflowschedulepolicy', on_delete=models.PROTECT, related_name='forecasts')
    policy_version = models.PositiveIntegerField()
    revision = models.PositiveIntegerField(default=1)
    source_stage = models.CharField(max_length=200)
    target_stage = models.CharField(max_length=200)
    target_event = models.CharField(max_length=5, choices=[('entry', 'entry'), ('exit', 'exit')], default='exit')
    calculated_at = models.DateTimeField(default=timezone.now)
    as_of = models.DateTimeField()
    initial_estimated_at = models.DateTimeField(null=True, blank=True)
    initial_is_backfill = models.BooleanField(default=False)
    calculated_estimated_at = models.DateTimeField(null=True, blank=True)
    declared_at = models.DateTimeField(null=True, blank=True)
    effective_estimated_at = models.DateTimeField(null=True, blank=True)
    actual_at = models.DateTimeField(null=True, blank=True)
    forecast_source = models.CharField(max_length=12, choices=[('calculated', 'calculated'), ('declared', 'declared'), ('actual', 'actual'), ('none', 'none')], default='none')
    forecast_status = models.CharField(max_length=12, choices=[('estimated', 'estimated'), ('provisional', 'provisional'), ('incomplete', 'incomplete'), ('declared', 'declared'), ('actual', 'actual'), ('cancelled', 'cancelled')], default='incomplete')
    context_snapshot = models.JSONField(default=dict, blank=True)
    assumptions = models.JSONField(default=list, blank=True)
    policy_snapshot = models.JSONField(default=dict, blank=True)
    calculation_reason = models.CharField(max_length=100, blank=True)
    calculation_version = models.CharField(max_length=32, default='1')
    fingerprint = models.CharField(max_length=64, blank=True)
    is_current = models.BooleanField(default=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["content_type","object_id","target_stage","target_event","revision"], name='wf_sched_forecast_revision'),
            models.UniqueConstraint(fields=["content_type","object_id","target_stage","target_event"], name='wf_sched_forecast_current', condition=models.Q(is_current=True)),
            models.CheckConstraint(check=models.Q(revision__gt=0, policy_version__gt=0, object_id__gt=0), name='wf_sched_revision_gt0'),
        ]
        indexes = [
            models.Index(fields=["is_current","effective_estimated_at"], name='wf_sched_forecast_date'),
            models.Index(fields=["is_current","forecast_status"], name='wf_sched_forecast_status'),
        ]

    def clean(self):
        super().clean()
        if self.policy_id and self.policy.version != self.policy_version:
            raise ValidationError({'policy_version': 'Policy version does not match the policy.'})
        expected = self.actual_at or self.declared_at or self.calculated_estimated_at
        source = ('actual' if self.actual_at else 'declared' if self.declared_at
                  else 'calculated' if self.calculated_estimated_at else 'none')
        if self.forecast_status != 'cancelled' and (
                self.effective_estimated_at != expected or self.forecast_source != source):
            raise ValidationError({'effective_estimated_at': 'Effective date must respect source priority.'})

class WorkflowForecastStep(models.Model):
    forecast = models.ForeignKey('workflow.workflowforecast', on_delete=models.CASCADE, related_name='steps')
    sequence = models.PositiveIntegerField()
    workflow_key = models.CharField(max_length=100)
    stage_key = models.CharField(max_length=100)
    estimated_start_at = models.DateTimeField(null=True, blank=True)
    estimated_end_at = models.DateTimeField(null=True, blank=True)
    actual_start_at = models.DateTimeField(null=True, blank=True)
    actual_end_at = models.DateTimeField(null=True, blank=True)
    standard_duration = models.PositiveIntegerField(default=0)
    elapsed_duration = models.PositiveIntegerField(default=0)
    remaining_duration = models.PositiveIntegerField(default=0)
    calendar = models.ForeignKey('workflow.workflowcalendar', on_delete=models.PROTECT, related_name='forecast_steps', null=True, blank=True)
    duration_components = models.JSONField(default=list, blank=True)
    applied_rules = models.JSONField(default=list, blank=True)
    calculation_details = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=32, blank=True)
    assumptions = models.JSONField(default=list, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["forecast","sequence"], name='wf_sched_forecast_step'),
        ]
        ordering = ["sequence"]

class WorkflowForecastAnchor(models.Model):
    forecast = models.ForeignKey('workflow.workflowforecast', on_delete=models.CASCADE, related_name='anchors')
    stage_key = models.CharField(max_length=200)
    target_event = models.CharField(max_length=5, choices=[('entry', 'entry'), ('exit', 'exit')], default='exit')
    anchor_type = models.CharField(max_length=12, choices=[('actual', 'actual'), ('declared', 'declared'), ('calculated', 'calculated')])
    anchor_datetime = models.DateTimeField()
    source_content_type = models.ForeignKey('contenttypes.contenttype', on_delete=models.PROTECT, related_name='workflow_forecast_anchors', null=True, blank=True)
    source_object_id = models.PositiveBigIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    source_object = GenericForeignKey('source_content_type', 'source_object_id')

    class Meta:
        constraints = [
            models.CheckConstraint(check=(models.Q(source_content_type__isnull=True, source_object_id__isnull=True) | models.Q(source_content_type__isnull=False, source_object_id__gt=0, source_object_id__isnull=False)), name='wf_sched_anchor_source_pair'),
        ]

 
class WorkflowForecastRefresh(models.Model):
    """Coalesced, retryable recalculation requests; not part of forecast history."""
    workflow_key = models.CharField(max_length=100)
    object_id = models.PositiveBigIntegerField()
    reason = models.CharField(max_length=100)
    requested_at = models.DateTimeField(default=timezone.now)
    available_at = models.DateTimeField(default=timezone.now)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    latest_policy = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['workflow_key', 'object_id'],
                                    name='wf_forecast_refresh_unique'),
        ]
        indexes = [
            models.Index(fields=['available_at', 'id'], name='wf_forecast_refresh_due'),
        ]
