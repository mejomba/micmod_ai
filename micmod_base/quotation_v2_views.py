"""Independent quotation v2 pricing editor; the original QuotationsView is untouched."""
import json
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from extra_data.models import Item
from factor.models import Factor
from .models import Quotation, QuotationItem
from .pricing_v2 import PricingError, amount, apply_materialized_values, calculate_pricing_v2


def _access(request, quote):
    user = request.user
    current_owner = getattr(getattr(quote, "last_work_flow", None), "to_user_id", None)
    owner = user.pk in (quote.creator_user_id, current_owner)
    can_view = (
        user.is_superuser or owner
        or user.has_perm("micmod_base.view_quotation")
        or user.has_perm("micmod_base.change_quotation")
    )
    if not can_view:
        raise PermissionDenied
    editable = (
        not quote.cancel and not quote.is_deleted
        and (user.is_superuser or (user.has_perm("micmod_base.change_quotation") and owner))
        and not Factor.objects.filter(q_id=quote.pk, is_deleted=False).exists()
    )
    return editable


def _current_prices(row):
    return row.price_json if isinstance(row.price_json, list) else []


def _price_choices(row):
    choices = []
    for idx, entry in enumerate(_current_prices(row)):
        if not isinstance(entry, dict) or entry.get("unique_title") in (
            None, "", "sales_admin", "goods_last_price", "goods_q_last_price"
        ):
            continue
        try:
            raw = entry.get("value")
            value = amount(raw.get("price") if isinstance(raw, dict) else raw, default=None)
            if value is None or value <= 0:
                continue
        except PricingError:
            continue
        choices.append({
            "index": idx,
            "name": entry.get("title") or entry.get("unique_title"),
            "method": entry.get("unique_title"),
            "price": str(value),
            "source": entry.get("iqref"),
            "updated": entry.get("jdate") or entry.get("date") or "",
            "access": entry.get("access_type") or "",
            "selected": bool(
                row.system_price_snapshot and
                row.system_price_snapshot.get("unique_title") == entry.get("unique_title") and
                str(row.system_price_snapshot.get("iqref")) == str(entry.get("iqref")) and
                str(row.system_price_snapshot.get("value")) == str(entry.get("value"))
            ),
        })
    return choices


def _select_reference(row, post):
    raw_index = post.get("system_price_index", "")
    if not raw_index.isdigit():
        # An already selected v2 system reference may remain in use, unchanged,
        # even if the current price inquiry no longer offers that option.
        if row.pricing_version == 2 and row.system_price is not None and raw_index == "keep":
            return row.system_price, row.system_price_method, row.system_price_snapshot
        raise PricingError("برای قیمت مرجع باید یک استعلام معتبر انتخاب کنید.")
    idx = int(raw_index)
    entries = _current_prices(row)
    if not 0 <= idx < len(entries):
        raise PricingError("گزینه استعلام قیمت موجود نیست.")
    entry = entries[idx]
    if not isinstance(entry, dict):
        raise PricingError("ساختار استعلام قیمت معتبر نیست.")
    if entry.get("unique_title") in (
        None, "", "sales_admin", "goods_last_price", "goods_q_last_price"
    ):
        raise PricingError("فقط قیمت معتبر استعلام می‌تواند قیمت مرجع سیستم باشد.")
    value = entry.get("value")
    value = amount(value.get("price") if isinstance(value, dict) else value, default=None)
    if value is None or value <= 0:
        raise PricingError("قیمت استعلام انتخاب‌شده معتبر نیست.")
    if entry.get("unique_title") == "bazar" and entry.get("price_expire_date"):
        expiry_raw = str(entry["price_expire_date"])
        expiry = parse_datetime(expiry_raw)
        expiry = expiry or parse_date(expiry_raw)
        if expiry is None:
            raise PricingError("تاریخ اعتبار استعلام بازار نامعتبر است.")
        current = timezone.now() if hasattr(expiry, "hour") else timezone.localdate()
        if hasattr(expiry, "hour") and timezone.is_naive(expiry):
            expiry = timezone.make_aware(expiry)
        if expiry < current:
            raise PricingError("اعتبار استعلام بازار به پایان رسیده است؛ استعلام تازه دریافت کنید.")
    return value, entry.get("unique_title"), {
        "unique_title": entry.get("unique_title"),
        "value": str(value),
        "iqref": entry.get("iqref"),
        "ref": entry.get("ref"),
        "seen": str(entry.get("seen") or ""),
        "date": str(entry.get("date") or ""),
        "currency_id": row.quotation.currency_ref_id,
        "quantity": row.quantity,
    }


