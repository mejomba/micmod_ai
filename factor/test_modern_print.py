"""Regression tests for the independent modern invoice and quotation print paths."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.http import HttpResponseBadRequest
from django.template.loader import get_template
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve, reverse

from factor.modern_print import (
    build_document, factor_modern_print, grouped, quotation_modern_print,
)


class ModernPrintContextTests(SimpleTestCase):
    def setUp(self):
        self.currency = SimpleNamespace(title_en="Rial", title="ریال")
        self.buyer = {
            "name": "مشتری نمونه", "phone": "021123456", "address": "تهران",
            "national_number": "-", "postal_code": "-", "is_legal_profile": False,
        }

    def invoice_context(self):
        item = SimpleNamespace(
            goods_code="65817", part_number_show="MCU FMD", price=100000,
            quantity=2, row_price=200000, discount_value=20000, tax=0,
            description="نمونه",
        )
        factor = SimpleNamespace(
            pk=75, q=SimpleNamespace(currency_ref=self.currency, is_official=False),
            currency_ref=self.currency, created_date="1405/08/24-10:30",
            payment=(200000, 10000, 20000, 0, 190000),
            description="ارسال پس از تأیید", is_official=False,
        )
        return {
            "data": factor, "formset": [SimpleNamespace(instance=item)],
            "buyer_info": self.buyer,
            "legal_profile_options": [{"value": "0", "label": "حقوقی", "selected": True}],
            "selected_legal_profile": "0",
        }

    def quotation_context(self):
        item = SimpleNamespace(
            goods_code="44", goods_code_fk=SimpleNamespace(part_number="Resonator"),
            fee_=lambda: 50000, quantity=2, row_price=100000,
            discount_value=0, tax=0, sales_description="ارسال فوری",
            description=None,
        )
        quotation = SimpleNamespace(
            pk=98, currency_ref=self.currency, request_date=date(2026, 11, 15),
            expiration_date=date(2026, 11, 20), payment=(100000, 0, 0, 0, 100000),
            description=None, is_official=False,
        )
        return {"data": quotation, "formset": [SimpleNamespace(instance=item)],
                "buyer_info": self.buyer}

    def test_invoice_uses_legacy_payment_and_converts_rial_to_toman(self):
        with patch("factor.modern_print.qr_image", return_value="data:fake"):
            doc = build_document(self.invoice_context(), True, "https://sample.test/factor", "/legacy")
        self.assertTrue(doc["invoice"])
        self.assertEqual(doc["currency_label"], "تومان")
        self.assertEqual(doc["subtotal"], "20,000")
        self.assertEqual(doc["discount"], "2,000")
        self.assertEqual(doc["additions"], "1,000")
        self.assertEqual(doc["total"], "19,000")
        self.assertEqual(doc["rows"][0]["unit_price"], "10,000")
        self.assertEqual(doc["rows"][0]["before_discount"], "20,000")
        self.assertEqual(doc["rows"][0]["total"], "18,000")
        self.assertEqual(doc["rows"][0]["name"], "MCU FMD")
        self.assertEqual(doc["selected_profile"], "0")
        self.assertEqual(doc["qr_url"], "data:fake")

    def test_quotation_includes_validity_and_its_own_items(self):
        with patch("factor.modern_print.qr_image", return_value=""):
            doc = build_document(self.quotation_context(), False, "https://sample.test/q", "/old")
        self.assertFalse(doc["invoice"])
        self.assertEqual(doc["number"], "P98")
        self.assertEqual(doc["expiry"], date(2026, 11, 20))
        self.assertEqual(doc["rows"][0]["name"], "Resonator")
        self.assertEqual(doc["rows"][0]["total"], "10,000")
        self.assertEqual(doc["rows"][0]["description"], "ارسال فوری")
        self.assertEqual(doc["total"], "10,000")

    def test_non_rial_currency_is_not_divided_by_ten(self):
        ctx = self.quotation_context()
        ctx["data"].currency_ref = SimpleNamespace(title_en="Dollar", title="دلار")
        with patch("factor.modern_print.qr_image", return_value=""):
            doc = build_document(ctx, False, "https://sample.test/q", "/old")
        self.assertEqual(doc["total"], "100,000")
        self.assertEqual(doc["currency_label"], "دلار")

    def test_numeric_output_does_not_expose_float_noise(self):
        self.assertEqual(grouped(1234567.500000001), "1,234,567.5")
        self.assertEqual(grouped(None), "0")

    def test_separate_urls_and_original_urls_remain_available(self):
        new_factor = reverse("factor:factor.print.modern", args=[12])
        old_factor = reverse("factor:factor.print", args=[12])
        new_quote = reverse("micmod_base:quotation.print.modern", args=[15])
        old_quote = reverse("micmod_base:print_customer", args=[15])
        self.assertNotEqual(new_factor, old_factor)
        self.assertNotEqual(new_quote, old_quote)
        self.assertEqual(resolve(new_factor).func, factor_modern_print)
        self.assertEqual(resolve(new_quote).func, quotation_modern_print)

    def test_template_is_print_only_and_preserves_legal_profile_form(self):
        template = get_template("factor/modern_print.html").template.source
        for token in (
            "document.rows", "document.total", "document.currency_label",
            "document.qr_url", "document.buyer.name", "document.seller.name",
            "document.expiry", 'name="legal_profile"', "window.print()",
            "document.legacy_url", "factor/css/modern_print.css",
        ):
            self.assertIn(token, template)

    def test_existing_print_template_still_exists(self):
        self.assertIsNotNone(get_template("factor/factor_print.html"))
        self.assertIsNotNone(get_template("micmod-base/quotation/view-print-raw.html"))


class ModernPrintViewTests(ModernPrintContextTests):
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.user = SimpleNamespace(is_authenticated=True)

    def test_invoice_print_reuses_existing_context_builder(self):
        url = reverse("factor:factor.print.modern", args=[75])
        req = self.factory.get(url, {"legal_profile": "0"})
        req.user = self.user
        with (
            patch("factor.views.print_view", return_value=self.invoice_context()) as old,
            patch("factor.modern_print.qr_image", return_value=""),
            patch("factor.modern_print.render") as render,
        ):
            factor_modern_print(req, id=75)
            old.assert_called_once_with(req, id=75, context_only=True)
            self.assertEqual(render.call_args.args[1], "factor/modern_print.html")
            doc = render.call_args.args[2]["document"]
            self.assertEqual(doc["buyer"]["name"], "مشتری نمونه")

    def test_quotation_print_reuses_existing_context_builder(self):
        url = reverse("micmod_base:quotation.print.modern", args=[98])
        req = self.factory.get(url)
        req.user = self.user
        with (
            patch("micmod_base.views.print_view", return_value=self.quotation_context()) as old,
            patch("factor.modern_print.qr_image", return_value=""),
            patch("factor.modern_print.render") as render,
        ):
            quotation_modern_print(req, id=98)
            old.assert_called_once_with(req, id=98, context_only=True)
            self.assertFalse(render.call_args.args[2]["document"]["invoice"])

    def test_invalid_legal_profile_error_is_preserved(self):
        req = self.factory.get(reverse("factor:factor.print.modern", args=[75]),
                               {"legal_profile": "55"})
        req.user = self.user
        with patch("factor.views.print_view", return_value=HttpResponseBadRequest("نامعتبر")):
            response = factor_modern_print(req, id=75)
        self.assertEqual(response.status_code, 400)
