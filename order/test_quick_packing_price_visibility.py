"""Make monetary numbers absent from ordinary users' Packing HTML and AJAX."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase

from order.models import Packing
from order.views import QuickPackingDataTableListView


class QuickPackingPriceVisibilityTests(SimpleTestCase):
    def setUp(self):
        self.view = QuickPackingDataTableListView()
        self.item = Mock(
            effective_sku='SKU', effective_part_number='PN',
            quantity_in_gio=10, available_for_packing=8,
            remaining_quantity_in_order=0, effective_unit_weight=2,
            effective_unit_price=123.45, effective_currency_title='USD',
            order_number='P-10', pk=10,
        )

    def test_ajax_hidden_column_does_not_contain_price_for_normal_user(self):
        self.view.request = SimpleNamespace(user=Mock(is_authenticated=True, is_superuser=False))
        row = {}
        self.view.customize_row(row, self.item)
        self.assertEqual(row['final_price'], '')
        self.assertNotIn('123.45', str(row))

    def test_ajax_superuser_can_receive_price(self):
        self.view.request = SimpleNamespace(user=Mock(is_authenticated=True, is_superuser=True))
        row = {}
        self.view.customize_row(row, self.item)
        self.assertEqual(row['final_price'], 123.45)

    def test_viewers_cannot_query_order_datatable_directly(self):
        with patch.object(Packing, 'user_can_create_workflow', return_value=False):
            with self.assertRaises(PermissionDenied):
                self.view.dispatch(SimpleNamespace(user=Mock()))

    def test_template_gates_all_monetary_values(self):
        text = (
            Path(settings.BASE_DIR) /
            'order/templates/order/packing/quick_packing_create.html'
        ).read_text(encoding='utf-8')
        self.assertIn('{% if can_view_prices %}', text)
        self.assertIn('const canViewPrices = {{ can_view_prices|yesno:"true,false" }};', text)
        self.assertIn('if (canViewPrices) {', text)
        self.assertIn('${canViewPrices ? `', text)
        self.assertNotIn('{% if not is_warehouse_stage or is_superuser %}\n                                                        <div class="pk-stat">\n                                                            <span class="pk-mini-label" data-key="packing_unit_price">', text)

    def test_audit_endpoint_filters_price_fields_on_server(self):
        source = (
            Path(settings.BASE_DIR) / 'order/views.py'
        ).read_text(encoding='utf-8')
        self.assertIn('include_financial=Packing.user_can_view_prices(', source)
