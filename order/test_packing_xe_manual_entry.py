"""XE reference links without automated XE scraping or provider credentials."""
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class QuickPackingXeManualReferenceTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.template = (
            Path(settings.BASE_DIR) /
            'order/templates/order/packing/quick_packing_create.html'
        ).read_text(encoding='utf-8')
        cls.view_source = (
            Path(settings.BASE_DIR) / 'order/views.py'
        ).read_text(encoding='utf-8')
        cls.settings_source = (
            Path(settings.BASE_DIR) / '_keenthemes/settings.py'
        ).read_text(encoding='utf-8')

    def test_direct_pair_link_has_fixed_public_xe_converter_domain(self):
        html = self.template
        self.assertIn(
            "'https://www.xe.com/currencyconverter/convert/?Amount=1&From='",
            html,
        )
        self.assertIn("encodeURIComponent(from)", html)
        self.assertIn("encodeURIComponent(to)", html)
        self.assertIn("const from = fxXeCode(sourceId)", html)
        self.assertIn("const to = fxXeCode(targetId)", html)
        self.assertIn("const normalized = code === 'RMB' ? 'CNY' : code", html)
        self.assertIn("return /^[A-Z]{3}$/.test(normalized)", html)
        self.assertIn("link.target = '_blank'", html)
        self.assertIn("link.rel = 'noopener noreferrer'", html)

    def test_rate_remains_manually_editable_and_is_saved_normally(self):
        html = self.template
        self.assertIn("input.type = 'number'", html)
        self.assertIn("input.addEventListener('input', () => {", html)
        self.assertIn("fxRates[source.id] = input.value.trim()", html)
        self.assertIn("fxSyncHidden()", html)
        self.assertIn("fxUpdateConvertedTotal(totals)", html)
        self.assertIn("fxXePage(source.id, target)", html)
        self.assertIn("packing_fx_xe_open", html)
        self.assertIn("packing_fx_xe_manual_help", html)
        self.assertIn("packing_fx_xe_unsupported", html)
        self.assertNotIn("name=\"converted_total\"", html)

    def test_no_automatic_read_of_xe_site_or_paid_api_remains(self):
        html = self.template
        self.assertNotIn('fxFetchXeRates', html)
        self.assertNotIn('fxXeQuotes', html)
        self.assertNotIn('fxXeFetchButton', html)
        self.assertNotIn('data-xe-configured=', html)
        self.assertNotIn('xe_rates:', html)
        self.assertNotIn("request.GET.get('xe_rates')", self.view_source)
        self.assertNotIn("from .xe_currency_rates", self.view_source)
        self.assertNotIn("XE_CURRENCY_API_KEY = ", self.settings_source)

    def test_financial_summary_is_still_collapsible_and_multilingual(self):
        html = self.template
        self.assertIn('<details class="pk-fx-fold"', html)
        self.assertIn('id="packing-fx-collapsed-total"', html)
        self.assertIn('id="packing-fx-header-total"', html)
        self.assertIn('id="packing-fx-converted-total"', html)
        self.assertIn('id="pk-fx-rate-rows"', html)
        self.assertGreaterEqual(html.count('packing_fx_xe_open:'), 2)
        self.assertGreaterEqual(html.count('packing_fx_xe_manual_help:'), 2)
        self.assertIn('مشاهده نرخ در XE', html)
        self.assertIn('View rate on XE', html)

    def test_manual_references_still_hide_financial_data_from_unauthorized_users(self):
        html = self.template
        self.assertIn('{% if can_view_prices %}', html[:html.index('<section id="pk-currency-fx"')])
        self.assertIn('{% if fx_can_edit %}', html)
        self.assertIn('fxEditable', html)
