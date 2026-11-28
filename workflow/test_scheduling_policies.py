from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from workflow.scheduling.models import (
    WorkflowSchedulePolicy, WorkflowCalendar, WorkflowCalendarException,
    WorkflowStageTiming, WorkflowTimingRule, WorkflowScheduleTransition,
)
from workflow.scheduling.policies import clone_policy, publish_policy, select_policy


class PolicyVersionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(username='schedule_admin', password=None)
        self.viewer = User.objects.create_user(username='schedule_viewer', password=None)
        self.policy = WorkflowSchedulePolicy.objects.create(
            name='Test policy', code='example', workflow_key='quotation')
        self.cal = WorkflowCalendar.objects.create(
            policy=self.policy, name='Working', code='work', working_weekdays=[0, 1, 2, 5, 6])
        WorkflowCalendarException.objects.create(calendar=self.cal, date=date(2026, 11, 26))
        self.timing = WorkflowStageTiming.objects.create(policy=self.policy,
            calendar=self.cal, workflow_key='quotation', stage_key='review', default_duration=1)
        WorkflowTimingRule.objects.create(stage_timing=self.timing, name='Example',
            effect_json={'operation': 'add_duration', 'value': 2})
        WorkflowScheduleTransition.objects.create(policy=self.policy, source_workflow='quotation',
            source_stage='review', target_workflow='quotation', target_stage='done')

    def test_clone_remaps_relations_and_leaves_source_unchanged(self):
        draft = clone_policy(self.policy.pk, user=self.admin)
        self.assertEqual(draft.version, 2)
        self.assertEqual(draft.status, 'draft')
        cal = draft.calendars.get()
        self.assertNotEqual(cal.pk, self.cal.pk)
        self.assertEqual(draft.stage_timings.get().calendar_id, cal.pk)
        self.assertEqual(cal.exceptions.count(), 1)
        self.assertEqual(draft.stage_timings.get().rules.get().effect_json['value'], 2)
        self.assertEqual(draft.transitions.count(), 1)
        cal.working_weekdays = [0]
        cal.save(update_fields=['working_weekdays'])
        self.cal.refresh_from_db()
        self.assertEqual(self.cal.working_weekdays, [0, 1, 2, 5, 6])

    def test_permission_and_validation_fail_closed(self):
        with self.assertRaises(PermissionDenied):
            clone_policy(self.policy.pk, user=self.viewer)
        with self.assertRaises(PermissionDenied):
            publish_policy(self.policy.pk, user=self.viewer, validate=lambda p: None)
        with self.assertRaises(ValidationError):
            publish_policy(self.policy.pk, user=self.admin, validate=None)
        def invalid(policy):
            raise ValidationError('Invalid route')
        with self.assertRaises(ValidationError):
            publish_policy(self.policy.pk, user=self.admin, validate=invalid)
        self.policy.refresh_from_db()
        self.assertEqual(self.policy.status, 'draft')

    def test_future_publication_and_old_version_preservation(self):
        now = timezone.now()
        first = publish_policy(self.policy.pk, user=self.admin,
            validate=lambda p: None, effective_from=now)
        draft = clone_policy(first.pk, user=self.admin)
        second = publish_policy(draft.pk, user=self.admin, validate=lambda p: None,
            effective_from=now + timedelta(days=1))
        self.assertEqual(select_policy('quotation', 'example', as_of=now).pk, first.pk)
        self.assertEqual(select_policy('quotation', 'example', as_of=now + timedelta(days=2)).pk, second.pk)
        first.refresh_from_db()
        self.assertEqual(first.status, 'published')
        self.assertEqual(first.version, 1)
        with self.assertRaises(ValidationError):
            publish_policy(first.pk, user=self.admin, validate=lambda p: None)
