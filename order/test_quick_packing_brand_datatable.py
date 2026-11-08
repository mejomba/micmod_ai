"""Regression: ajax_datatable defers non-column fields on the page queryset."""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from order.views import QuickPackingDataTableListView


class QuickPackingBrandDatatableTests(SimpleTestCase):
    def test_brand_title_annotation_works_with_deferred_columns(self):
        view = QuickPackingDataTableListView()
        queryset = view.get_initial_queryset().only(
            'id', 'order_number', 'created_date',
        )
        # Query compilation (no DB access) reproduces the prior FieldError:
        # Order.brand cannot be deferred and select_related simultaneously.
        sql = str(queryset.query)
        self.assertIn('brand', sql.lower())
        self.assertIn('effective_brand_title', queryset.query.annotations)
        self.assertFalse(queryset.query.select_related)

    def test_brand_title_uses_annotation_without_loading_brand_relation(self):
        view = QuickPackingDataTableListView()
        view.request = SimpleNamespace(user=SimpleNamespace())
        obj = SimpleNamespace(
            effective_sku='SKU1', effective_part_number='Part',
            quantity_in_gio=4, available_for_packing=3,
            remaining_quantity_in_order=1, effective_unit_weight=0.5,
            effective_brand_title='<Example Brand>',
            effective_unit_price=2, effective_currency_title='USD',
            order_number='ORD-1', pk=1,
        )
        row = {}
        with patch('order.views.Packing.user_can_view_prices', return_value=True):
            view.customize_row(row, obj)
        self.assertEqual(row['brand_title'], '&lt;Example Brand&gt;')