def _save_price(row, post, *, upgrade=False):
    if row.pricing_version != 2 and not upgrade:
        raise PricingError("ردیف قدیمی فقط با تأیید صریح قابل تبدیل به نسخه ۲ است.")
    system_price, method, snapshot = _select_reference(row, post)
    if snapshot and snapshot.get("currency_id") not in (None, row.quotation.currency_ref_id):
        raise PricingError("ارز استعلام با ارز پیش‌فاکتور متفاوت است؛ قیمت‌ها را تازه‌سازی کنید.")
    is_manager = post.get("manager_approved") == "1"
    manager = None
    if is_manager:
        submitted = post.get("manager_price")
        if (submitted is None or submitted.strip() == "") and upgrade and row.price_method == "sales_admin":
            submitted = row.final_price
        manager = amount(submitted, default=None)
        if manager is None:
            raise PricingError("فی مصوب مدیر باید وارد شود.")
    discount = amount(post.get("discount_per_item", "0"))
    if is_manager:
        discount = Decimal("0")
    result = calculate_pricing_v2(
        system_price=system_price,
        manager_approved_price=manager,
        quantity=row.quantity,
        discount_per_item=discount,
        self_discount=row.quotation.self_discount or 0,
        is_official=row.quotation.is_official,
        official_value=row.quotation.official_value or 0,
        tax_rate=getattr(settings, "TAX_VALUE", 0),
    )
    row.pricing_version = 2
    row.system_price = system_price
    row.system_price_method = method
    row.system_price_snapshot = snapshot
    row.manager_approved_price = manager
    row.price_method = "sales_admin" if is_manager else method
    if getattr(row, "pk", None) and snapshot and str(snapshot.get("iqref") or "").isdigit():
        # Keep the legacy inquiry reference usable by existing BI consumers.
        from inquiry.models import PriceInquiryResult
        inquiry_id = int(snapshot["iqref"])
        if PriceInquiryResult.objects.filter(
            pk=inquiry_id, sku_id=row.goods_code_fk_id
        ).exists():
            row.selected_price_code_id = inquiry_id
    row.discount_per_item = float(discount)
    apply_materialized_values(row)
    return result


def _fetch_prices(request, quote, row):
    """Reuse the actual inquiry pricing endpoint on the server, not client JSON."""
    from inquiry.views import get_item

    original_query = request.GET
    query = original_query.copy()
    query.update({
        "q": str(row.goods_code),
        "party_id": str(getattr(quote.customer_party_id, "sepidar_party_id", "") or ""),
        "id_currency_ref": str(quote.currency_ref_id),
        "id_payment_method": str(quote.payment_method or ""),
        "id_customer_grade": str(quote.customer_grade or ""),
        "id_market_grade": str(quote.market_grade or ""),
        "price_setting": str(quote.q_price_setting_id or ""),
        "quantity": str(row.quantity),
        "trade_price_code": str(row.trade_price_code_id or ""),
        "bazar_price_code": str(row.bazar_price_code_id or ""),
    })
    try:
        request.GET = query
        response = get_item(request)
    finally:
        request.GET = original_query
    if response.status_code != 200:
        raise PricingError("سرویس استعلام قیمت پاسخ معتبر نداد.")
    data = json.loads(response.content)
    entries = (data.get("items") or [{}])[0].get("price_list")
    if not isinstance(entries, list) or not entries:
        raise PricingError("استعلام قیمتی برای این کالا دریافت نشد.")
    if len(entries) > 250:
        raise PricingError("تعداد گزینه‌های استعلام غیرمجاز است.")
    return entries


def _view_rows(quote):
    rows = quote.quotation.filter(is_deleted=False).select_related("goods_code_fk").order_by("index", "pk")
    rendered = []
    for row in rows:
        options = _price_choices(row)
        # A saved, verified reference is always usable without forcing a new inquiry.
        legacy = row.pricing_version != 2
        rendered.append({
            "obj": row,
            "options": options,
            "is_legacy": legacy,
            "is_manager": (row.manager_approved_price is not None if not legacy
                           else row.price_method == "sales_admin"),
            "selected_method": row.system_price_method,
            "price": row.fee_() if not (row.pricing_version == 2 and row.system_price is None) else None,
            "discount": row.discount_value,
            "final_total": row.price,
        })
    return rendered


