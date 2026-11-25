"""PostgreSQL-only database protections, including QuerySet and raw SQL writes."""
from datetime import date
from unittest import skipUnless
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import connection, IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from workflow.scheduling.models import (WorkflowSchedulePolicy, WorkflowCalendar,
    WorkflowCalendarException, WorkflowStageTiming, WorkflowTimingRule,
    WorkflowScheduleTransition, WorkflowForecast, WorkflowForecastStep, WorkflowForecastAnchor)
from order.scheduling_seed import seed_policy
from workflow.scheduling.policies import clone_policy


@skipUnless(connection.vendor == 'postgresql','PostgreSQL trigger protection')
class SchedulingProtectionTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_superuser(username='protection_admin',password=None)
        self.policy,_=seed_policy('order',user=self.user,publish=True)
        self.calendar=self.policy.calendars.get(code='working')
        self.stage=self.policy.stage_timings.get(workflow_key='order',stage_key='trade_approval')
        self.rule=self.stage.rules.first()

    def rejected(self, operation):
        with self.assertRaises(IntegrityError), transaction.atomic():
            operation()

    def test_published_policy_and_children_are_immutable(self):
        self.rejected(lambda: WorkflowSchedulePolicy.objects.filter(pk=self.policy.pk).update(name='changed'))
        self.rejected(lambda: WorkflowStageTiming.objects.filter(pk=self.stage.pk).update(default_duration=99))
        self.rejected(lambda: WorkflowTimingRule.objects.filter(pk=self.rule.pk).delete())
        self.rejected(lambda: WorkflowCalendarException.objects.bulk_create([
            WorkflowCalendarException(calendar=self.calendar,date=date(2027,1,1))]))
        self.rejected(lambda: WorkflowScheduleTransition.objects.filter(policy=self.policy).update(priority=99))
        self.calendar.name='changed'
        self.rejected(lambda: self.calendar.save(update_fields=['name']))
        draft=clone_policy(self.policy.pk,user=self.user)
        self.assertEqual(draft.status,'draft')
        stage=draft.stage_timings.get(workflow_key='order',stage_key='trade_approval')
        self.assertEqual(WorkflowStageTiming.objects.filter(pk=stage.pk).update(default_duration=5),1)
        self.rejected(lambda: WorkflowStageTiming.objects.filter(pk=stage.pk).update(calendar_id=self.calendar.pk))

    def test_raw_sql_is_guarded(self):
        def mutate():
            with connection.cursor() as cursor:
                cursor.execute('UPDATE workflow_workflowcalendar SET name=%s WHERE id=%s',['bad',self.calendar.pk])
        self.rejected(mutate)

    def test_forecast_history_is_append_only(self):
        now=timezone.now()
        row=WorkflowForecast.objects.create(content_type=ContentType.objects.get_for_model(self.policy),
            object_id=self.policy.pk,policy=self.policy,policy_version=self.policy.version,
            source_stage='order.trade_approval',target_stage='packing.warehouse',as_of=now)
        step=WorkflowForecastStep.objects.create(forecast=row,sequence=1,workflow_key='order',stage_key='trade_approval')
        anchor=WorkflowForecastAnchor.objects.create(forecast=row,stage_key='order.trade_approval',
            anchor_type='actual',anchor_datetime=now)
        self.rejected(lambda: WorkflowForecast.objects.filter(pk=row.pk).update(initial_estimated_at=now))
        self.rejected(lambda: WorkflowForecastStep.objects.filter(pk=step.pk).update(standard_duration=10))
        self.rejected(lambda: WorkflowForecastAnchor.objects.filter(pk=anchor.pk).delete())
        self.assertEqual(WorkflowForecast.objects.filter(pk=row.pk).update(is_current=False),1)
        self.rejected(lambda: WorkflowForecast.objects.filter(pk=row.pk).update(is_current=True))
        self.rejected(lambda: WorkflowForecastStep.objects.create(forecast=row,sequence=2,workflow_key='order',stage_key='supplier_dispatch'))
        self.rejected(lambda: WorkflowForecast.objects.filter(pk=row.pk).delete())
