"""Version-2 quotation pricing. This module does not depend on legacy calculation rules.

All amounts are expressed in the quotation currency. The system price is an
immutable-in-calculation reference: manager approval changes the *selling*
price but NEVER overwrites the system reference. The persisted fields on
QuotationItem are materialized from this deterministic calculator.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


ZERO = Decimal("0")
HUNDRED = Decimal("100")
PRECISION = Decimal("0.0001")


class PricingError(ValueError):
    """Raised when a version-2 quotation row cannot be priced safely."""


def amount(value, *, default=ZERO):
    if value is None or value == "":
        return default
    try:
        result = Decimal(str(value).replace(",", "").strip())
    except (ValueError, TypeError, InvalidOperation) as exc:
        raise PricingError("مبلغ واردشده معتبر نیست.") from exc
    if not result.is_finite():
        raise PricingError("مقدار نامعتبر برای مبلغ وارد شده است.")
    return result


def four(value):
    return value.quantize(PRECISION, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class PricingResult:
    reference_price: Decimal
    customer_unit_price: Decimal
    quantity: Decimal
    unit_discount: Decimal
    document_discount: Decimal
    official_adjustment: Decimal
    row_discount: Decimal
    gross: Decimal
    tax: Decimal
    final_total: Decimal
    effective_unit_price: Decimal
    positive_sales_difference_unit: Decimal
    positive_sales_difference_total: Decimal
    manager_approved: bool

    def as_bi_fields(self):
        return {
            "effective_unit_price": four(self.effective_unit_price),
            "calculated_row_discount": four(self.row_discount),
            "manager_price_difference": four(
                (self.effective_unit_price - self.reference_price) if self.manager_approved else ZERO
            ),
            "manager_positive_difference": four(self.positive_sales_difference_total),
        }


def calculate_pricing_v2(
    *,
    system_price,
    manager_approved_price=None,
    quantity=1,
    discount_per_item=0,
    self_discount=0,
    is_official=False,
    official_value=0,
    tax_rate=0,
):
    system = amount(system_price, default=None)
    if system is None or system <= ZERO:
        raise PricingError("برای قیمت‌گذاری نسخه ۲ باید قیمت مرجع سیستم انتخاب شود.")

    qty = amount(quantity, default=None)
    if qty is None or qty <= ZERO:
        raise PricingError("تعداد کالا باید بزرگ‌تر از صفر باشد.")

    manager = (
        amount(manager_approved_price)
        if manager_approved_price is not None and manager_approved_price != ""
        else None
    )
    if manager is not None and manager < ZERO:
        raise PricingError("قیمت مصوب مدیر نمی‌تواند منفی باشد.")

    percent = amount(self_discount)
    if percent < ZERO or percent > HUNDRED:
        raise PricingError("تخفیف کلی باید بین صفر و صد درصد باشد.")

    tax_percent = amount(tax_rate)
    official_percent = amount(official_value)
    if not ZERO <= official_percent <= HUNDRED or not ZERO <= tax_percent <= HUNDRED:
        raise PricingError("نرخ مالیات یا تعدیل رسمی نامعتبر است.")

    approved = manager is not None
    if approved:
        # Manager approval is unconditional: no row or document commercial discount.
        # If the manager sold above system, only the *customer-visible* base rises.
        customer_base = max(system, manager)
        unit_discount = customer_base - manager
        document_discount = ZERO
        actual_unit = manager
        positive_difference = max(manager - system, ZERO)
    else:
        row_discount_per_unit = amount(discount_per_item)
        if row_discount_per_unit < ZERO or row_discount_per_unit > system:
            raise PricingError("تخفیف واحد باید بین صفر و قیمت مرجع باشد.")
        unit_discount = row_discount_per_unit
        # Preserve existing base for self_discount (percentage of gross unit price).
        document_discount = system * percent / HUNDRED
        actual_unit = system - unit_discount - document_discount
        if actual_unit < ZERO:
            raise PricingError("جمع تخفیف‌ها نمی‌تواند بیشتر از قیمت مرجع باشد.")
        customer_base = system
        positive_difference = ZERO

    gross = customer_base * qty
    commercial_discount = (unit_discount + document_discount) * qty

    # Existing Sepidar tax model adjusts the taxable base when official_value is set.
    # This is a *tax-related adjustment*, not self_discount or discount_per_item.
    official_adjustment = ZERO
    if is_official and official_percent:
        official_adjustment = (
            (gross - commercial_discount) * official_percent / (HUNDRED + tax_percent)
        )
    discount_total = commercial_discount + official_adjustment
    taxable = gross - discount_total
    tax = taxable * tax_percent / HUNDRED if is_official else ZERO
    total = taxable + tax

    return PricingResult(
        reference_price=system,
        customer_unit_price=customer_base,
        quantity=qty,
        unit_discount=unit_discount * qty,
        document_discount=document_discount * qty,
        official_adjustment=official_adjustment,
        row_discount=discount_total,
        gross=gross,
        tax=tax,
        final_total=total,
        effective_unit_price=actual_unit,
        positive_sales_difference_unit=positive_difference,
        positive_sales_difference_total=positive_difference * qty,
        manager_approved=approved,
    )


def from_quotation_item(item):
    from django.conf import settings
    quotation = item.quotation
    return calculate_pricing_v2(
        system_price=item.system_price,
        manager_approved_price=item.manager_approved_price,
        quantity=item.quantity,
        discount_per_item=item.discount_per_item or ZERO,
        self_discount=quotation.self_discount or ZERO,
        is_official=quotation.is_official,
        official_value=quotation.official_value or ZERO,
        tax_rate=getattr(settings, "TAX_VALUE", 0),
    )


def apply_materialized_values(item):
    """Call only on explicit version-2 price/quantity edits, not when reading legacy rows."""
    if item.pricing_version != 2:
        raise PricingError("بروزرسانی قیمت‌گذاری نسخه ۲ فقط برای ردیف نسخه ۲ مجاز است.")
    result = from_quotation_item(item)
    for key, value in result.as_bi_fields().items():
        setattr(item, key, value)
    item.final_price = float(
        result.effective_unit_price
        if item.manager_approved_price is not None
        else result.reference_price
    )
    return result
