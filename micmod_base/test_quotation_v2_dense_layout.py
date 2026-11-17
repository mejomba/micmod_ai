"""Regression checks for the dense quotation-v2 *visual* layout.

The browser must still be tested manually for actual geometry, Select2 position
and drag/drop; these tests guard source-level layout and business-hook contracts.
"""
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class QuotationV2DenseLayoutTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        root = Path(settings.BASE_DIR) / "micmod_base"
        cls.item = (
            root / "templates/micmod-base/quotation/v2/item_full.html"
        ).read_text(encoding="utf-8")
        cls.page = (
            root / "templates/micmod-base/quotation/v2/full.html"
        ).read_text(encoding="utf-8")
        cls.css = (
            root / "static/micmod_base/css/quotation_v2_dense.css"
        ).read_text(encoding="utf-8")

    def test_dense_stylesheet_remains_last_in_row_cascade(self):
        row_css = self.page.index("quotation_v2_rows.css")
        dense_css = self.page.index("quotation_v2_dense.css")
        self.assertLess(row_css, dense_css)

    def test_pricing_sources_share_one_container_without_moving_totals(self):
        start = self.item.index('<div class="qv6-finance-tools">')
        end = self.item.index('<div class="qv3-financial-breakdown"', start)
        region = self.item[start:end]
        self.assertEqual(self.item.count('class="qv6-finance-tools"'), 1)
        for hook in (
            'class="qv3-v2-price-tools"',
            'data-qv2-source-select',
            'class="qv3-price-all-sources"',
            'class="qv3-panel qv3-panel-inquiry qv3-price-inquiry"',
            'id="id_display_price_container"',
            'name="selected_price_code"',
            'id="new-inquiry-result-',
        ):
            with self.subTest(hook=hook):
                self.assertIn(hook, region)
        self.assertIn("grid-template-columns: minmax(0, 1.1fr) minmax(0, .9fr)", self.css)

    def test_prices_can_fit_three_editors_on_a_desktop_line(self):
        for name in ("qv3-price-method", "qv3-price-inputs", "qv3-price-target"):
            self.assertIn('class="' + name + '"', self.item)
        self.assertIn(
            "grid-template-columns: minmax(0, .95fr) minmax(0, 1.8fr) minmax(0, 1fr)",
            self.css,
        )
        self.assertIn("grid-column: auto !important;", self.css)

    def test_item_has_horizontal_stock_actions_and_optional_details(self):
        self.assertIn('class="qv3-stock-quick"', self.item)
        self.assertIn('class="qv3-product-extra"', self.item)
        self.assertIn("get_sepidar_stock_info(event)", self.item)
        self.assertIn("item_order_quantity(event)", self.item)
        self.assertIn(".qv3-inventory-response:empty", self.css)
        self.assertIn(".qv3-product-extra[open]", self.css)
        self.assertIn("grid-column: span 6;", self.css)

    def test_dense_rows_have_responsive_single_line_headers(self):
        self.assertIn("@media (min-width: 1060px)", self.css)
        self.assertIn("min-height: 53px !important", self.css)
        self.assertIn("grid-template-rows: minmax(0,1fr) !important", self.css)
        self.assertIn("@media (max-width: 760px)", self.css)
        self.assertIn("@media (max-width: 510px)", self.css)
        self.assertIn("grid-template-columns: minmax(0, 1fr) !important", self.css)
        self.assertIn(".qv3-detail-grid > .qv3-panel[open]", self.css)

    def test_legacy_formset_and_price_behaviour_still_embedded(self):
        for hook in (
            'class="answer qv3-row-content"',
            'row-counter question-btn active-form',
            'nested_manage.management_form',
            'form_s.hidden_fields',
            'form_s.DELETE',
            'id="id_price_method_container"',
            'form_s.final_price',
            'form_s.discount_per_item',
            'form_s.price_target',
            'form_s.v2_manager_price',
            'class="select2 goods_code qv3-select2"',
            'class="select2 selected_price_code"',
            'handel-drop',
        ):
            with self.subTest(hook=hook):
                self.assertIn(hook, self.item)
