"""Django regression tests for deferred columns and payment query count."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase

from micmod_base.base import Currency
from order.models import Order, OrderPaymentItem
from order.trade_payment_schedule import render_payment_schedule
from order.views import OrderDataTableListView


def trade_view():
    view = OrderDataTableListView()
    view.request = SimpleNamespace(
        user=SimpleNamespace(base_group='trade', is_superuser=False),
        POST={'q': 'all'},
    )
    return view


class TradePaymentDatatableTests(SimpleTestCase):
    def test_order_currency_annotation_survives_deferred_fields(self):
        view = trade_view()
        queryset = view.get_initial_queryset(view.request).only('id', 'order_number')
        self.assertIn('list_order_currency_title', queryset.query.annotations)
        self.assertIn('currency', str(queryset.query).lower())
        self.assertFalse(queryset.query.select_related)

    def test_unattached_payment_does_not_hide_gio_or_packing(self):
        view = trade_view()
        obj = SimpleNamespace(
            list_order_currency_title='RMB',
            list_payment_items=[SimpleNamespace(
                pk=1, is_deleted=False, is_pay=False, pay_date=date(2026, 11, 30),
                payment_id=None, currency=None, total_amount=12500,
            )],
            delay_reason=Mock(), workflows=Mock(), gio_items=Mock(), packing_item_order=Mock(),
        )
        obj.delay_reason.all.return_value = []
        obj.workflows.filter.return_value.order_by.return_value.first.return_value = None
        obj.gio_items.select_related.return_value.all.return_value = [
            SimpleNamespace(quantity=10, gio=SimpleNamespace(pk=8)),
        ]
        obj.packing_item_order.select_related.return_value.all.return_value = [
            SimpleNamespace(quantity=5, packing=SimpleNamespace(pk=9)),
        ]
        row = {}
        with patch('order.views.timezone.localdate', return_value=date(2026, 11, 28)), \
                patch('order.views.reverse_lazy', return_value='/document/'):
            view.customize_row_trade(row, obj)
        self.assertIn('12,500 RMB 2026/11/30', row['future_payments'])
        self.assertIn('10 in 8', row['gio'])
        self.assertIn('5 in 9', row['packing'])


class TradePaymentQueryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        rmb = Currency.objects.create(title='Yuan', title_en='RMB')
        orders = Order.objects.bulk_create([
            Order(order_number='PAY-SCHEDULE-1', currency=rmb),
            Order(order_number='PAY-SCHEDULE-2', currency=rmb),
        ])
        OrderPaymentItem.objects.bulk_create([
            OrderPaymentItem(order=orders[0], pay_date=date(2026, 11, 29), total_amount=10),
            OrderPaymentItem(order=orders[0], pay_date=date(2026, 11, 30), total_amount=20),
            OrderPaymentItem(order=orders[1], pay_date=date(2026, 11, 29), total_amount=30),
            OrderPaymentItem(order=orders[1], pay_date=date(2026, 11, 29), total_amount=99, is_deleted=True),
        ])
        cls.order_ids = [order.pk for order in orders]

    def test_two_queries_for_multiple_orders_and_their_payment_rows(self):
        view = trade_view()
        queryset = view.get_initial_queryset(view.request).filter(pk__in=self.order_ids).only(
            'id', 'order_number',
        )
        # One order query (including currency title) and one payment prefetch.
        with self.assertNumQueries(2):
            rows = {
                order.order_number: render_payment_schedule(
                    order.list_payment_items, order.list_order_currency_title, date(2026, 11, 28),
                )[0]
                for order in queryset
            }
        self.assertIn('10 RMB', rows['PAY-SCHEDULE-1'])
        self.assertIn('20 RMB', rows['PAY-SCHEDULE-1'])
        self.assertIn('30 RMB', rows['PAY-SCHEDULE-2'])
        self.assertNotIn('99 RMB', rows['PAY-SCHEDULE-2'])
