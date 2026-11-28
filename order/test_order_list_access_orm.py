"""Integration checks for the shared order-list toolbar and payment columns."""
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase

from order.order_list_access import can_view_order_payments
from order.trade_order_excel import EXPORT_FIELDS
from order.views import OrderDataTableListView


class OrderListAccessIntegrationTests(SimpleTestCase):
    def user(self, role, admin):
        return SimpleNamespace(base_group=role, is_superuser=admin)

    def test_payment_columns_present_exactly_once_for_authorized_roles(self):
        for role in ('trade', 'sales', 'mac', 'bazar', None):
            for admin in (False, True):
                with self.subTest(role=role, admin=admin):
                    view = OrderDataTableListView()
                    request = SimpleNamespace(user=self.user(role, admin))
                    view.request = request
                    columns = [c['name'] for c in view.get_column_defs(request)]
                    expected = int(admin or role == 'trade')
                    self.assertEqual(columns.count('future_payments'), expected)
                    self.assertEqual(columns.count('past_payments'), expected)

    def test_payment_partials_share_visibility(self):
        for role, admin in [('trade', False), ('sales', True), ('sales', False), ('mac', True)]:
            user = self.user(role, admin)
            request = RequestFactory().get('/order/list/')
            request.user = user
            context = {'can_view_order_payments': can_view_order_payments(user), 'trade_export_fields': EXPORT_FIELDS}
            for template, marker in [
                ('trade_payment_filters', 'id="tradePaymentPanel"'),
                ('trade_payment_summary', 'id="tradePaymentSummary"'),
                ('trade_order_export', 'id="tradeOrderExport"'),
            ]:
                with self.subTest(role=role, admin=admin, template=template):
                    html = render_to_string('order/partial/' + template + '.html', context, request=request)
                    self.assertEqual(html.count(marker), int(admin or role == 'trade'))

    def test_payment_toolbar_has_short_labels_and_inline_calendar(self):
        from html.parser import HTMLParser

        class ToolbarParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.stack = []
                self.calendar_in_toolbar = False
                self.labels = {}
                self.mode = None

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == 'div':
                    if attrs.get('id') == 'tradePaymentDateControls':
                        self.calendar_in_toolbar = 'tp-filter-toolbar' in self.stack
                    self.stack.append(attrs.get('class', '').split(' ')[0])
                if tag == 'button':
                    self.mode = attrs.get('data-payment-mode')

            def handle_data(self, data):
                if self.mode:
                    self.labels[self.mode] = self.labels.get(self.mode, '') + data

            def handle_endtag(self, tag):
                if tag == 'div':
                    self.stack.pop()
                if tag == 'button':
                    self.mode = None

        request = RequestFactory().get('/order/list/')
        request.user = self.user('trade', False)
        html = render_to_string('order/partial/trade_payment_filters.html',
                                {'can_view_order_payments': True}, request=request)
        parser = ToolbarParser()
        parser.feed(html)
        self.assertTrue(parser.calendar_in_toolbar)
        self.assertEqual(set(parser.labels), {'scheduled', 'overdue', 'today', 'due_until', 'date_range'})
        self.assertTrue(all('پرداخت' not in label for label in parser.labels.values()))
        for field in ('tradePaymentStart', 'tradePaymentEnd', 'tradePaymentApply', 'tradePaymentClear'):
            self.assertEqual(html.count('id="' + field + '"'), 1)
