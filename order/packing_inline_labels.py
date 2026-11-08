"""Independent inline Packing autocomplete labels and server-side validation."""
from extra_data.models import Brand
from .models import PackingItem


LABEL_LIMITS = {'category': 150, 'main_category': 150, 'brand': 150}


def normalize_packing_label(kind, value):
    if kind not in LABEL_LIMITS:
        raise ValueError('فیلد انتخاب‌شده معتبر نیست.')
    result = ' '.join(str(value or '').split())
    if len(result) > LABEL_LIMITS[kind]:
        raise ValueError(f'مقدار {kind} از حداکثر طول مجاز بیشتر است.')
    if any(ord(char) < 32 for char in result):
        raise ValueError(f'مقدار {kind} دارای کاراکتر نامعتبر است.')
    return result or None


def packing_label_suggestions(kind, query):
    """Suggestions are independent; neither category constrains the other."""
    if kind not in LABEL_LIMITS:
        return []
    query = str(query or '').strip()[:100]
    if kind == 'brand':
        return list(
            Brand.objects.filter(title__icontains=query)
            .order_by('title').values_list('title', flat=True)[:30]
        )
    return list(
        PackingItem.objects.filter(
            is_deleted=False, **{f'{kind}__icontains': query}
        )
        .exclude(**{f'{kind}__isnull': True}).exclude(**{kind: ''})
        .order_by(kind).values_list(kind, flat=True).distinct()[:30]
    )
