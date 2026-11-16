"""Regression tests: quotation legacy remains unchanged; v2 is opt-in per row."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from django.template.loader import get_template
from django.urls import resolve, reverse

from factor.models import FactorItem
from micmod_base.models import QuotationItem
from micmod_base.pricing_v2 import (
    PricingError, calculate_pricing_v2, apply_materialized_values,
)
from micmod_base.quotation_v2_views import (
    _select_reference, _save_price, quotation_v2_editor,
)


def quote(self_discount=10, is_official=False):
    return SimpleNamespace(
        self_discount=self_discount, is_official=is_official,
        official_value=0, currency_ref_id=1,
    )


def fake_row(version=2, approved=None):
    return SimpleNamespace(
        pricing_version=version,
        quotation=quote(),
        quantity=2,
        price_json=[
            {"unique_title": "express", "value": 1000, "iqref": 13, "title": "سریع"},
            {"unique_title": "goods_last_price", "value": 900},
            {"unique_title": "air", "value": 1100, "iqref": 14, "title": "هوایی"},
        ],
        system_price=None, system_price_method=None,
        system_price_snapshot=None,
        price_method="sales_admin" if approved is not None else "express",
        final_price=approved if approved is not None else 1000,
        manager_approved_price=None, discount_per_item=50,
        effective_unit_price=None, calculated_row_discount=None,
        manager_price_difference=None, manager_positive_difference=None,
    )


class PricingV2Calculations(SimpleTestCase):
    def test_regular_row_has_unit_and_document_discount(self):
        r = calculate_pricing_v2(
            system_price=1000, quantity=2, discount_per_item=50,
            self_discount=10,
        )
        self.assertEqual(r.reference_price, Decimal("1000"))
        self.assertEqual(r.gross, Decimal("2000"))
        self.assertEqual(r.unit_discount, Decimal("100"))
        self.assertEqual(r.document_discount, Decimal("200"))
        self.assertEqual(r.row_discount, Decimal("300"))
        self.assertEqual(r.effective_unit_price, Decimal("850"))
        self.assertEqual(r.final_total, Decimal("1700"))
        self.assertEqual(r.positive_sales_difference_total, Decimal("0"))

    def test_manager_below_system_is_discount_not_price_reference_mutation(self):
        r = calculate_pricing_v2(
            system_price=1000, manager_approved_price=800,
            quantity=3, discount_per_item=300, self_discount=25,
        )
        self.assertEqual(r.reference_price, 1000)
        self.assertEqual(r.customer_unit_price, 1000)
        self.assertEqual(r.unit_discount, 600)
        self.assertEqual(r.document_discount, 0)
        self.assertEqual(r.effective_unit_price, 800)
        self.assertEqual(r.final_total, 2400)
        self.assertEqual(r.positive_sales_difference_total, 0)

    def test_manager_above_system_is_customer_base_and_positive_bi_delta(self):
        r = calculate_pricing_v2(
            system_price=1000, manager_approved_price=1200,
            quantity=4, discount_per_item=400, self_discount=20,
        )
        self.assertEqual(r.reference_price, 1000)
        self.assertEqual(r.customer_unit_price, 1200)
        self.assertEqual(r.unit_discount, 0)
        self.assertEqual(r.document_discount, 0)
        self.assertEqual(r.final_total, 4800)
        self.assertEqual(r.positive_sales_difference_unit, 200)
        self.assertEqual(r.positive_sales_difference_total, 800)
        self.assertEqual(r.as_bi_fields()["manager_price_difference"], Decimal("200.0000"))
        self.assertEqual(r.as_bi_fields()["manager_positive_difference"], Decimal("800.0000"))

    def test_manager_equal_system_has_zero_delta_and_zero_discount(self):
        r = calculate_pricing_v2(
            system_price=1000, manager_approved_price=1000,
            quantity=2, discount_per_item=100, self_discount=15,
        )
        self.assertEqual(r.final_total, 2000)
        self.assertEqual(r.row_discount, 0)
        self.assertEqual(r.positive_sales_difference_total, 0)

    def test_official_tax_adjustment_is_distinct_from_commercial_discount(self):
        r = calculate_pricing_v2(
            system_price=1200, manager_approved_price=1000,
            quantity=2, self_discount=50, is_official=True,
            tax_rate=10, official_value=5,
        )
        self.assertEqual(r.document_discount, 0)
        self.assertEqual(r.unit_discount, 400)
        self.assertEqual(r.official_adjustment.quantize(Decimal(".0001")), Decimal("90.9091"))
        self.assertEqual(r.final_total.quantize(Decimal(".01")), Decimal("2100.00"))

    def test_invalid_values_cannot_create_fake_financial_data(self):
        for kwargs in [
            {"system_price": None},
            {"system_price": 0},
            {"system_price": "NaN"},
            {"system_price": 100, "quantity": -1},
            {"system_price": 100, "self_discount": 101},
            {"system_price": 100, "discount_per_item": 101},
            {"system_price": 100, "manager_approved_price": -5},
            {"system_price": 100, "discount_per_item": 90, "self_discount": 20},
        ]:
            with self.subTest(kwargs=kwargs), self.assertRaises(PricingError):
                calculate_pricing_v2(**kwargs)

    def test_materialized_fields_match_calculator_without_changing_reference(self):
        row = fake_row()
        row.system_price = Decimal("1000")
        row.manager_approved_price = Decimal("1200")
        before = row.system_price
        result = apply_materialized_values(row)
        self.assertEqual(row.system_price, before)
        self.assertEqual(row.final_price, 1200)
        self.assertEqual(row.manager_positive_difference, Decimal("400.0000"))
        self.assertEqual(row.calculated_row_discount, Decimal("0.0000"))
        self.assertEqual(row.effective_unit_price, Decimal("1200.0000"))
        self.assertEqual(result.final_total, 2400)


class PricingV2Compatibility(SimpleTestCase):
    def test_existing_pricing_version_default_is_legacy(self):
        field = QuotationItem._meta.get_field("pricing_version")
        self.assertEqual(field.get_default(), 1)
        self.assertTrue(QuotationItem._meta.get_field("manager_approved_price").null)
        self.assertTrue(QuotationItem._meta.get_field("system_price").null)

    def test_only_server_persisted_price_options_can_be_selected(self):
        row = fake_row()
        price, method, snapshot = _select_reference(row, {"system_price_index": "0"})
        self.assertEqual(price, 1000)
        self.assertEqual(method, "express")
        self.assertEqual(snapshot["iqref"], 13)
        self.assertEqual(snapshot["currency_id"], 1)
        for chosen in ("1", "3000", "garbage"):
            with self.subTest(chosen=chosen), self.assertRaises(PricingError):
                _select_reference(row, {"system_price_index": chosen})

    def test_keep_reference_never_overwrites_selected_system_price(self):
        row = fake_row()
        row.system_price = Decimal("875.5")
        row.system_price_method = "air"
        row.system_price_snapshot = {"currency_id": 1, "unique_title": "air"}
        price, method, _ = _select_reference(row, {"system_price_index": "keep"})
        self.assertEqual(price, Decimal("875.5"))
        self.assertEqual(method, "air")

    def test_v1_cannot_be_silently_upgraded(self):
        row = fake_row(version=1, approved=700)
        with self.assertRaises(PricingError):
            _save_price(row, {"system_price_index": "0", "manager_approved": "1"}, upgrade=False)
        self.assertEqual(row.pricing_version, 1)
        self.assertEqual(row.final_price, 700)

    def test_explicit_upgrade_moves_historical_manager_to_new_field(self):
        row = fake_row(version=1, approved=700)
        result = _save_price(
            row,
            {"system_price_index": "0", "manager_approved": "1", "discount_per_item": "50"},
            upgrade=True,
        )
        self.assertEqual(row.pricing_version, 2)
        self.assertEqual(row.manager_approved_price, 700)
        self.assertEqual(row.system_price, 1000)
        self.assertEqual(row.discount_per_item, 0)
        self.assertEqual(row.final_price, 700)
        self.assertEqual(result.final_total, 1400)

    def test_factor_v2_manager_row_does_not_receive_self_discount(self):
        fake = SimpleNamespace(
            qi_id=12, qi=SimpleNamespace(pricing_version=2, manager_approved_price=900),
            net_price=2000, quantity=2, discount_per_item=100,
            factor=SimpleNamespace(self_discount=30, is_official=False, official_value=0),
        )
        self.assertEqual(FactorItem.discount_tuple.fget(fake), (0, 0, 200))

    def test_old_factor_row_still_receives_document_discount(self):
        fake = SimpleNamespace(
            pk=15, qi_id=None, net_price=2000, quantity=2, discount_per_item=100,
            factor=SimpleNamespace(self_discount=30, is_official=False, official_value=0),
        )
        self.assertEqual(FactorItem.discount_tuple.fget(fake)[1:], (600, 200))

    def test_v2_editor_has_independent_route_and_template(self):
        path = reverse("micmod_base:quotation.v2", kwargs={"pk": 17})
        from micmod_base.quotation_v2_full import QuotationsV2FullView
        self.assertIs(resolve(path).func.view_class, QuotationsV2FullView)
        pricing_path = reverse("micmod_base:quotation.v2.pricing", kwargs={"pk": 17})
        self.assertEqual(resolve(pricing_path).func, quotation_v2_editor)
        self.assertNotEqual(path, reverse("micmod_base:quotations.view", kwargs={"pk": 17}))
        self.assertIsNotNone(get_template("micmod-base/quotation/v2/full.html"))
        self.assertIsNotNone(get_template("micmod-base/quotation/v2/editor.html"))
        self.assertIsNotNone(get_template("micmod-base/quotation/view.html"))
        self.assertIsNotNone(get_template("micmod-base/quotation/view-print-raw.html"))

    def test_new_template_explicitly_communicates_discount_exemption(self):
        source = get_template("micmod-base/quotation/v2/editor.html").template.source
        self.assertIn("تخفیف کلی فقط روی ردیف‌های بدون قیمت مصوب مدیر", source)
        self.assertIn("confirm_upgrade", source)
        self.assertIn("system_price_index", source)
        self.assertIn("manager_price", source)
        self.assertIn("name=\"action\" value=\"add\"", source)


class PricingV2HistoricalSafety(SimpleTestCase):
    def test_historical_manager_discount_is_still_applied_in_version_one(self):
        # The 62 historical manager-priced/discounted rows must use the old math.
        old_row = SimpleNamespace(
            pricing_version=1, net_price=2000, quantity=2,
            discount_per_item=50, pk=100,
            quotation=SimpleNamespace(self_discount=10, official_value=0),
        )
        self.assertEqual(
            QuotationItem.discount_tuple.fget(old_row),
            (0, 200, 100),
        )

    def test_v2_editor_cannot_modify_a_document_already_in_sepidar(self):
        from micmod_base.quotation_v2_views import _access
        user = SimpleNamespace(pk=1, is_superuser=True)
        request = SimpleNamespace(user=user)
        quoted = SimpleNamespace(
            creator_user_id=1, last_work_flow=SimpleNamespace(
                to_user_id=1, current_state_name="تایید پیش فاکتور",
            ), cancel=False, is_deleted=False, sepidar_quotation_id=1234,
            sepidar_number=909, pk=17,
        )
        with patch("micmod_base.quotation_v2_views.Factor.objects.filter") as factors:
            factors.return_value.exists.return_value = False
            self.assertFalse(_access(request, quoted))
            quoted.sepidar_quotation_id = None
            quoted.sepidar_number = None
            self.assertTrue(_access(request, quoted))

    def test_v2_system_price_never_changes_when_manager_price_changes(self):
        row = fake_row()
        row.system_price = Decimal("1000")
        row.system_price_method = "express"
        row.system_price_snapshot = {
            "currency_id": 1, "unique_title": "express", "value": "1000",
        }
        _save_price(
            row,
            {
                "system_price_index": "keep",
                "manager_approved": "1",
                "manager_price": "1800",
                "discount_per_item": "50",
            },
        )
        self.assertEqual(row.system_price, Decimal("1000"))
        self.assertEqual(row.manager_approved_price, Decimal("1800"))
        self.assertEqual(row.manager_positive_difference, Decimal("1600.0000"))
        self.assertEqual(row.price_method, "sales_admin")


class PricingV2LockingRegression(SimpleTestCase):
    def test_for_update_locks_only_item_not_nullable_joined_relations(self):
        # No database round-trip is required: verify the actual queryset
        # passed by the v2 editor to Django's object lookup.
        from micmod_base.quotation_v2_views import _get_locked_item

        quotation = SimpleNamespace(pk=16682)
        item = SimpleNamespace(quotation=None)
        with patch(
            "micmod_base.quotation_v2_views.get_object_or_404",
            return_value=item,
        ) as lookup:
            self.assertIs(_get_locked_item(quotation, 99), item)

        query = lookup.call_args.args[0].query
        self.assertTrue(query.select_for_update)
        self.assertFalse(query.select_related)
        self.assertEqual(lookup.call_args.kwargs["pk"], 99)
        self.assertEqual(lookup.call_args.kwargs["quotation_id"], 16682)
        self.assertIs(item.quotation, quotation)
