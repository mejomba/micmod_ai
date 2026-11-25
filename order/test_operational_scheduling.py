from datetime import date
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone
from order.models import Order, Packing, GIO, GIOItem, PackingItem, PackingSepidarTransfer, PackingSepidarTransferItem
from order.scheduling_adapters import forecast_order_arrival, order_state
from order.scheduling_seed import seed_policy
from workflow.models import WorkFlow


class OperationalSchedulingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(username='eta_admin', password=None)
        self.policy, _ = seed_policy('order', user=self.user, publish=True)
        self.order = Order.objects.create(quantity=1000, production_lead_time=0, transportation_method='air')
        WorkFlow.objects.create(content_type=ContentType.objects.get_for_model(Order),
            object_id=self.order.pk, state='تایید مدیر فروش', current_state_name='تایید بازرگانی',
            wf_status=3, to_user=self.user)

    def test_seed_idempotence_and_virtual_prediction(self):
        repeated, created = seed_policy('order', user=self.user)
        self.assertFalse(created)
        self.assertEqual(repeated.pk, self.policy.pk)
        result = forecast_order_arrival(self.order)
        self.assertIsNotNone(result['complete_arrival'])
        self.assertEqual(result['status'], 'provisional')
        self.assertEqual(len(result['shipments']), 1)
        self.assertEqual(GIO.objects.count(), 0)
        self.assertEqual(Packing.objects.count(), 0)
        self.order.refresh_from_db()
        self.assertEqual(self.order.production_lead_time, 0)
        self.assertIsNone(self.order.trade_commitment_date)

    def test_declared_packing_and_remaining_gio_do_not_double_count(self):
        gio = GIO.objects.create(gio_date=date.today(), manual_weight_kg=Decimal('16000'))
        GIOItem.objects.create(gio=gio, order=self.order, quantity=750)
        packing = Packing.objects.create(shipment_type='air', estimated_arrive_to_wh_date=date.today())
        PackingItem.objects.create(packing=packing, order=self.order, quantity=400)
        result = forecast_order_arrival(self.order)
        self.assertEqual(sum(s.quantity for s in result['shipments']), 1000)
        self.assertEqual([s.quantity for s in result['shipments']], [400, 350, 250])
        self.assertEqual(result['shipments'][0].source, 'declared')

    def test_warehouse_entry_not_actual_receipt(self):
        from django.conf import settings
        packing = Packing.objects.create(shipment_type='air', estimated_arrive_to_wh_date=date.today())
        item = PackingItem.objects.create(packing=packing, order=self.order, quantity=1000)
        WorkFlow.objects.create(content_type=ContentType.objects.get_for_model(Packing),
            object_id=packing.pk, state='ترخیص', current_state_name='انبار', wf_status=3, to_user=self.user)
        self.assertEqual(forecast_order_arrival(self.order)['received_quantity'], 0)
        transfer = PackingSepidarTransfer.objects.create(packing=packing, transfer_type='normal',
            source_stock_ref=91, destination_stock_ref=settings.SEPIDAR_CONST_DATA['central_wh_id'],
            status='success', receipt_id=123, sent_at=timezone.now())
        PackingSepidarTransferItem.objects.create(transfer=transfer, packing_item=item, item_ref=1, quantity=1000)
        result = forecast_order_arrival(self.order)
        self.assertEqual(result['received_quantity'], 1000)
        self.assertEqual(result['status'], 'actual')
        self.assertEqual(result['complete_arrival'], transfer.sent_at)
        self.assertIsNotNone(result['shipments'][0].declared)
        self.assertEqual(result['shipments'][0].source, 'actual')

    def test_other_destination_not_a_central_receipt(self):
        packing = Packing.objects.create(shipment_type='air', estimated_arrive_to_wh_date=date.today())
        item = PackingItem.objects.create(packing=packing, order=self.order, quantity=1000)
        transfer = PackingSepidarTransfer.objects.create(packing=packing, transfer_type='damaged',
            source_stock_ref=91, destination_stock_ref=42, status='success', receipt_id=456,
            sent_at=timezone.now())
        PackingSepidarTransferItem.objects.create(transfer=transfer, packing_item=item, item_ref=1, quantity=1000)
        result = forecast_order_arrival(self.order)
        self.assertEqual(result['received_quantity'], 0)
        self.assertIsNone(result['complete_arrival'])
        self.assertEqual(result['status'], 'incomplete')

    def test_cancelled_order(self):
        Order.objects.filter(pk=self.order.pk).update(sales_admin_cancel=True)
        self.order.refresh_from_db()
        self.assertEqual(forecast_order_arrival(self.order)['status'], 'cancelled')

    def test_terminal_order_still_reads_actual_receipt(self):
        from django.conf import settings
        from order.forecast_service import recalculate
        first, _ = recalculate('order', self.order.pk, reason='backfill')
        packing = Packing.objects.create(shipment_type='air')
        item = PackingItem.objects.create(packing=packing, order=self.order, quantity=1000)
        transfer = PackingSepidarTransfer.objects.create(packing=packing, transfer_type='normal',
            source_stock_ref=91, destination_stock_ref=settings.SEPIDAR_CONST_DATA['central_wh_id'],
            status='success', receipt_id=123, sent_at=timezone.now())
        PackingSepidarTransferItem.objects.create(transfer=transfer, packing_item=item, item_ref=1, quantity=1000)
        WorkFlow.objects.create(content_type=ContentType.objects.get_for_model(Order),
            object_id=self.order.pk, state='پرداخت / PACKING / GIO', current_state_name='مرحله نهایی',
            wf_status=3,to_user=self.user)
        self.assertEqual(order_state(self.order).stage,'order.done')
        result = forecast_order_arrival(self.order)
        self.assertEqual(result['status'],'actual')
        latest, changed = recalculate('order', self.order.pk)
        self.assertTrue(changed)
        self.assertEqual(latest.actual_at,transfer.sent_at)
        self.assertEqual(latest.initial_estimated_at,first.initial_estimated_at)
        # Later edits to source evidence cannot silently move an actual date.
        from datetime import timedelta
        PackingSepidarTransfer.objects.filter(pk=transfer.pk).update(sent_at=transfer.sent_at-timedelta(days=1))
        frozen, changed = recalculate('order',self.order.pk,latest_policy=True)
        self.assertFalse(changed)
        self.assertEqual(frozen.pk,latest.pk)
        self.assertEqual(frozen.actual_at,transfer.sent_at)

    def test_terminal_packing_without_receipt_is_not_declared_complete(self):
        packing = Packing.objects.create(shipment_type='air',estimated_arrive_to_wh_date=date.today())
        PackingItem.objects.create(packing=packing, order=self.order, quantity=1000)
        WorkFlow.objects.create(content_type=ContentType.objects.get_for_model(Packing),
            object_id=packing.pk,state='انبار',current_state_name='اتمام کار',wf_status=3,to_user=self.user)
        result = forecast_order_arrival(self.order)
        self.assertEqual(result['status'],'incomplete')
        self.assertIsNone(result['complete_arrival'])
        self.assertEqual(result['received_quantity'],0)
