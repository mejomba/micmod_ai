"""Integration contract and security checks for the Sepidar transfer UI."""
import json
from pathlib import Path

from django.test import SimpleTestCase
from django.conf import settings


class PackingSepidarUiTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.page = (Path(settings.BASE_DIR) /
                    'order/templates/order/packing/quick_packing_create.html').read_text(encoding='utf-8')

    def test_sender_is_manual_post_only(self):
        self.assertIn("data-send-url=", self.page)
        self.assertIn("method: 'POST'", self.page)
        self.assertIn("id=\"pk-sepidar-send\"", self.page)
        self.assertIn('can_send_to_sepidar', self.page)

    def test_old_placeholder_is_no_longer_used(self):
        self.assertNotIn('pk-central-receipt-button', self.page)
        self.assertNotIn('packing_central_receipt_not_connected', self.page)

    def test_preview_does_not_render_remote_html(self):
        self.assertIn('td.textContent = value', self.page)

    def test_transfer_column_alignment(self):
        self.assertIn('pk-sepidar-table', self.page)
        self.assertIn('<colgroup>', self.page)
        self.assertIn('table-layout: fixed', self.page)
        self.assertIn('text-align: start !important', self.page)

    def test_transfer_labels_exist_in_all_site_locales(self):
        keys = (
            'packing_received_quantity_help',
            'packing_damaged_quantity_help',
            'packing_sepidar_transfers_title',
            'packing_sepidar_save_first',
            'packing_sepidar_preview',
            'packing_sepidar_send',
            'packing_sepidar_destination',
            'packing_sepidar_quantity',
            'packing_sepidar_status',
            'packing_sepidar_documents',
            'packing_sepidar_type_damaged',
            'packing_sepidar_status_unknown',
            'packing_sepidar_all_success',
        )
        for lang in ('fa', 'en', 'gr', 'it', 'ru', 'sp'):
            with self.subTest(lang=lang):
                path = Path(settings.BASE_DIR) / 'assets' / 'lang' / f'{lang}.json'
                catalog = json.loads(path.read_text(encoding='utf-8'))
                for key in keys:
                    self.assertTrue(catalog.get(key), f'Missing {key} for {lang}')

    def test_dynamic_transfer_rows_are_relocalized_on_language_switch(self):
        self.assertIn('applySepidarTranslations();', self.page)
        self.assertIn('cachedSepidarTransfers', self.page)
        self.assertIn("panel.dir = currentLanguage() === 'fa' ? 'rtl' : 'ltr'", self.page)
