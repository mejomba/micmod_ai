"""Warehouse Packing presentation, input defaults, and submission lock regressions."""
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class QuickPackingWarehouseUiTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.html = (
            Path(settings.BASE_DIR) / 'order/templates/order/packing/quick_packing_create.html'
        ).read_text(encoding='utf-8')

    def test_warehouse_header_shows_six_readonly_fields(self):
        self.assertIn('<div class="packing-meta-grid pk-warehouse-meta-grid"', self.html)
        warehouse_header = self.html.split('class="packing-meta-grid pk-warehouse-meta-grid"', 1)[1]
        warehouse_header = warehouse_header.split('{% else %}', 1)[0]
        fields = [
            'packing_number_label', 'packing_shipment_type_label',
            'packing_bl_number_label', 'packing_bl_date',
            'packing_transportation_company', 'packing_header_description_label',
        ]
        for key in fields:
            with self.subTest(key=key):
                self.assertIn('data-key="' + key + '"', warehouse_header)
        self.assertEqual(warehouse_header.count('class="pk-warehouse-meta-field'), 6)
        self.assertNotIn('<input', warehouse_header)
        self.assertNotIn('<textarea', warehouse_header)
        self.assertNotIn('<select', warehouse_header)
        self.assertIn('iter_packing_document_groups', self.html)

    def test_warehouse_dates_default_to_jalali_and_can_be_switched(self):
        self.assertIn("const initialCalendar = isWarehouseStage ? 'jalali' : savedCalendar;", self.html)
        self.assertIn('data-packing-readonly-date="{{ packing_object.bl_date|date:', self.html)
        self.assertIn("fa-IR-u-ca-persian-nu-latn", self.html)
        self.assertIn('updatePackingReadonlyHeaderDates(root);', self.html)
        self.assertIn('updatePackingReadonlyHeaderDates(document);', self.html)

    def test_warehouse_editor_has_only_received_and_ruined_fields(self):
        markup = self.html.split('<div class="pk-row-editor-fields">', 1)[1]
        warehouse = markup.split('{% else %}', 1)[0]
        self.assertIn('name="existing-{{ packing_item.pk }}-wh_receipt_quantity"', warehouse)
        self.assertIn('name="existing-{{ packing_item.pk }}-ruined_quantity"', warehouse)
        self.assertNotIn('name="existing-{{ packing_item.pk }}-quantity"', warehouse)
        self.assertIn('packing_item.wh_receipt_quantity|default_if_none:packing_item.quantity', warehouse)

    def test_double_click_protection_covers_save_and_workflow(self):
        self.assertIn('let packingRequestPending = false;', self.html)
        self.assertIn('if (packingRequestPending) return;', self.html)
        self.assertIn('setPackingRequestPending(true);', self.html)
        self.assertIn('setPackingRequestPending(false);', self.html)

    def test_warehouse_header_is_immutable_even_if_posted(self):
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        from order.views import QuickPackingView

        view = QuickPackingView()
        view.request = SimpleNamespace(user=Mock())
        view._workflow_constraint = Mock(return_value={
            'form_state': 8,
            'wf_access': True,
            'form_constraint': [{} for _ in range(10)],
        })
        view._is_warehouse_stage = Mock(return_value=True)
        with patch.object(view, 'form_class') as form_class:
            view._build_form(
                packing_obj=Mock(),
                data={
                    'packing_number': 'TAMPERED',
                    'shipment_type': 'air',
                    'bl_number': 'TAMPERED',
                    'bl_date': '2026-10-27',
                    'transportation_company': 'TAMPERED',
                    'description': 'TAMPERED',
                },
            )

        passed = form_class.call_args.kwargs
        for name in (
            'packing_number', 'shipment_type', 'bl_number', 'bl_date',
            'transportation_company', 'description',
            'currency', 'origin', 'destination',
        ):
            with self.subTest(name=name):
                self.assertNotIn(name, passed['allowed_fields'])
                self.assertNotIn(name, passed['only_show'])
        self.assertIn('file_1', passed['allowed_fields'])

