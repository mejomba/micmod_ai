"""Integration contract and security checks for the Sepidar transfer UI."""
from pathlib import Path

from django.test import SimpleTestCase
from django.conf import settings


class PackingSepidarUiTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.page = (Path(settings.BASE_DIR) /
                    'order/templates/order/packing/quick_packing_create.html').read_text()

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
