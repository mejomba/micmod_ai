"""Database constraints and model validation for the scheduling subsystem."""
from datetime import date
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from workflow.scheduling.models import (
    WorkflowSchedulePolicy, WorkflowCalendar, WorkflowCalendarException,
    WorkflowStageTiming, WorkflowTimingRule, WorkflowScheduleTransition,
    WorkflowForecast, WorkflowForecastStep, WorkflowForecastAnchor,
)


class SchedulingModelTests(TestCase):
    def setUp(self):
        self.policy = WorkflowSchedulePolicy.objects.create(name='Generic', code='generic', workflow_key='test')
        self.calendar = WorkflowCalendar.objects.create(policy=self.policy, name='Working', code='work', working_weekdays=[0, 1, 2, 5, 6])
        self.stage = WorkflowStageTiming.objects.create(policy=self.policy, calendar=self.calendar, workflow_key='test', stage_key='review', default_duration=2)

    def assert_constraint(self, create):
        with self.assertRaises(IntegrityError), transaction.atomic():
            create()

    def test_policy_version_and_publication_constraints(self):
        self.assert_constraint(lambda: WorkflowSchedulePolicy.objects.create(name='Duplicate', code='generic', workflow_key='test'))
        self.assert_constraint(lambda: WorkflowSchedulePolicy.objects.create(name='Invalid', code='invalid', workflow_key='test', is_active=True))
        v2 = WorkflowSchedulePolicy.objects.create(name='New', code='generic', workflow_key='test', version=2)
        self.assertNotEqual(v2.pk, self.policy.pk)

    def test_calendar_validation_and_unique_exception(self):
        self.calendar.working_weekdays = [True, 2]
        with self.assertRaises(ValidationError):
            self.calendar.full_clean()
        WorkflowCalendarException.objects.create(calendar=self.calendar, date=date(2026, 11, 26))
        self.assert_constraint(lambda: WorkflowCalendarException.objects.create(calendar=self.calendar, date=date(2026, 11, 26), is_working_day=True))

    def test_stage_calendar_version_and_duration(self):
        other = WorkflowSchedulePolicy.objects.create(name='New', code='generic', workflow_key='test', version=2)
        stage = WorkflowStageTiming(policy=other, calendar=self.calendar, workflow_key='test', stage_key='review')
        with self.assertRaises(ValidationError):
            stage.full_clean()
        self.assert_constraint(lambda: WorkflowStageTiming.objects.create(policy=self.policy, calendar=self.calendar, workflow_key='test', stage_key='negative', default_duration=-1))

    def test_rule_validation(self):
        rule = WorkflowTimingRule(stage_timing=self.stage, name='invalid', effect_json={'operation': 'set_duration', 'value': -1})
        with self.assertRaises(ValidationError):
            rule.full_clean()

    def test_transition_self_loop_validation(self):
        edge = WorkflowScheduleTransition(policy=self.policy, source_workflow='test', source_stage='review', target_workflow='test', target_stage='review')
        with self.assertRaises(ValidationError):
            edge.full_clean()

    def forecast_fields(self):
        now = timezone.now()
        return dict(content_type=ContentType.objects.get_for_model(self.policy), object_id=self.policy.pk,
                    policy=self.policy, policy_version=1, source_stage='test.review', target_stage='test.done',
                    as_of=now, calculated_estimated_at=now, effective_estimated_at=now,
                    initial_estimated_at=now, forecast_source='calculated', forecast_status='estimated')

    def test_forecast_current_uniqueness_and_history(self):
        fields = self.forecast_fields()
        first = WorkflowForecast.objects.create(**fields)
        self.assertEqual(first.content_object, self.policy)
        self.assert_constraint(lambda: WorkflowForecast.objects.create(**fields, revision=2))
        WorkflowForecast.objects.filter(pk=first.pk).update(is_current=False)
        second = WorkflowForecast.objects.create(**fields, revision=2)
        self.assertEqual(second.initial_estimated_at, first.initial_estimated_at)
        self.assertEqual(WorkflowForecast.objects.filter(is_current=True).count(), 1)
        self.assert_constraint(lambda: WorkflowForecast.objects.create(**fields, revision=2, is_current=False))

    def test_source_priority_validation(self):
        fields = self.forecast_fields()
        forecast = WorkflowForecast(**fields, actual_at=fields['as_of'])
        with self.assertRaises(ValidationError):
            forecast.full_clean()
        forecast.forecast_source = 'actual'
        forecast.forecast_status = 'actual'
        forecast.full_clean()

    def test_steps_and_anchors(self):
        forecast = WorkflowForecast.objects.create(**self.forecast_fields())
        WorkflowForecastStep.objects.create(forecast=forecast, sequence=1, workflow_key='test', stage_key='review', calendar=self.calendar, duration_components=[{'days': 2, 'calendar': 'work'}])
        self.assert_constraint(lambda: WorkflowForecastStep.objects.create(forecast=forecast, sequence=1, workflow_key='test', stage_key='done'))
        anchor = WorkflowForecastAnchor.objects.create(forecast=forecast, stage_key='test.done', anchor_type='actual', anchor_datetime=timezone.now(), source_content_type=forecast.content_type, source_object_id=self.policy.pk)
        self.assertEqual(anchor.source_object, self.policy)
        self.assert_constraint(lambda: WorkflowForecastAnchor.objects.create(forecast=forecast, stage_key='test.done', anchor_type='actual', anchor_datetime=timezone.now(), source_object_id=self.policy.pk))
