"""Check the shared-Carton-Number size guard stays on Quick Packing."""
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class InlineCartonSizeUIContractTests(SimpleTestCase):
    def test_page_autofills_and_warns_on_size_mismatch(self):
        template = (Path(settings.BASE_DIR) /
                    'order/templates/order/packing/quick_packing_create.html'
                    ).read_text(encoding='utf-8')
        self.assertIn('function updatePackingCartonSizes()', template)
        self.assertIn('data-carton-number=', template)
        self.assertIn('data-carton-size=', template)
        self.assertIn('pk-carton-size-warning', template)
        self.assertIn('packing_carton_size_mismatch', template)
        self.assertIn('packing_carton_size_missing', template)
        self.assertIn('item.sizeInput.value = size', template)
        self.assertIn("input.setCustomValidity(message)", template)
        self.assertIn("if (!updatePackingCartonSizes())", template)
        self.assertIn("showPackingFeedback('error', packingVolumePhrase(", template)
