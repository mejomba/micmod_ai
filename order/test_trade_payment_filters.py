"""Trade payment filter and summary regressions (no Sepidar calls)."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from ajax_datatable import AjaxDatatableView
from django.core.paginator import Paginator
from django.test import SimpleTestCase, TestCase

from inquiry.models import Supplier
from micmod_base.base import Currency
from order.models import Order, OrderPayment, OrderPaymentItem
from order.trade_payment_filters import apply_payment_filter, format_total, parse_payment_date, payment_totals
from order.views import OrderDataTableListView


TODAY = date(2026, 11, 28)


class PaymentFilterValidationTests(SimpleTestCase):
    def test_strict_iso_dates_and_invalid_dates(self):
        self.assertEqual(parse_payment_date('2026-11-28'), TODAY)
        for invalid in ('', None, '2026-02-30', '20261128', '2026-11-8'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                parse_payment_date(invalid)

    def test_amount_format(self):
        self.assertEqual(format_total(Decimal('12500.5000')), '12,500.5')
        self.assertEqual(format_total(Decimal('0.0000')), '0')
        self.assertEqual(format_total(None), '0')


class TradePaymentFiltersTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        rmb = Currency.objects.create(title='Yuan', title_en='RMB')
        usd = Currency.objects.create(title='Dollar', title_en='USD')
        supplier = Supplier.objects.bulk_create([Supplier(title='Payment filter test vendor')])[0]
        header = OrderPayment.objects.bulk_create([
            OrderPayment(vendor_party=supplier, total_amount=50, currency=usd),
        ])[0]
        a, b, c, d, e = Order.objects.bulk_create([
            Order(order_number='PAY-FILTER-A', currency=rmb),
            Order(order_number='PAY-FILTER-B', currency=usd),
            Order(order_number='PAY-FILTER-C', currency=rmb),
            Order(order_number='PAY-FILTER-D', currency=rmb),
            Order(order_number='PAY-FILTER-E', currency=None),
        ])
        cls.ids = [a.pk, b.pk, c.pk, d.pk, e.pk]

        def row(order, day, amount, paid=False, **kwargs):
            return OrderPaymentItem(
                order=order, pay_date=date(2026, 11, day) if day else None,
                total_amount=amount, is_pay=paid, **kwargs,
            )

        OrderPaymentItem.objects.bulk_create([
            row(a, 20, 10, True),
            row(a, 25, 20),
            row(a, 28, 30),
            row(a, 29, 40),
            row(a, 29, 40),
            row(a, 30, 50, True, payment=header, currency=rmb),
            row(a, None, 60, True),
            row(a, None, 70),
            row(a, 29, 99, is_deleted=True),
            row(b, 29, 100, True),
            row(b, 28, 110, True),
            row(b, 20, 120, True),
            row(c, 20, 5, True),
            row(c, 30, 6),
            row(d, 25, 999, is_deleted=True),
            row(d, 29, 999, is_deleted=True),
            row(e, 28, 7),
            row(e, 20, 8, currency=usd),
            OrderPaymentItem(order=None, total_amount=999, pay_date=TODAY),
        ])

    def queryset(self):
        return Order.objects.filter(pk__in=self.ids)

    def numbers(self, mode, start='', end=''):
        qs = apply_payment_filter(self.queryset(), mode, start, end, TODAY)
        return list(qs.order_by('order_number').values_list('order_number', flat=True))

    def test_scheduled_includes_paid_future_and_does_not_duplicate_orders(self):
        self.assertEqual(self.numbers('scheduled'), ['PAY-FILTER-A', 'PAY-FILTER-B', 'PAY-FILTER-C'])

    def test_overdue_requires_date_and_unpaid_on_same_row(self):
        self.assertEqual(self.numbers('overdue'), ['PAY-FILTER-A', 'PAY-FILTER-E'])

    def test_today_includes_paid_and_unpaid(self):
        self.assertEqual(self.numbers('today'), ['PAY-FILTER-A', 'PAY-FILTER-B', 'PAY-FILTER-E'])

    def test_due_until_is_inclusive_and_unpaid(self):
        self.assertEqual(self.numbers('due_until', end='2026-11-28'), ['PAY-FILTER-A', 'PAY-FILTER-E'])
        self.assertEqual(self.numbers('due_until', end='2026-11-30'), ['PAY-FILTER-A', 'PAY-FILTER-C', 'PAY-FILTER-E'])

    def test_range_is_inclusive_and_includes_paid(self):
        self.assertEqual(self.numbers('date_range', '2026-11-29', '2026-11-29'),
                         ['PAY-FILTER-A', 'PAY-FILTER-B'])
        self.assertEqual(self.numbers('date_range', '2026-11-30', '2026-11-30'),
                         ['PAY-FILTER-A', 'PAY-FILTER-C'])

    def test_invalid_filter_or_dates_are_rejected(self):
        for mode, start, end in [
            ('invalid', '', ''), ('due_until', '', ''),
            ('date_range', '', '2026-11-29'), ('date_range', '2026-11-30', '2026-11-29'),
        ]:
            with self.subTest(mode=mode, start=start, end=end), self.assertRaises(ValueError):
                self.numbers(mode, start, end)

    @staticmethod
    def amounts(summary, category):
        return {row['currency']: Decimal(row['amount'].replace(',', '')) for row in summary['totals'][category]}

    def test_summary_counts_all_rows_of_filtered_orders_and_separates_currencies(self):
        qs = apply_payment_filter(self.queryset(), 'scheduled', '', '', TODAY)
        summary = payment_totals(qs, TODAY)
        self.assertEqual(summary['order_count'], 3)
        self.assertEqual(self.amounts(summary, 'paid'), {'RMB': 75, 'USD': 380})
        self.assertEqual(self.amounts(summary, 'overdue'), {'RMB': 20})
        self.assertEqual(self.amounts(summary, 'today'), {'RMB': 30})
        self.assertEqual(self.amounts(summary, 'scheduled'), {'RMB': 86})
        self.assertEqual(self.amounts(summary, 'undated'), {'RMB': 70})
        self.assertEqual(summary['totals']['scheduled'][0]['count'], 3)

    def test_missing_currency_and_no_matches(self):
        summary = payment_totals(self.queryset().filter(order_number='PAY-FILTER-E'), TODAY)
        self.assertEqual(self.amounts(summary, 'today'), {'ارز نامشخص': 7})
        self.assertEqual(self.amounts(summary, 'overdue'), {'USD': 8})
        empty = payment_totals(self.queryset().none(), TODAY)
        self.assertEqual(empty['order_count'], 0)
        self.assertTrue(all(not rows for rows in empty['totals'].values()))

    def trade_view(self, mode='scheduled', **params):
        view = OrderDataTableListView()
        view.request = SimpleNamespace(
            user=SimpleNamespace(base_group='trade', is_superuser=False),
            POST={'q': 'all', 'payment_filter': mode, **params},
        )
        return view

    def test_response_uses_full_filtered_queryset_not_page(self):
        view = self.trade_view()
        with patch('order.views.timezone.localdate', return_value=TODAY):
            qs = view.get_initial_queryset(view.request).filter(pk__in=self.ids).only('id', 'order_number')
        # Simulate a column/global search narrowing three matching orders to two.
        qs = qs.exclude(order_number='PAY-FILTER-C')
        paginator = Paginator(qs, 1)
        self.assertEqual(paginator.count, 2)
        for start in (0, 1):
            with patch.object(AjaxDatatableView, 'get_response_dict', return_value={'draw': 1, 'data': []}):
                response = view.get_response_dict(view.request, paginator, 1, start)
            summary = response['payment_summary']
            self.assertEqual(summary['order_count'], 2)
            self.assertEqual(self.amounts(summary, 'scheduled'), {'RMB': 80})
            self.assertEqual(self.amounts(summary, 'paid'), {'RMB': 70, 'USD': 380})

    def test_invalid_date_fails_closed_with_message(self):
        view = self.trade_view('due_until', payment_end='wrong')
        qs = view.get_initial_queryset(view.request)
        self.assertEqual(qs.count(), 0)
        with patch.object(AjaxDatatableView, 'get_response_dict', return_value={'draw': 1, 'data': []}):
            response = view.get_response_dict(view.request, Paginator(qs, 10), 1, 0)
        self.assertTrue(response['payment_summary']['error'])

    def test_non_trade_does_not_receive_financial_summary(self):
        view = self.trade_view()
        view.request.user.base_group = 'sales'
        with patch.object(AjaxDatatableView, 'get_response_dict', return_value={'draw': 1, 'data': []}):
            response = view.get_response_dict(view.request, Paginator(self.queryset(), 10), 1, 0)
        self.assertNotIn('payment_summary', response)
