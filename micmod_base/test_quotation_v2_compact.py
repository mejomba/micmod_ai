"""Regression coverage for v2 placeholder saving, dropdown width and dense UI."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase
from django.template.loader import get_template

from micmod_base.forms import BaseQIFormset
from micmod_base.quotation_v2_full_forms import (
    BaseQIFormsetV2,
    QuotationItemFormV2,
    is_unused_quotation_extra,
)


class QuotationV2EmptyExtraRowTests(SimpleTestCase):
    @staticmethod
    def fake_form(pk=None, prefix="quotation-1", data=None):
        return SimpleNamespace(
            instance=SimpleNamespace(pk=pk),
            is_bound=True,
            prefix=prefix,
            data=data or {},
            nested=SimpleNamespace(
                prefix="qir-" + prefix + "-quotation_item_rel",
            ),
        )

    def test_empty_last_extra_skips_auto_filled_financial_and_index_fields(self):
        form = self.fake_form(data={
            "quotation-1-index": "1",
            "quotation-1-discount_per_item": "0",
            "quotation-1-price_method": "sales_admin",
            "quotation-1-final_price": "0",
            "quotation-1-need_local_price_inquiry": "false",
            "quotation-1-need_foreign_price_inquiry": "false",
            "qir-quotation-1-quotation_item_rel-TOTAL_FORMS": "1",
            "qir-quotation-1-quotation_item_rel-0-price": "0",
        })
        self.assertTrue(is_unused_quotation_extra(form))

    def test_entered_sku_quantity_or_note_must_not_be_ignored(self):
        for payload in (
            {"quotation-1-goods_code": "SKU-1"},
            {"quotation-1-quantity": "3"},
            {"quotation-1-description": "requested part"},
            {"quotation-1-need_local_price_inquiry": "on"},
            {"qir-quotation-1-quotation_item_rel-0-description": "note"},
            {"qir-quotation-1-quotation_item_rel-0-price": "5"},
        ):
            with self.subTest(payload=payload):
                self.assertFalse(is_unused_quotation_extra(
                    self.fake_form(data=payload)
                ))

    def test_existing_rows_never_skipped_even_when_all_values_blank(self):
        self.assertFalse(is_unused_quotation_extra(
            self.fake_form(pk=998, data={})
        ))
        self.assertFalse(is_unused_quotation_extra(
            self.fake_form(pk=998, data={"quotation-1-DELETE": "on"})
        ))

    def test_bound_blank_form_does_not_call_model_form_has_changed(self):
        instance = SimpleNamespace(pk=None)
        form = object.__new__(QuotationItemFormV2)
        form.instance = instance
        form.is_bound = True
        form.prefix = "quotation-1"
        form.data = {"quotation-1-index": "10"}
        form.nested = SimpleNamespace(
            prefix="qir-quotation-1-quotation_item_rel"
        )
        self.assertFalse(QuotationItemFormV2.has_changed(form))

    def test_save_excludes_only_placeholder_and_restores_formset_forms(self):
        original = self.fake_form(pk=14, prefix="quotation-0")
        blank = self.fake_form(prefix="quotation-1", data={
            "quotation-1-index": "1",
        })
        new = self.fake_form(prefix="quotation-2", data={
            "quotation-2-goods_code": "SKU-A",
            "quotation-2-quantity": "5",
        })
        fs = object.__new__(BaseQIFormsetV2)
        fs.forms = [original, blank, new]
        selected = []

        def base_save(*args, **kwargs):
            selected.extend(fs.forms)
            return ["old", "new"]

        with patch.object(BaseQIFormset, "save", side_effect=base_save):
            result = BaseQIFormsetV2.save(fs, request=SimpleNamespace())
        self.assertEqual(result, ["old", "new"])
        self.assertEqual(selected, [original, new])
        self.assertEqual(fs.forms, [original, blank, new])

    def test_formset_nested_validator_skips_unused_form(self):
        fs = object.__new__(BaseQIFormsetV2)
        blank = self.fake_form(data={"quotation-1-index": "1"})
        checked = self.fake_form(prefix="quotation-0", data={
            "quotation-0-goods_code": "SKU-99",
        })
        calls = []
        blank.nested.is_valid = lambda: calls.append("blank") or False
        checked.nested.is_valid = lambda: calls.append("real") or True
        fs.forms = [checked, blank]
        fs.is_bound = True

        from django.forms.models import BaseInlineFormSet
        with patch.object(BaseInlineFormSet, "is_valid", return_value=True):
            result = BaseQIFormsetV2.is_valid(fs)
        self.assertTrue(result)
        self.assertEqual(calls, ["real"])


class QuotationV2DenseControlsTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        root = Path(settings.BASE_DIR) / "micmod_base/static/micmod_base"
        cls.html = get_template(
            "micmod-base/quotation/v2/full.html"
        ).template.source
        cls.js = (root / "js/quotation_v2_rows.js").read_text(encoding="utf-8")
        cls.css = (root / "css/quotation_v2_dense.css").read_text(encoding="utf-8")

    def test_product_dropdown_is_viewport_wide_right_aligned(self):
        self.assertIn("quotation_v2_dense.css", self.html)
        self.assertLess(
            self.html.index("quotation_v2_rows.css"),
            self.html.index("quotation_v2_dense.css"),
        )
        for fragment in (
            "qv5-wide-goods-dropdown", "position:fixed!important",
            "right:var(--qv5-goods-right)!important",
            "width:var(--qv5-goods-width)!important", "max-width:90vw",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.css)
        self.assertIn("viewportWidth * 0.9", self.js)
        self.assertIn("viewportWidth - rect.right", self.js)
        self.assertIn('document.addEventListener("scroll", schedulePosition, true)', self.js)
        self.assertIn(".qv3-product-selector .goods_code", self.js)

    def test_dense_open_form_is_restructured_not_just_smaller_fonts(self):
        for fragment in (
            ".qv3-workspace-product{", "grid-template-columns:repeat(12,minmax(0,1fr))",
            ".qv3-product-selection,", "display:contents!important",
            ".qv3-stock-quick{", ".qv3-financial-breakdown{",
            "grid-template-columns:repeat(4,minmax(0,1fr))!important",
            ".qv3-detail-grid{",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.css)

    def test_trailing_blank_rows_trimmed_without_reindexing_in_middle(self):
        self.assertIn("function isEmptyExtraRow(row)", self.js)
        self.assertIn("function trimUnusedExtraRowsBeforeSubmit()", self.js)
        self.assertIn("count > minimum", self.js)
        self.assertIn("Math.max(1, initialCount)", self.js)
        self.assertIn('el.dataset.qv3Row === prefix + "-" + (count - 1)', self.js)
        self.assertIn("total.value = String(count)", self.js)
        self.assertIn("trimUnusedExtraRowsBeforeSubmit();", self.js)
