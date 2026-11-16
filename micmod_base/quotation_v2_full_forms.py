"""Complete quotation-v2 formset built on top of the legacy production formset.

All original fields, nested InquiryResult forms and permissions remain intact.
The version is set *per new item*, never per parent quotation, so documents may
contain historical v1 rows next to newly created v2 rows.

Price options presented by JavaScript are for convenience only. Monetary values
are resolved again on the server and never trusted from posted price_json.
"""
from decimal import Decimal

from django import forms
from django.conf import settings
from django.forms import inlineformset_factory

from .forms import BaseQIFormset, QuotationItemForm2, qi_fields
from .models import Quotation, QuotationItem
from .pricing_v2 import (
    PricingError, apply_materialized_values, amount,
    calculate_pricing_v2,
)
from .quotation_v2_views import _fetch_prices, _select_reference


class QuotationItemFormV2(QuotationItemForm2):
    """Legacy fields/constraints plus independent manager and system pricing."""
    v2_system_method = forms.CharField(
        required=False, widget=forms.HiddenInput,
    )
    v2_system_index = forms.CharField(
        required=False, widget=forms.HiddenInput,
    )
    v2_manager_price = forms.DecimalField(
        max_digits=22, decimal_places=4, min_value=0, required=False,
        label="فی مصوب مدیر",
        widget=forms.NumberInput(attrs={
            "class": "form-control qv2-manager-price",
            "step": "0.0001", "min": "0",
            "inputmode": "decimal",
            "placeholder": "مبلغ مصوب مدیر",
        }),
    )

    def __init__(self, *args, **kwargs):
        constraint = kwargs.get("constraint") or (kwargs.get("initial") or {}).get("constraint") or {}
        self.v2_request = constraint.get("request")
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            if self.instance.pk and self.instance.pricing_version == 2:
                self.initial["v2_system_method"] = self.instance.system_price_method or ""
                self.initial["v2_manager_price"] = self.instance.manager_approved_price


class BaseQIFormsetV2(BaseQIFormset):
    """Preserve the nested legacy formset and validate v2 monetary input early."""

    def clean(self):
        super().clean()
        if any(self.errors):
            return

        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue

            row = form.instance
            # Do not reinterpret existing historical quotations or manager discounts.
            if row.pk and row.pricing_version != 2:
                continue

            row.pricing_version = 2
            parent = self.instance
            row.quotation = parent

            method = (form.cleaned_data.get("price_method") or "").strip()
            reference_method = (form.cleaned_data.get("v2_system_method") or "").strip()
            if method != "sales_admin":
                reference_method = method

            request = form.v2_request
            advancing = (
                request is not None
                and any(key in request.POST for key in ("next", "submit", "submit/copy", "submit/copy_q"))
                and getattr(form, "form_state", 0) is not None
                and (getattr(form, "form_state", 0) or 0) >= 1
            )

            if not reference_method or reference_method == "----------":
                # Unpriced drafts may enter the inquiry workflow. An approved
                # manager price may NEVER be saved without a system baseline.
                if method == "sales_admin" or advancing or row.system_price is not None:
                    form.add_error("v2_system_method", "برای محاسبه مبلغ، قیمت مرجع سیستم را انتخاب کنید.")
                    continue
                row.final_price = 0
                row.manager_approved_price = None
                row.effective_unit_price = None
                row.calculated_row_discount = None
                row.manager_price_difference = None
                row.manager_positive_difference = None
                form.cleaned_data["final_price"] = 0
                continue

            manager = form.cleaned_data.get("v2_manager_price") if method == "sales_admin" else None
            if method == "sales_admin" and manager is None:
                form.add_error("v2_manager_price", "برای مصوب مدیر باید مبلغ مصوب وارد شود.")
                continue

            # The item might already have a verified reference. Reuse it if its
            # source, quantity and currency still match. This avoids repeated
            # Sepidar round-trips when an unrelated field changes.
            snap = row.system_price_snapshot or {}
            same_saved = (
                row.pk and row.system_price is not None
                and row.system_price_method == reference_method
                and str(snap.get("currency_id")) == str(parent.currency_ref_id)
                and str(snap.get("quantity")) == str(row.quantity)
                and not form.cleaned_data.get("v2_system_index")
            )
            try:
                if not same_saved:
                    if request is None:
                        raise PricingError("اطلاعات درخواست برای بررسی قیمت موجود نیست.")
                    fresh_entries = _fetch_prices(request, parent, row)
                    row.price_json = fresh_entries
                    form.cleaned_data["price_json"] = fresh_entries

                    # Indexes always refer to the fresh *server* list, never to
                    # monetary amounts submitted by the browser.
                    raw_index = (form.cleaned_data.get("v2_system_index") or "").strip()
                    if raw_index.isdigit():
                        idx = int(raw_index)
                        if not 0 <= idx < len(fresh_entries):
                            raise PricingError("گزینه قیمت انتخاب‌شده معتبر نیست.")
                        if fresh_entries[idx].get("unique_title") != reference_method:
                            raise PricingError("روش قیمت با گزینه استعلام مطابقت ندارد.")
                    else:
                        matches = [
                            idx for idx, item in enumerate(fresh_entries)
                            if item.get("unique_title") == reference_method
                        ]
                        if len(matches) != 1:
                            raise PricingError("قیمت مرجع یکتا نیست؛ گزینه قیمت را دوباره انتخاب کنید.")
                        idx = matches[0]

                    system, source, snapshot = _select_reference(
                        row, {"system_price_index": str(idx)}
                    )
                    snapshot["quantity"] = row.quantity
                    row.system_price = system
                    row.system_price_method = source
                    row.system_price_snapshot = snapshot

                discount = amount(form.cleaned_data.get("discount_per_item") or 0)
                if manager is not None:
                    # No *additional* commercial discount on v2 manager rows.
                    discount = Decimal("0")
                # Calculate once now, before workflow/formset commit.
                calculate_pricing_v2(
                    system_price=row.system_price,
                    manager_approved_price=manager,
                    quantity=row.quantity,
                    discount_per_item=discount,
                    self_discount=parent.self_discount or 0,
                    is_official=parent.is_official,
                    official_value=parent.official_value or 0,
                    tax_rate=getattr(settings, "TAX_VALUE", 0),
                )

                row.manager_approved_price = manager
                row.discount_per_item = float(discount)
                form.cleaned_data["discount_per_item"] = float(discount)
                apply_materialized_values(row)
                form.cleaned_data["final_price"] = row.final_price
            except PricingError as exc:
                form.add_error("v2_system_method", str(exc))


QuotationItemFormsetV2 = inlineformset_factory(
    Quotation, QuotationItem,
    form=QuotationItemFormV2,
    formset=BaseQIFormsetV2,
    extra=1,
    fields=qi_fields,
)
