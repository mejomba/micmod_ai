"""Validation for multi-condition sale terms shared by Factor and Quotation.

The UI sends a list starting with one computed system cash row, followed by
user-entered conditions. Legacy lists without the computed row remain readable.
`amount` retains its historical meaning: fraction, e.g. 0.3 for 30 percent.
"""
from decimal import Decimal, InvalidOperation
import re

from django import forms
from django.utils.dateparse import parse_datetime

VALID_TYPES = {"cash", "check", "advance"}
DATE_KEYS = ("Check Collection Date", "Receipt Date")


def dec(value, field, row):
    # sac-v9b-empty-zero: empty numeric field means zero.
    if value is None or (isinstance(value, str) and not value.strip()):
        value = 0
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise forms.ValidationError(f"شرط {row}: مقدار {field} معتبر نیست.")
    if not result.is_finite():
        raise forms.ValidationError(f"شرط {row}: مقدار {field} معتبر نیست.")
    return result


def parse_utc(value, row, label):
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise forms.ValidationError(f"شرط {row}: {label} نامعتبر است.")
    string = value.strip().replace(" ", "T", 1)
    string = re.sub(r"([+-]\d{2})$", r"\1:00", string)
    dt = parse_datetime(string)
    if dt is None or dt.tzinfo is None or dt.utcoffset() is None or dt.utcoffset().total_seconds() != 0:
        raise forms.ValidationError(f"شرط {row}: {label} باید تاریخ میلادی UTC باشد.")
    return dt


def normalize_sale_conditions(value):
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise forms.ValidationError("شرایط فروش باید آرایه‌ای از JSON باشد.")
    if len(value) > 101:
        raise forms.ValidationError("تعداد شروط پرداخت بیش از حد مجاز است.")

    results = []
    seen_system = False
    total_manual_amount = Decimal("0")
    system_total = system_payment = None
    for index, original in enumerate(value, 1):
        if not isinstance(original, dict):
            raise forms.ValidationError(f"شرط {index}: ساختار نامعتبر است.")
        kind = original.get("type")
        if kind not in VALID_TYPES:
            raise forms.ValidationError(f"شرط {index}: نوع پرداخت نامعتبر است.")
        fraction = dec(original.get("amount"), "نسبت پرداخت", index)
        if fraction < 0:
            raise forms.ValidationError(f"شرط {index}: نسبت پرداخت منفی مجاز نیست.")
        is_system = original.get("is_system") is True
        if is_system:
            if index != 1 or seen_system or kind != "cash":
                raise forms.ValidationError("ردیف نقدی سیستمی باید اولین و تنها ردیف سیستمی باشد.")
            seen_system = True
            if fraction > 1:
                raise forms.ValidationError("مبلغ نقدی سیستمی نمی‌تواند بیش از مبلغ کل سند باشد.")

        dates = {}
        for key in DATE_KEYS:
            dt = parse_utc(original.get(key), index, "تاریخ دریافت چک" if key == DATE_KEYS[0] else "تاریخ دریافت/وصول وجه")
            dates[key] = original.get(key) or None
            if key == DATE_KEYS[0]:
                collection = dt
            else:
                receipt = dt
        if is_system and any(dates.values()):
            raise forms.ValidationError("برای ردیف نقدی سیستمی نباید تاریخ وارد شود.")
        if not is_system and kind == "check" and collection and receipt and receipt < collection:
            raise forms.ValidationError(f"شرط {index}: تاریخ وصول چک قبل از تاریخ دریافت چک است.")
        if kind != "check" and dates[DATE_KEYS[0]] is not None:
            raise forms.ValidationError(f"شرط {index}: تاریخ دریافت چک فقط برای پرداخت چکی است.")

        item = dict(original)
        item.pop("item_scope", None)  # Removed from the final UI.
        item["type"] = kind
        item["amount"] = format(fraction.normalize(), "f")
        item.update(dates)
        if "input_mode" in item or is_system:
            mode = item.get("input_mode")
            if mode not in ("percent", "amount"):
                raise forms.ValidationError(f"شرط {index}: نحوه ورود پرداخت نامعتبر است.")
            payment = dec(item.get("payment_amount"), "مبلغ پرداخت", index)
            percentage = dec(item.get("percentage"), "درصد پرداخت", index)
            input_value = dec(item.get("input_value"), "مقدار واردشده", index)
            # sac-v9b-empty-zero: store zero, never a blank numeric string.
            for numeric_key, parsed in (("payment_amount", payment),
                                        ("percentage", percentage),
                                        ("input_value", input_value)):
                old_numeric = item.get(numeric_key)
                if old_numeric is None or (isinstance(old_numeric, str) and not old_numeric.strip()):
                    item[numeric_key] = format(parsed, "f")
            if payment < 0 or percentage < 0 or input_value < 0:
                raise forms.ValidationError(f"شرط {index}: مقادیر منفی مجاز نیستند.")
            if abs(fraction * 100 - percentage) > Decimal("0.00001"):
                raise forms.ValidationError(f"شرط {index}: درصد و نسبت پرداخت با هم منطبق نیستند.")
            if mode == "percent" and abs(input_value - percentage) > Decimal("0.00001"):
                raise forms.ValidationError(f"شرط {index}: درصد واردشده با درصد ذخیره‌شده منطبق نیست.")
            if mode == "amount" and abs(input_value - payment) > Decimal("0.02"):
                raise forms.ValidationError(f"شرط {index}: مبلغ واردشده با مبلغ ذخیره‌شده منطبق نیست.")
            if is_system:
                system_total = dec(item.get("base_total"), "مبلغ کل سند", index)
                system_payment = payment
                if system_total < 0:
                    raise forms.ValidationError("مبلغ کل سند نمی‌تواند منفی باشد.")
            else:
                total_manual_amount += payment
        results.append(item)

    if seen_system:
        expected = max(Decimal("0"), system_total - total_manual_amount)
        # Monetary amounts are submitted to two decimals.
        if abs(expected - system_payment) > Decimal("0.05"):
            raise forms.ValidationError("مانده نقدی سیستمی با جمع پرداخت‌ها مطابقت ندارد.")
        if system_total > 0:
            expected_ratio = system_payment / system_total
            if abs(dec(results[0]["amount"], "نسبت سیستمی", 1) - expected_ratio) > Decimal("0.0000001"):
                raise forms.ValidationError("نسبت ردیف نقدی سیستمی نادرست است.")
    return results


class SaleConditionsFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Provide defaults for a new Factor, or an existing linked Factor whose
        # own JSON is empty. Never overwrite populated Factor JSON or bound POST.
        if self.is_bound or "sale_type_multi_condition" not in self.fields:
            return
        if self._meta.model.__name__ != "Factor":
            return
        instance = self.instance
        if instance and instance.__class__.__name__ == "Factor" and instance.pk and (instance.sale_type_multi_condition or []):
            return
        if self.initial.get("sale_type_multi_condition"):
            return
        source = None
        if instance and instance.__class__.__name__ == "Quotation":
            source = instance
        elif getattr(instance, "q", None) is not None:
            source = instance.q
        else:
            q = self.initial.get("q")
            if q:
                from micmod_base.models import Quotation
                try:
                    source = q if isinstance(q, Quotation) else Quotation.objects.filter(pk=getattr(q, "pk", q)).first()
                except (TypeError, ValueError):
                    source = None
        if source is not None:
            from copy import deepcopy
            self.initial["sale_type_multi_condition"] = deepcopy(source.sale_type_multi_condition or [])

    def clean_sale_type_multi_condition(self):
        sale_type = self.cleaned_data.get("sale_type")
        if sale_type is None and "sale_type" not in self.fields:
            sale_type = getattr(self.instance, "sale_type", None)
        if sale_type is not None:
            label = str(getattr(sale_type, "title", "")).replace(" ", "").replace("‌", "")
            # The ID is an internal backend fallback; it is not sent to the browser.
            if getattr(sale_type, "pk", None) != 53 and "چندشرطی" not in label:
                return getattr(self.instance, "sale_type_multi_condition", None) or []
        terms = self.cleaned_data.get("sale_type_multi_condition", [])
        # A linked quotation supplies defaults when creating a Factor. This is
        # necessary even for POST-only/legacy flows that never fire Select2 JS.
        if self._meta.model.__name__ == "Factor" and not getattr(self.instance, "pk", None) and not terms:
            quotation = self.cleaned_data.get("q") or getattr(self.instance, "q", None)
            if quotation is not None:
                from copy import deepcopy
                terms = deepcopy(getattr(quotation, "sale_type_multi_condition", None) or [])
        return normalize_sale_conditions(terms)
