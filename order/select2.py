from django.db.models import Q
from django.http import JsonResponse

from extra_data.models import Customer, Item
from inquiry.models import Supplier, PriceInquiryResult
from micmod_base.models import Quotation, QuotationItem
from django.contrib.auth import get_user_model

SELECT2_SOURCES = {
    "customer_party_id": {"qs": Customer.objects.all(),
                          "search": ["sepidar_dl_id__icontains", "sepidar_dl_code__icontains",
                                     "title__icontains", "name__icontains", "last_name__icontains"],
                          "default_order": ["-id"],
                          'value_field': 'sepidar_party_id'},

    "item":             {"qs": Item.objects.all(),
                         "search": ["part_number__icontains", "sku__icontains"],
                         "default_order": ["-id"]},

    "supplier":          {"qs": Supplier.objects.all(),
                          "search": ["title__icontains"],
                          "default_order": ["-id"]},

    "trade_user":        {"qs": get_user_model().objects.filter(groups__name='trade_user'),
                          "search": ["first_name__icontains", "username__icontains"],
                          "default_order": ["-id"]},

    "inquiry":           {"qs": PriceInquiryResult.objects.filter(creator_user__groups__name='trade_user', active=True),
                          "search": ["sku__sku"],
                          "default_order": ["-id"]},

    "qi":                {"qs": QuotationItem.objects.all(),
                          "search": ["id", "goods_code_fk_id", "goods_code_fk__part_number"],
                          "default_order": ["-id"],
                          "filters": {"user_id": "customer_party_id__customer_group__current_user_id",},  # نام پارامتر GET -> lookup در ORM
                          "require_filters": [],  # اگر کالا نبود، خالی برگردان
                          }
        }


def order_select2_search(request, key):
    src = SELECT2_SOURCES.get(key)
    if not src:
        return JsonResponse({"results": [], "pagination": {"more": False}})

    qs = src["qs"]
    for param, lookup in src.get("filters", {}).items():       # فیلتر مشتری فاکتور
        val = request.GET.get(param)
        if val:
            qs = qs.filter(**{lookup: val})
        elif param in src.get("require_filters", []):
            return JsonResponse({"results": [], "pagination": {"more": False}})

    q = request.GET.get("q", "").strip()
    if q:
        cond = Q()
        for f in src["search"]:
            cond |= Q(**{f: q})
        qs = qs.filter(cond)
    elif src.get("default_order"):
        qs = qs.order_by(*src["default_order"])

    page = max(int(request.GET.get("page", 1)), 1)
    size = src.get("page_size", 20)
    rows = list(qs[(page - 1) * size: page * size + 1])
    more = len(rows) > size
    vf = src.get("value_field", "pk")
    results = [{"id": (o.pk if vf == "pk" else getattr(o, vf)), "text": getattr(o, 'select2_html_respo_text', None) or str(o)}
               for o in rows[:size]]
    return JsonResponse({"results": results, "pagination": {"more": more}})
