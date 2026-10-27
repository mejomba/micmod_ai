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

    def test_header_grid_does_not_render_in_warehouse(self):
        self.assertIn('{% if not is_warehouse_stage %}', self.html)
        self.assertIn('<div class="packing-meta-grid">', self.html)
        self.assertIn('iter_packing_document_groups', self.html)

    def test_warehouse_editor_has_only_received_and_ruined_fields(self):
        markup = self.html.split('<div class="pk-row-editor-fields">', 1)[1]
        warehouse = markup.split('{% else %}', 1)[0]
        self.assertIn('name="existing-{{ packing_item.pk }}-arrived_quantity"', warehouse)
        self.assertIn('name="existing-{{ packing_item.pk }}-ruined_quantity"', warehouse)
        self.assertNotIn('name="existing-{{ packing_item.pk }}-quantity"', warehouse)
        self.assertIn('packing_item.arrived_quantity|default_if_none:packing_item.quantity', warehouse)

    def test_double_click_protection_covers_save_and_workflow(self):
        self.assertIn('let packingRequestPending = false;', self.html)
        self.assertIn('if (packingRequestPending) return;', self.html)
        self.assertIn('setPackingRequestPending(true);', self.html)
        self.assertIn('setPackingRequestPending(false);', self.html)
