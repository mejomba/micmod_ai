"""Keep Quick Packing labels and live language switching in sync with asset dictionaries."""
import json
import re
from pathlib import Path
from django.conf import settings
from django.test import SimpleTestCase

class QuickPackingTranslationTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        root = Path(settings.BASE_DIR)
        cls.template = (root / 'order/templates/order/packing/quick_packing_create.html').read_text(encoding='utf-8')
        cls.app_js = (root / 'assets/js/app.js').read_text(encoding='utf-8')
        cls.locales = {
            lang: json.loads((root / f'assets/lang/{lang}.json').read_text(encoding='utf-8'))
            for lang in ('fa', 'en')
        }

    def test_packing_data_keys_are_present_in_both_locales(self):
        keys = set(re.findall(r'data-key="([a-zA-Z][a-zA-Z0-9_-]*)"', self.template))
        keys.update(re.findall(r'data-(?:placeholder|title|aria)-key="([a-zA-Z][a-zA-Z0-9_-]*)"', self.template))
        keys.update(re.findall(r"tr\\('([^']+)'", self.template))
        for lang, dictionary in self.locales.items():
            with self.subTest(lang=lang):
                missing = sorted(key for key in keys if key not in dictionary)
                self.assertFalse(missing, f'Missing {lang} Quick Packing translations: {missing}')

    def test_dynamic_rows_and_language_switch_retranslate(self):
        self.assertIn('dason:language-changed', self.app_js)
        self.assertIn("document.addEventListener('dason:language-changed'", self.template)
        self.assertIn('applyDynamicTranslations(row);', self.template)
        self.assertIn('updatePackingTableLanguage();', self.template)
        self.assertIn('data-title-key="packing_remove_row"', self.template)
        self.assertIn("cache: 'no-cache'", self.template)
