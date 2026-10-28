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
        keys.update(re.findall(r"tr\('([^']+)'", self.template))
        for lang, dictionary in self.locales.items():
            with self.subTest(lang=lang):
                missing = sorted(key for key in keys if key not in dictionary)
                self.assertFalse(missing, f'Missing {lang} Quick Packing translations: {missing}')

    def test_workflow_stages_translate_on_language_click_without_refresh(self):
        stage_labels = {
            'fa': ["پیش‌نویس","تحویل شرکت حمل","حمل","قبض انبار","تحویل اسناد","اظهار","ضمانتنامه","ترخیص","انبار","اتمام کار"],
            'en': ["Draft","Handover to Carrier","In Transit","Warehouse Receipt","Document Handover","Customs Declaration","Guarantee Letter","Customs Clearance","Warehouse","Completed"],
        }
        for lang, names in stage_labels.items():
            with self.subTest(lang=lang):
                for index, name in enumerate(names):
                    self.assertEqual(self.locales[lang][f'packing_workflow_stage_{index}'], name)
        self.assertIn('data-key="packing_workflow_stage_{{ forloop.counter0 }}"', self.template)
        self.assertIn("const packingStageKeys = Object.fromEntries(", self.template)
        self.assertIn("applyWorkflowStageLabels(root);", self.template)
        self.assertIn("applyWorkflowStageLabels(document, lang, false);", self.template)
        self.assertIn("document.addEventListener('click', function (event)", self.template)
        self.assertIn("packingTranslationLanguage = fallbackLang;", self.template)

    def test_dynamic_rows_and_language_switch_retranslate(self):
        self.assertIn('dason:language-changed', self.app_js)
        self.assertIn("document.addEventListener('dason:language-changed'", self.template)
        self.assertIn('applyDynamicTranslations(row);', self.template)
        self.assertIn('updatePackingTableLanguage();', self.template)
        self.assertIn('data-title-key="packing_remove_row"', self.template)
        self.assertIn("cache: 'no-cache'", self.template)
