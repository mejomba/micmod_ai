"""The full quotation v2 screen must retain production workflow + nested rows."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.template.loader import get_template
from django.urls import resolve, reverse

from inquiry.forms import InquiryResultForm
from micmod_base.forms import (
    BaseQIFormset, QuotationForm, QuotationItemForm2, QuotationItemFormset,
)
from micmod_base.quotation_v2_full import QuotationsV2FullView
from micmod_base.quotation_v2_full_forms import (
    BaseQIFormsetV2, QuotationItemFormV2, QuotationItemFormsetV2,
)
from micmod_base.views import QuotationsView


class QuotationV2CompleteWorkflowTests(SimpleTestCase):
    def test_full_view_reuses_legacy_workflow_and_forms(self):
        self.assertTrue(issubclass(QuotationsV2FullView, QuotationsView))
        self.assertIs(QuotationsV2FullView.flow_config, QuotationsView.flow_config)
        self.assertTrue(QuotationsV2FullView.has_flow)
        self.assertIs(QuotationsV2FullView.form_struct["form"], QuotationForm)
        self.assertIs(
            QuotationsV2FullView.form_struct["childes"][0]["childes"][0]["form"],
            InquiryResultForm,
        )
        self.assertTrue(issubclass(QuotationItemFormV2, QuotationItemForm2))
        self.assertTrue(issubclass(QuotationItemFormsetV2, BaseQIFormset))
        self.assertTrue(issubclass(BaseQIFormsetV2, BaseQIFormset))
        self.assertEqual(
            QuotationItemFormsetV2.form._meta.fields,
            QuotationItemFormset.form._meta.fields,
        )

    def test_creation_and_editing_routes_are_independent_of_legacy(self):
        create = reverse("micmod_base:quotation.v2.create")
        edit = reverse("micmod_base:quotation.v2", kwargs={"pk": 16682})
        self.assertIs(resolve(create).func.view_class, QuotationsV2FullView)
        self.assertIs(resolve(edit).func.view_class, QuotationsV2FullView)
        self.assertNotEqual(create, reverse("micmod_base:quotations.create"))
        self.assertNotEqual(edit, reverse("micmod_base:quotations.view", kwargs={"pk": 16682}))

    def test_full_template_contains_all_existing_operational_components(self):
        template = get_template("micmod-base/quotation/v2/full.html").template.source
        for required in (
            "workflow/flow.html",
            "factor/partial/sale_conditions_editor.html",
            "formset.management_form",
            "formset.empty_form",
            "form_.nested.forms.0",
            "item_full.html",
            "partials/formset_header_buttons.html",
            "core/partial/add_formset_button.html",
            "js/extra/quotation1.js",
            "js/extra/formset.js",
            "quotation_v2_full.js",
            "get_comment_user_list",
            "get_payment_list",
            "id_kt_empty_modal_lg",
            "form_footer_extra",
            "qv2-workflow-heading",
            "qv2-lines-heading",
        ):
            with self.subTest(component=required):
                self.assertIn(required, template)

    def test_item_template_preserves_old_controls_and_adds_separate_prices(self):
        source = get_template("micmod-base/quotation/v2/item_full.html").template.source
        for required in (
            "nested_manage.management_form",
            "form_s.quantity",
            "form_s.goods_code",
            "form_s.goods_name",
            "form_s.need_local_price_inquiry",
            "form_s.need_foreign_price_inquiry",
            "form_s.discount_per_item",
            "form_s.final_price",
            "form_s.price_json",
            "form_s.sales_description",
            "form_s.supply_date",
            "form_s.customer_goods_code",
            "form_s.customer_goods_name",
            "data-qv2-version",
            "data-qv2-source-select",
            "form_s.v2_manager_price",
            "quotation.v2.pricing",
        ):
            with self.subTest(component=required):
                self.assertIn(required, source)

    def test_v2_formset_adds_no_fields_to_legacy_quotationitem_model_form(self):
        self.assertEqual(
            set(QuotationItemFormsetV2.form._meta.fields),
            set(QuotationItemFormset.form._meta.fields),
        )
        self.assertIn("v2_manager_price", QuotationItemFormV2.base_fields)
        self.assertIn("v2_system_method", QuotationItemFormV2.base_fields)
        self.assertIn("v2_system_index", QuotationItemFormV2.base_fields)

    def test_v2_success_url_returns_to_full_screen(self):
        view = QuotationsV2FullView()
        view.object = SimpleNamespace(pk=16682)
        self.assertEqual(
            str(view.get_success_url()),
            reverse("micmod_base:quotation.v2", kwargs={"pk": 16682}),
        )


class QuotationV2MixedVersionFormsetTests(SimpleTestCase):
    @staticmethod
    def fake_form(row, *, method, reference_method="", price_index="",
                  manager=None, discount=50):
        form = MagicMock()
        form.instance = row
        form.form_state = 1
        form.v2_request = SimpleNamespace(POST={"draft": "1"})
        form.cleaned_data = {
            "price_method": method,
            "v2_system_method": reference_method,
            "v2_system_index": price_index,
            "v2_manager_price": manager,
            "discount_per_item": discount,
            "DELETE": False,
        }
        return form

    @staticmethod
    def fake_formset(forms):
        formset = object.__new__(BaseQIFormsetV2)
        formset.__dict__["forms"] = forms
        formset._errors = []
        formset._non_form_errors = []
        formset.instance = SimpleNamespace(
            currency_ref_id=1, self_discount=10, is_official=False,
            official_value=0,
        )
        return formset

    @staticmethod
    def fake_row(pk=None, version=1):
        return SimpleNamespace(
            pk=pk, pricing_version=version, quantity=2,
            price_json=None, system_price=None,
            system_price_method=None, system_price_snapshot=None,
            manager_approved_price=None, discount_per_item=50,
            price_method="sales_admin" if version == 1 else "express",
            final_price=1000, effective_unit_price=None,
            calculated_row_discount=None, manager_price_difference=None,
            manager_positive_difference=None,
        )

    def test_existing_legacy_row_never_gets_repriced_or_upgraded(self):
        old = self.fake_row(pk=99, version=1)
        form = self.fake_form(old, method="sales_admin", manager=Decimal("1000"))
        with patch.object(BaseQIFormset, "clean"), patch(
            "micmod_base.quotation_v2_full_forms._fetch_prices"
        ) as fetch:
            BaseQIFormsetV2.clean(self.fake_formset([form]))
        fetch.assert_not_called()
        self.assertEqual(old.pricing_version, 1)
        self.assertEqual(old.final_price, 1000)
        self.assertIsNone(old.system_price)

    def test_new_rows_default_to_v2_even_inside_legacy_quote(self):
        row = self.fake_row(pk=None, version=1)
        form = self.fake_form(row, method="", discount=50)
        with patch.object(BaseQIFormset, "clean"):
            BaseQIFormsetV2.clean(self.fake_formset([form]))
        self.assertEqual(row.pricing_version, 2)
        self.assertIsNone(row.system_price)

    def test_new_manager_row_requires_independent_system_reference(self):
        row = self.fake_row()
        form = self.fake_form(row, method="sales_admin", manager=Decimal("800"))
        with patch.object(BaseQIFormset, "clean"):
            BaseQIFormsetV2.clean(self.fake_formset([form]))
        form.add_error.assert_called_once()
        self.assertIn("v2_system_method", form.add_error.call_args.args)

    def test_server_selected_reference_prices_manager_without_global_discount(self):
        row = self.fake_row()
        form = self.fake_form(
            row, method="sales_admin", reference_method="express",
            price_index="0", manager=Decimal("800"), discount=70,
        )
        entries = [{"unique_title": "express", "value": 1000, "iqref": 13}]
        with patch.object(BaseQIFormset, "clean"), patch(
            "micmod_base.quotation_v2_full_forms._fetch_prices",
            return_value=entries,
        ):
            BaseQIFormsetV2.clean(self.fake_formset([form]))
        self.assertEqual(row.pricing_version, 2)
        self.assertEqual(row.system_price, Decimal("1000"))
        self.assertEqual(row.manager_approved_price, Decimal("800"))
        self.assertEqual(row.discount_per_item, 0)
        self.assertEqual(row.final_price, 800)
        self.assertEqual(row.calculated_row_discount, Decimal("400.0000"))
        self.assertEqual(row.manager_positive_difference, Decimal("0.0000"))
        self.assertEqual(form.cleaned_data["price_json"], entries)

    def test_client_supplied_reference_price_is_not_used(self):
        row = self.fake_row()
        form = self.fake_form(
            row, method="express", reference_method="express",
            price_index="0", discount=0,
        )
        form.cleaned_data["price_json"] = [
            {"unique_title": "express", "value": 1}
        ]
        with patch.object(BaseQIFormset, "clean"), patch(
            "micmod_base.quotation_v2_full_forms._fetch_prices",
            return_value=[{"unique_title": "express", "value": 1000}],
        ):
            BaseQIFormsetV2.clean(self.fake_formset([form]))
        self.assertEqual(row.system_price, Decimal("1000"))
        self.assertEqual(row.final_price, 1000)
