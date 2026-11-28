"""Role visibility rules are testable without Django or the portal database."""
from types import SimpleNamespace
from unittest import TestCase

from order.order_list_access import can_view_order_payments, visible_order_filters


class OrderListAccessTests(TestCase):
    def user(self, role, admin=False):
        return SimpleNamespace(base_group=role, is_superuser=admin)

    def keys(self, role, admin=False):
        return [key for key, label in visible_order_filters(self.user(role, admin))]

    def test_trade_filters_unchanged(self):
        self.assertEqual(self.keys('trade'), [
            'all', 'active', 'is_force_order', 'cancel_request',
            'gio_complete', 'gio_incomplete', 'packing_complete', 'packing_incomplete',
            'payment_complete', 'payment_incomplete', 'has_customer_prepaid',
        ])

    def test_sales_filters_unchanged(self):
        self.assertEqual(self.keys('sales'), [
            'all', 'quantity_difference', 'need_sale_admin_confirmation', 'has_error',
            'pcb_item', 'back', 'is_sample', 'is_force_order', 'cancel_denied', 'cancel',
            'has_customer_prepaid', 'duplicated_codes', 'my_orders',
        ])

    def test_superusers_see_same_unique_union_independent_of_role(self):
        expected = set(self.keys('trade')) | set(self.keys('sales')) | {'commitment_date_difference'}
        self.assertEqual(len(expected), 22)
        baseline = self.keys(None, True)
        for role in ('trade', 'sales', 'mac', 'bazar', None):
            with self.subTest(role=role):
                keys = self.keys(role, True)
                self.assertEqual(keys, baseline)
                self.assertEqual(set(keys), expected)
                self.assertEqual(len(keys), len(set(keys)))

    def test_other_roles_do_not_gain_old_filters(self):
        for role in ('mac', 'bazar', None):
            self.assertEqual(self.keys(role), [])

    def test_payment_tools_visibility(self):
        for role in ('trade', 'sales', 'mac', 'bazar', None):
            for admin in (True, False):
                with self.subTest(role=role, admin=admin):
                    self.assertEqual(can_view_order_payments(self.user(role, admin)), admin or role == 'trade')
