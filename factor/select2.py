from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.db.models import Q

from extra_data.models import CustomerAddress, Item, Customer
from micmod_base.models import Quotation

User = get_user_model()
SELECT2_SOURCES = {
    "address":          {"qs": CustomerAddress.objects.all(),
                         "search": ["title__icontains", "address__icontains"],
                         "filters": {"customer": "customer_id"},   # نام پارامتر GET -> lookup در ORM
                         "require_filters": ["customer"],           # اگر مشتری نبود، خالی برگردان
                        },
    "customer_party_id": {"qs": Customer.objects.all(),
                          "search": ["sepidar_dl_id__icontains",
                                     "title__icontains", "name__icontains", "last_name__icontains"],
                          "default_order": ["-id"],
                          'value_field': 'sepidar_party_id'},
    "item":             {"qs": Item.objects.all(),
                         "search": ["name__icontains", "sku__icontains"],
                         "default_order": ["-id"]},
    "checker":          {"qs": User.objects.filter(groups__name__in=['accounting_user', 'accounting_admin']).distinct(),
                         "search": ["username__icontains", "first_name__icontains", "last_name__icontains", "email__icontains"],
                         "default_order": ["-id"]},
    "wh_user":          {"qs": User.objects.filter(groups__name__in=['wh_user', 'wh_admin']).distinct(),
                         "search": ["username__icontains", "first_name__icontains", "last_name__icontains", "email__icontains"],
                         "default_order": ["-id"]},
    "q":                {"qs": Quotation.objects.all(),
                         "search": ["id", "customer_party_id__title__icontains", ],
                         "default_order": ["-id"],
                         # "filters": {"creator_user": "creator_user_id"},  # نام پارامتر GET -> lookup در ORM
                         # "require_filters": ["creator_user"],
                         }
        }


def select2_search(request, key):
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
    results = [{"id": (o.pk if vf == "pk" else getattr(o, vf)), "text": str(o)}
               for o in rows[:size]]
    return JsonResponse({"results": results, "pagination": {"more": more}})


def select2_create_factor_from_quotation(request, key):
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
    results = [{"id": (o.pk if vf == "pk" else getattr(o, vf)), "text": str(o)}
               for o in rows[:size]]
    return JsonResponse({"results": results, "pagination": {"more": more}})