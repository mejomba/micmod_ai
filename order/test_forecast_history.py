from datetime import date
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from order.forecast_service import recalculate
from order.models import Order, GIO, GIOItem
from order.scheduling_queue import enqueue, drain
from order.scheduling_seed import seed_policy
from workflow.models import WorkFlow
from workflow.scheduling.models import WorkflowForecast, WorkflowForecastRefresh


class ForecastHistoryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(username='forecast_history_admin', password=None)
        self.policy, _ = seed_policy('order', user=self.user, publish=True)
        self.order = Order.objects.create(quantity=1000, production_lead_time=0, transportation_method='air')
        self.ct = ContentType.objects.get_for_model(Order)
        WorkFlow.objects.create(content_type=self.ct, object_id=self.order.pk, state='تایید مدیر فروش',
                                current_state_name='تایید بازرگانی', wf_status=3, to_user=self.user)

    def records(self):
        return WorkflowForecast.objects.filter(content_type=self.ct, object_id=self.order.pk).order_by('revision')

    def test_initial_and_idempotent_history(self):
        first, changed = recalculate('order', self.order.pk, reason='backfill')
        self.assertTrue(changed)
        self.assertTrue(first.initial_is_backfill)
        self.assertIsNotNone(first.initial_estimated_at)
        self.assertTrue(first.steps.exists())
        self.assertTrue(first.anchors.exists())
        second, changed = recalculate('order', self.order.pk)
        self.assertFalse(changed)
        self.assertEqual(first.pk, second.pk)
        Order.objects.filter(pk=self.order.pk).update(production_lead_time=10)
        third, changed = recalculate('order', self.order.pk)
        self.assertTrue(changed)
        self.assertEqual(third.initial_estimated_at, first.initial_estimated_at)
        self.assertEqual(third.revision, 2)
        self.assertEqual(self.records().filter(is_current=True).count(), 1)
        first.refresh_from_db()
        self.assertFalse(first.is_current)
        self.assertIsNotNone(third.policy_snapshot['calendars'])

    def test_cancelled_and_dry_run(self):
        result, changed = recalculate('order', self.order.pk, dry_run=True)
        self.assertFalse(changed)
        self.assertIsNotNone(result['complete_arrival'])
        self.assertFalse(self.records().exists())
        first, _ = recalculate('order', self.order.pk, reason='trade_entry')
        self.assertFalse(first.initial_is_backfill)
        Order.objects.filter(pk=self.order.pk).update(sales_admin_cancel=True)
        row, _ = recalculate('order', self.order.pk)
        self.assertEqual(row.forecast_status, 'cancelled')
        self.assertIsNone(row.effective_estimated_at)
        self.assertEqual(row.initial_estimated_at, first.initial_estimated_at)

    def test_queue_coalescing_and_retry(self):
        enqueue('order', self.order.pk, 'trade_entry')
        enqueue('order', self.order.pk, 'order_changed')
        self.assertEqual(WorkflowForecastRefresh.objects.count(), 1)
        self.assertEqual(WorkflowForecastRefresh.objects.get().reason, 'trade_entry')
        with patch('order.scheduling_queue.recalculate', side_effect=RuntimeError('test failure')):
            self.assertEqual(drain(1)['failed'], 1)
        job = WorkflowForecastRefresh.objects.get()
        self.assertEqual(job.attempts, 1)
        self.assertIn('test failure', job.last_error)
        WorkflowForecastRefresh.objects.update(available_at=timezone.now())
        self.assertEqual(drain(1)['changed'], 1)
        self.assertFalse(WorkflowForecastRefresh.objects.exists())

    @override_settings(WORKFLOW_SCHEDULING_AUTO_ENABLED=True)
    def test_events_after_commit_and_rollback(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.order.production_lead_time = 9
            self.order.save()
            self.assertFalse(WorkflowForecastRefresh.objects.exists())
        self.assertTrue(WorkflowForecastRefresh.objects.filter(workflow_key='order', object_id=self.order.pk).exists())
        WorkflowForecastRefresh.objects.all().delete()
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    self.order.production_lead_time = 11
                    self.order.save()
                    raise RuntimeError('rollback')
            except RuntimeError:
                pass
        self.assertFalse(WorkflowForecastRefresh.objects.exists())

    @override_settings(WORKFLOW_SCHEDULING_AUTO_ENABLED=True)
    def test_reassignment_and_description_do_not_enqueue(self):
        with self.captureOnCommitCallbacks(execute=True):
            WorkFlow.objects.create(content_type=self.ct, object_id=self.order.pk, state='تایید بازرگانی',
                                    current_state_name='تایید بازرگانی', wf_status=4, to_user=self.user)
        self.assertFalse(WorkflowForecastRefresh.objects.exists())

    @override_settings(WORKFLOW_SCHEDULING_AUTO_ENABLED=True)
    def test_gio_removal_refreshes_old_order(self):
        gio = GIO.objects.create(gio_date=date.today(), manual_weight_kg=Decimal('12000'))
        row = GIOItem.objects.create(gio=gio, order=self.order, quantity=5)
        with self.captureOnCommitCallbacks(execute=True):
            row.is_deleted = True
            row.save()
        self.assertTrue(WorkflowForecastRefresh.objects.filter(workflow_key='order', object_id=self.order.pk).exists())

    def test_command_preview_does_not_write(self):
        call_command('recalculate_workflow_forecasts', order_id=[self.order.pk], dry_run=True)
        self.assertFalse(self.records().exists())