@login_required
@require_http_methods(["GET", "POST"])
def quotation_v2_editor(request, pk):
    quote = get_object_or_404(
        Quotation.objects.select_related("customer_party_id", "currency_ref", "last_work_flow"),
        pk=pk,
    )
    editable = _access(request, quote)
    if request.method == "POST":
        if not editable:
            raise PermissionDenied("امکان ویرایش مالی این سند وجود ندارد.")
        action = request.POST.get("action")
        try:
            with transaction.atomic():
                if action == "add":
                    sku = (request.POST.get("sku") or "").strip()
                    if not sku or len(sku) > 40:
                        raise PricingError("کد کالا معتبر نیست.")
                    item = Item.objects.filter(sku__iexact=sku).first()
                    if item is None and sku.isdigit():
                        item = Item.objects.filter(pk=int(sku)).first()
                    if item is None:
                        raise PricingError("کالای مورد نظر پیدا نشد.")
                    qty = amount(request.POST.get("quantity"), default=None)
                    if qty is None or qty != qty.to_integral_value() or qty <= 0:
                        raise PricingError("تعداد کالا باید عدد صحیح و مثبت باشد.")
                    max_index = quote.quotation.aggregate(last=Max("index"))["last"] or 0
                    QuotationItem.objects.create(
                        quotation=quote, pricing_version=2, index=max_index + 1,
                        goods_code=str(item.sku), goods_code_fk=item,
                        goods_name=item.part_number, itemid=item.sepidar_id_0,
                        quantity=int(qty), discount_per_item=0,
                        creator_user=request.user, editor_user=request.user,
                    )
                    messages.success(request, "ردیف نسخه ۲ ایجاد شد؛ استعلام قیمت آن را دریافت کنید.")
                elif action in ("refresh", "save", "upgrade"):
                    row_id = request.POST.get("row_id", "")
                    if not row_id.isdigit():
                        raise PricingError("شناسه ردیف نامعتبر است.")
                    row = get_object_or_404(
                        QuotationItem.objects.select_for_update().select_related("quotation", "quotation__currency_ref"),
                        pk=int(row_id), quotation=quote, is_deleted=False,
                    )
                    if action == "refresh":
                        if row.pricing_version != 2:
                            raise PricingError("ابتدا ردیف قدیمی را آگاهانه ارتقا دهید.")
                        row.price_json = _fetch_prices(request, quote, row)
                        row.extra_data.request = request
                        row.save(update_fields=["price_json"])
                        messages.success(request, "قیمت‌های استعلام از سرور دریافت و ثبت شدند.")
                    else:
                        upgrade = action == "upgrade"
                        if upgrade and request.POST.get("confirm_upgrade") != "1":
                            raise PricingError("برای تبدیل ردیف قدیمی باید تغییر قانون محاسبات را تأیید کنید.")
                        if row.pricing_version != 2 and not upgrade:
                            raise PricingError("ردیف نسخه ۱ تنها در حالت مشاهده است.")
                        if not request.user.is_superuser and not request.user.has_perm("micmod_base.discount_per_item"):
                            if not (request.POST.get("manager_approved") == "1"):
                                posted_discount = amount(request.POST.get("discount_per_item", "0"))
                                if posted_discount != amount(row.discount_per_item):
                                    raise PricingError("اجازه تغییر تخفیف ردیف را ندارید.")
                        result = _save_price(row, request.POST, upgrade=upgrade)
                        row.editor_user = request.user
                        row.extra_data.request = request
                        row.save()
                        messages.success(request, "قیمت نسخه ۲ ذخیره شد. مبلغ ردیف: {:,.2f}".format(result.final_total))
                else:
                    raise PricingError("عملیات درخواستی معتبر نیست.")
        except PricingError as exc:
            messages.error(request, str(exc))
        except (ValueError, TypeError, OverflowError):
            messages.error(request, "اطلاعات ارسال‌شده معتبر نیست.")
        return redirect("micmod_base:quotation.v2", pk=pk)

    rows = _view_rows(quote)
    return render(request, "micmod-base/quotation/v2/editor.html", {
        "quote": quote,
        "rows": rows,
        "editable": editable,
        "can_discount": request.user.is_superuser or request.user.has_perm("micmod_base.discount_per_item"),
        "payment": quote.payment,
        "tax_rate": getattr(settings, "TAX_VALUE", 0),
        "legacy_url": reverse("micmod_base:quotations.view", kwargs={"pk": pk}),
        "print_url": reverse("micmod_base:quotation.print.modern", args=[pk]),
    })
