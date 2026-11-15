"""Optional A4 customer print design; existing print endpoints remain untouched."""
from base64 import b64encode
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse


def as_decimal(value):
    try:
        amount = Decimal(str(value if value is not None else 0))
        return amount if amount.is_finite() else Decimal("0")
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def grouped(value):
    value = as_decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    result = format(value, ",.2f")
    return result.rstrip("0").rstrip(".") if "." in result else result


def document_currency(document, invoice):
    """Prices stored in Rial must be displayed in Toman as in the design."""
    currency = getattr(document, "currency_ref", None)
    if invoice and getattr(document, "q", None):
        currency = getattr(document.q, "currency_ref", None) or currency
    currency_code = getattr(currency, "title_en", "") or ""
    if currency_code.lower() == "rial":
        return Decimal("0.1"), "تومان"
    return Decimal("1"), getattr(currency, "title", None) or currency_code or "واحد پول سند"


def qr_image(url):
    """Self-contained QR, printable offline (no third-party URL or tracking)."""
    try:
        import qrcode
        from qrcode.image.svg import SvgPathImage
    except ImportError:
        return ""
    image = qrcode.make(url, image_factory=SvgPathImage, border=1, box_size=6)
    buffer = BytesIO()
    image.save(buffer)
    return "data:image/svg+xml;base64," + b64encode(buffer.getvalue()).decode("ascii")


def _seller(document):
    official = bool(getattr(document, "is_official", False))
    if not official and getattr(document, "q", None):
        official = bool(getattr(document.q, "is_official", False))
    seller = {
        "name": "رهاورد تجارت آینده" if official else "میکرومدرن",
        "phone": "" if official else "۰۲۱-۶۶۷۳۳۷۹۱",
        "address": "" if official else "خیابان جمهوری، چهارراه سی تیر، پاساژ فرقانی، طبقه دوم، واحد ۱",
        "economic_number": "411563971988" if official else "",
    }
    # Business identities may be configured per legal entity without changing code.
    configured = getattr(settings, "MODERN_PRINT_SELLERS", {}) or {}
    seller.update(configured.get("official" if official else "regular", {}))
    return seller


def build_document(context, invoice, absolute_url, legacy_url):
    """Normalise existing print-view data; reuse its permission and profile context."""
    document = context["data"]
    multiplier, currency_label = document_currency(document, invoice)
    payment = document.payment
    source_forms = context["formset"]
    rows = []
    for form in source_forms:
        item = form.instance
        product = getattr(item, "goods_code", None) if invoice else getattr(item, "goods_code_fk", None)
        goods_code = product if invoice else getattr(item, "goods_code", None)
        product_name = (
            (getattr(item, "part_number_show", None) if invoice else None)
            or getattr(product, "part_number", None)
            or getattr(item, "product_name", None)
            or getattr(item, "customer_goods_name", None)
            or getattr(item, "description", None)
            or str(goods_code or "-")
        )
        unit_price = (
            getattr(item, "price", None) if invoice else
            item.fee_()
        )
        original = as_decimal(item.row_price)
        discount = as_decimal(item.discount_value)
        tax = as_decimal(item.tax)
        rows.append({
            "code": str(goods_code or "-"),
            "name": product_name,
            "description": getattr(item, "sales_description", None) or (
                getattr(item, "description", None) if product_name != getattr(item, "description", None) else ""
            ),
            "quantity": grouped(getattr(item, "quantity", 0)),
            "unit_price": grouped(as_decimal(unit_price) * multiplier),
            "discount": grouped(discount * multiplier),
            "has_discount": discount != 0,
            "before_discount": grouped(original * multiplier),
            "total": grouped((original - discount + tax) * multiplier),
        })

    buyer = context.get("buyer_info") or {}
    return {
        "invoice": invoice,
        "title": "فاکتور فروش کالا و خدمات" if invoice else "پیش‌فاکتور فروش کالا و خدمات",
        "number": ("F" if invoice else "P") + str(document.pk),
        "date": document.created_date if invoice else document.request_date,
        "expiry": None if invoice else document.expiration_date,
        "seller": _seller(document),
        "buyer": buyer,
        "rows": rows,
        "subtotal": grouped(as_decimal(payment[0]) * multiplier),
        "additions": grouped(as_decimal(payment[1]) * multiplier),
        "has_additions": as_decimal(payment[1]) != 0,
        "discount": grouped(as_decimal(payment[2]) * multiplier),
        "has_discount": as_decimal(payment[2]) != 0,
        "tax": grouped(as_decimal(payment[3]) * multiplier),
        "has_tax": as_decimal(payment[3]) != 0,
        "total": grouped(as_decimal(payment[4]) * multiplier),
        "currency_label": currency_label,
        "notes": getattr(document, "description", None) or "",
        "qr_url": qr_image(absolute_url),
        "legacy_url": legacy_url,
        "profile_options": context.get("legal_profile_options", []),
        "selected_profile": context.get("selected_legal_profile") or "",
    }


@login_required
def factor_modern_print(request, id):
    from factor.views import print_view
    context = print_view(request, id=id, context_only=True)
    if isinstance(context, HttpResponse):
        return context
    if not context.get("data"):
        raise Http404("فاکتور یافت نشد.")
    modern_url = reverse("factor:factor.print.modern", args=[id])
    profile = request.GET.get("legal_profile", "")
    legacy_url = reverse("factor:factor.print", args=[id]) + "?" + urlencode({"action": "factor_print", "legal_profile": profile})
    qr_target = request.build_absolute_uri(modern_url + "?" + urlencode({"legal_profile": profile}))
    document = build_document(context, True, qr_target, legacy_url)
    return render(request, "factor/modern_print.html", {"document": document})


@login_required
def quotation_modern_print(request, id):
    from micmod_base.views import print_view
    context = print_view(request, id=id, context_only=True)
    if isinstance(context, HttpResponse):
        return context
    if not context.get("data"):
        raise Http404("پیش‌فاکتور یافت نشد.")
    modern_url = reverse("micmod_base:quotation.print.modern", args=[id])
    profile = request.GET.get("legal_profile", "")
    legacy_url = reverse("micmod_base:print_customer", args=[id]) + "?" + urlencode({"legal_profile": profile})
    qr_target = request.build_absolute_uri(modern_url + "?" + urlencode({"legal_profile": profile}))
    document = build_document(context, False, qr_target, legacy_url)
    return render(request, "factor/modern_print.html", {"document": document})
