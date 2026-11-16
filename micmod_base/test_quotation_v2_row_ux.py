"""Quotation v2 row redesign: prevent regression in operational formset hooks.

These are structural tests. They do not replace end-to-end Selenium/Playwright
tests of Select2, multi-stage workflow or Sepidar.
"""
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.template.loader import get_template
from django.urls import reverse

from micmod_base.forms import QuotationItemForm2
from micmod_base.quotation_v2_full_forms import QuotationItemFormV2


class QuotationV2RowExperienceTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.row = get_template(
            "micmod-base/quotation/v2/item_full.html"
        ).template.source
        cls.page = get_template(
            "micmod-base/quotation/v2/full.html"
        ).template.source

    def test_row_is_new_component_not_old_column_layout(self):
        for selector in (
            "qv3-item", "qv3-row-header", "qv3-workspace",
            "qv3-workspace-product", "qv3-workspace-finance",
            "qv3-detail-grid", "qv3-panel-inquiry",
            "qv3-panel-product", "qv3-panel-delivery",
            "qv3-panel-notes", "qv3-financial-breakdown",
            "qv3-row-footer", "qv3-details-toggle",
        ):
            with self.subTest(selector=selector):
                self.assertIn(selector, self.row)
        self.assertNotIn("col-lg-2 rounded", self.row)
        self.assertNotIn("ribbon ribbon-start", self.row)

    def test_legacy_formset_and_inquiry_hooks_are_preserved(self):
        for selector in (
            "card item", "row-counter question-btn active-form",
            'class="answer qv3-row-content"',
            'class="counter qv3-sequence"',
            'name="code_h"', 'name="name_h"',
            'name="quantity_h"', 'name="unit-price_h"',
            'name="total-price_h"',
            "nested_manage.management_form", "nested.hidden_fields",
            "form_s.hidden_fields", "form_s.DELETE",
            "form_s.price_json",
            "goods_code qv3-select2", "goods_code_alt",
            'name="-goods_name_lbl"', 'name="-goods_name_alt_lbl"',
            'name="box-alt-goods"', 'id="moq"', 'id="moq_box"',
            'id="moq_main_box"', 'id="all_price_count"',
            'id="id_price_method_container"',
            'id="id_display_price_container"',
            'id="customer-last-sales"',
            'id="id_goods_last_price"', 'id="id_goods_q_last_price"',
            'id="lead_time_text"',
            'id="selected_price_code_data"',
            "selected_price_code",
            'name="MAC"', 'name="tax_value"',
            'name="discount_value"', 'name="-total_price"',
            "sepidar_stock_info_result",
            "new-inquiry-result-", "changelog-btn",
            "handel-drop", "comment-form-group__",
        ):
            with self.subTest(selector=selector):
                self.assertIn(selector, self.row)

    def test_complete_quotationitem_fields_remain_available(self):
        for field in (
            "quantity", "price_target",
            "customer_goods_code", "customer_goods_name",
            "need_local_price_inquiry", "local_price_inquiry_done",
            "need_foreign_price_inquiry", "foreign_price_inquiry_done",
            "bazar_price_code", "trade_price_code",
            "final_price", "discount_per_item",
            "description", "sales_description",
            "item_in_china", "supply_date", "supply_status",
            "lead_time", "assigned_trade_user", "assigned_trade_user2",
            "task_start", "task_start2",
            "has_delay", "delay_reason", "delay_time",
        ):
            with self.subTest(field=field):
                self.assertIn("form_s." + field, self.row)
        self.assertIn("nested.stock_amount", self.row)
        self.assertIn("nested.stock_amount_res", self.row)
        self.assertIn("nested.description", self.row)
        self.assertTrue(issubclass(QuotationItemFormV2, QuotationItemForm2))

    def test_role_based_price_visibility_remains(self):
        original_guard = 'request.user|has_one_group:"sales_user, sales_admin"'
        self.assertIn(original_guard, self.row)
        self.assertLess(
            self.row.index(original_guard),
            self.row.index('id="id_display_price_container"'),
        )
        self.assertIn('request.user|has_permission:"micmod_base.discount_per_item"', self.row)
        self.assertIn('request.user|has_one_group:"trade_user, trade_admin"', self.row)

    def test_row_pricing_keeps_previous_form_fields_for_later_phase(self):
        for field in (
            "form_s.final_price",
            "form_s.discount_per_item",
            "form_s.v2_manager_price",
            "data-qv2-source-select",
            "data-qv2-reference-value",
            "data-previous_price_method",
            "data-qv2-system-price",
            "data-qv2-system-method",
        ):
            with self.subTest(field=field):
                self.assertIn(field, self.row)

    def test_full_page_uses_new_assets_without_affecting_header(self):
        self.assertIn("quotation_v2_full.css", self.page)
        self.assertIn("quotation_v2_rows.css", self.page)
        self.assertIn("quotation_v2_full.js", self.page)
        self.assertIn("quotation_v2_rows.js", self.page)
        self.assertLess(
            self.page.index("quotation_v2_full.css"),
            self.page.index("quotation_v2_rows.css"),
        )
        self.assertIn("qv2-top", self.page)
        self.assertIn("workflow/flow.html", self.page)
        self.assertIn("item_full.html", self.page)
        self.assertIn("formset.empty_form", self.page)
        self.assertEqual(
            reverse("micmod_base:quotation.v2", kwargs={"pk": 16682}),
            "/micmod_base/quotation/v2/16682/",
        )

    def test_ui_js_does_not_redefine_financial_or_workflow_functions(self):
        js = (
            Path(settings.BASE_DIR)
            / "micmod_base/static/micmod_base/js/quotation_v2_rows.js"
        ).read_text(encoding="utf-8")
        self.assertIn("MutationObserver", js)
        self.assertIn("select2:select", js)
        self.assertIn("qv3-marked-delete", js)
        self.assertIn("normalizeAddedRows", js)
        self.assertIn('hostObserver.observe(host, { childList: true })', js)
        self.assertIn('window.addEventListener("load"', js)
        self.assertNotIn("window.calculate_price =", js)
        self.assertNotIn("window.set_price_data =", js)
        self.assertNotIn("apply_materialized_values", js)
        self.assertNotIn("workflow_form", js)
