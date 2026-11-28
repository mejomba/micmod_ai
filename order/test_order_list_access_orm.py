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
