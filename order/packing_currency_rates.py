"""Validation for saved Packing FX preferences (never the converted total).

Rate direction: 1 unit of a row's source currency = N units of the
selected Packing.currency. A source matching the target uses rate 1.

Schema: {'target_currency_id': '4', 'rates': {'2': '1.25000000'}}.
All values are strings to avoid silently rounding Decimal with JSON floats.
"""
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError


MAX_RATE = Decimal('1000000000000000000')
MAX_DECIMALS = Decimal('0.00000001')


def _rate(value):
    if isinstance(value, bool) or len(str(value)) > 64:
        raise ValidationError('نرخ تبدیل باید یک عدد مثبت معتبر باشد.')
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError('نرخ تبدیل باید یک عدد مثبت معتبر باشد.')
    if not number.is_finite() or not (Decimal(0) < number < MAX_RATE):
        raise ValidationError('نرخ تبدیل باید یک عدد مثبت و در محدوده مجاز باشد.')
    try:
        exact = number == number.quantize(MAX_DECIMALS)
    except InvalidOperation:
        exact = False
    if not exact:
        raise ValidationError('نرخ تبدیل نباید بیشتر از ۸ رقم اعشار داشته باشد.')
    return format(number.normalize(), 'f')


def normalize_packing_currency_rates(value, target_currency_id, valid_currency_ids=None):
    """Reject stale target IDs, unknown currency IDs and invalid rates.

    valid_currency_ids may be injected by tests; normally it is read from
    the already-small Currency catalog by the form.
    """
    if value is None or value == '':
        value = {}
    if not isinstance(value, dict):
        raise ValidationError('ساختار نرخ‌های تبدیل معتبر نیست.')
    if not value:
        return {}
    if set(value) != {'target_currency_id', 'rates'}:
        raise ValidationError('ساختار نرخ‌های تبدیل معتبر نیست.')

    target = str(target_currency_id or '')
    if not target or str(value['target_currency_id']) != target:
        raise ValidationError('ارز مقصد نرخ‌های تبدیل با ارز انتخاب‌شده یکسان نیست.')
    rates = value['rates']
    if not isinstance(rates, dict) or len(rates) > 150:
        raise ValidationError('لیست نرخ‌های تبدیل معتبر نیست.')

    known = (
        {str(pk) for pk in valid_currency_ids}
        if valid_currency_ids is not None else None
    )
    normalized = {}
    for key, raw in rates.items():
        currency_key = str(key)
        if (not currency_key.isascii() or not currency_key.isdecimal()
                or len(currency_key) > 12 or int(currency_key) <= 0
                or (known is not None and currency_key not in known)):
            raise ValidationError('یکی از ارزهای مبدا معتبر نیست.')
        if currency_key == target:
            raise ValidationError('برای ارز مقصد نیازی به ثبت نرخ تبدیل نیست.')
        if raw is None or str(raw).strip() == '':
            continue  # A rate may be supplied in a future edit.
        normalized[currency_key] = _rate(raw)
    return {'target_currency_id': target, 'rates': normalized}
