"""HTTP export regression tests; require the Django project test database."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch
from io import BytesIO

from django.test import RequestFactory, SimpleTestCase, TestCase
from openpyxl import load_workbook

from micmod_base.base import Currency
from order.models import Order, OrderPaymentItem
from order.views import trade_order_excel


class TradeExcelAccessTests(SimpleTestCase):
    def test_rejects_nontrade_and_anonymous(self):
        for user in (SimpleNamespace(is_authenticated=False), SimpleNamespace(is_authenticated=True, base_group='sales')):
            request = RequestFactory().post('/order/list/trade-excel/', {'export_fields[]': ['order_number']})
            request.user = user
            request._dont_enforce_csrf_checks = True
            self.assertEqual(trade_order_excel(request).status_code, 403)

    def test_rejects_invalid_field(self):
        request = RequestFactory().post('/order/list/trade-excel/', {'export_fields[]': ['password']})
        request.user = SimpleNamespace(is_authenticated=True, base_group='trade')
        request._dont_enforce_csrf_checks = True
        self.assertEqual(trade_order_excel(request).status_code, 400)


class TradeExcelFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        currency = Currency.objects.create(title='Yuan', title_en='RMB')
        orders = Order.objects.bulk_create([
            Order(order_number='EXPORT-MATCH-A', currency=currency),
            Order(order_number='EXPORT-MATCH-B', currency=currency),
            Order(order_number='EXPORT-OTHER', currency=currency),
            Order(order_number='EXPORT-MATCH-DELETED', currency=currency, is_deleted=True),
        ])
        OrderPaymentItem.objects.bulk_create([
            OrderPaymentItem(order=order, pay_date=date(2026, 11, 29), total_amount=100)
            for order in orders
        ])

    def test_exports_all_matching_orders_ignoring_page_length(self):
        request = RequestFactory().post('/order/list/trade-excel/', {
            'export_fields[]': ['order_number', 'scheduled'],
            'q': 'all', 'payment_filter': 'scheduled', 'draw': '3', 'start': '0', 'length': '1',
            'columns[0][name]': 'order_number', 'columns[0][searchable]': 'true',
            'columns[0][orderable]': 'true', 'columns[0][search][value]': 'EXPORT-MATCH',
            'order[0][column]': '0', 'order[0][dir]': 'asc',
        })
        request.user = SimpleNamespace(is_authenticated=True, base_group='trade', is_superuser=False)
        request._dont_enforce_csrf_checks = True
        with patch('order.views.timezone.localdate', return_value=date(2026, 11, 28)):
            response = trade_order_excel(request)
        self.assertEqual(response.status_code, 200)
        wb = load_workbook(BytesIO(response.content))
        self.assertEqual(list(wb['Orders'].values)[1:], [
            ('EXPORT-MATCH-A', '100 RMB'), ('EXPORT-MATCH-B', '100 RMB'),
        ])
        self.assertIn('attachment', response['Content-Disposition'])

    def test_superuser_nontrade_can_export_with_payment_filter(self):
        request = RequestFactory().post('/order/list/trade-excel/', {
            'export_fields[]': ['order_number', 'scheduled'],
            'q': 'active', 'payment_filter': 'scheduled', 'draw': '3', 'start': '0', 'length': '1',
            'columns[0][name]': 'order_number', 'columns[0][searchable]': 'true',
            'columns[0][orderable]': 'true', 'columns[0][search][value]': 'EXPORT-MATCH',
            'order[0][column]': '0', 'order[0][dir]': 'asc',
        })
        request.user = SimpleNamespace(is_authenticated=True, base_group='sales', is_superuser=True)
        request._dont_enforce_csrf_checks = True
        with patch('order.views.timezone.localdate', return_value=date(2026, 11, 28)):
            response = trade_order_excel(request)
        self.assertEqual(response.status_code, 200)
        wb = load_workbook(BytesIO(response.content))
        self.assertEqual(list(wb['Orders'].values)[1:], [
            ('EXPORT-MATCH-A', '100 RMB'), ('EXPORT-MATCH-B', '100 RMB'),
        ])
