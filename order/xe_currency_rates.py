"""Read Xe mid-market currency quotes through the authenticated XE Data API.

No HTML scraping and no user-visible credentials. Xe responds to requests
from a *base* currency to counter currencies. Packing expects the inverse
direction: 1 unit of each row currency expressed in Packing.currency.

Only rates explicitly saved through the existing PackingSafeForm persist.
This module never writes Packing objects or converted totals.
"""
from decimal import Decimal, InvalidOperation
import hashlib
import re

import requests
from django.conf import settings
from django.core.cache import cache


XE_URL = 'https://xecdapi.xe.com/v1/convert_from.json/'
XE_ISO_PATTERN = re.compile(r'^[A-Z]{3}$')
XE_CODE_ALIASES = {'RMB': 'CNY'}
RATE_PRECISION = Decimal('0.00000001')
MAX_RATE = Decimal('1000000000000000000')


class XeRateError(Exception):
    def __init__(self, message, *, status_code=502, code='xe_error'):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


def xe_configured():
    return bool(
        getattr(settings, 'XE_CURRENCY_API_KEY', '')
        or (
            getattr(settings, 'XE_CURRENCY_USERNAME', '')
            and getattr(settings, 'XE_CURRENCY_PASSWORD', '')
        )
    )


def xe_iso_code(currency):
    """Map an internal Currency.title_en to a supported ISO request code.

    Avoid guesswork for custom non-ISO currencies (e.g. Toman); such rows
    remain editable manually and are excluded from the provider request.
    """
    code = str(currency or '').strip().upper()
    code = XE_CODE_ALIASES.get(code, code)
    return code if XE_ISO_PATTERN.fullmatch(code) else None


def _valid_inverse(raw):
    try:
        mid = Decimal(str(raw))
        if not mid.is_finite() or mid <= 0:
            return None
        rate = (Decimal(1) / mid).quantize(RATE_PRECISION)
        if not rate.is_finite() or rate <= 0 or rate >= MAX_RATE:
            return None
        return format(rate.normalize(), 'f')
    except (InvalidOperation, ValueError, TypeError, ArithmeticError):
        return None


def _get_xe_quotes(base, counters):
    """Return independent mid-market quotes with a short, bounded cache."""
    if not xe_configured():
        raise XeRateError(
            'اتصال XE هنوز تنظیم نشده است. برای فعال‌سازی API Key سرویس را تنظیم کنید.',
            status_code=503, code='not_configured',
        )
    code_list = sorted(set(counters) - {base})
    if not code_list:
        return {'rates': {}, 'timestamp': None, 'cached': False}
    if len(code_list) > 20:
        raise XeRateError('تعداد ارزهای درخواستی بیش از حد مجاز است.',
                          status_code=400, code='too_many_currencies')

    cache_key = 'packing:xe:v1:' + hashlib.sha256(
        (base + '|' + ','.join(code_list)).encode('ascii')
    ).hexdigest()
    cached = cache.get(cache_key)
    if isinstance(cached, dict):
        return {**cached, 'cached': True}

    key = getattr(settings, 'XE_CURRENCY_API_KEY', '') or ''
    auth = None
    headers = {'Accept': 'application/json'}
    if key:
        headers['Authorization'] = 'Bearer ' + key
    else:
        auth = (
            getattr(settings, 'XE_CURRENCY_USERNAME', ''),
            getattr(settings, 'XE_CURRENCY_PASSWORD', ''),
        )
    try:
        response = requests.get(
            XE_URL,
            params={'from': base, 'to': ','.join(code_list), 'amount': '1'},
            headers=headers,
            auth=auth,
            timeout=(3, 8),
        )
    except requests.RequestException as exc:
        raise XeRateError('ارتباط با سرویس XE برقرار نشد. نرخ‌ها را می‌توانید دستی وارد کنید.',
                          code='connection_failed') from exc

    if response.status_code in (401, 403):
        raise XeRateError(
            'دسترسی به Xe Currency Data API مجاز نیست؛ اعتبار API Key و سهمیه را بررسی کنید.',
            status_code=503, code='xe_auth_or_quota',
        )
    if response.status_code == 429:
        raise XeRateError(
            'تعداد درخواست‌های XE بیش از حد مجاز است؛ بعداً تلاش کنید.',
            status_code=503, code='xe_rate_limited',
        )
    if response.status_code != 200:
        raise XeRateError(
            'XE پاسخ معتبر نداد؛ نرخ‌های دستی قابل استفاده هستند.',
            status_code=502, code='xe_unavailable',
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise XeRateError('پاسخ نرخ XE معتبر نیست.', code='xe_invalid_response') from exc
    if not isinstance(payload, dict) or payload.get('from') != base:
        raise XeRateError('مبنای ارز در پاسخ XE با درخواست یکسان نیست.',
                          code='xe_invalid_response')
    entries = payload.get('to')
    if not isinstance(entries, list):
        raise XeRateError('فهرست نرخ‌های XE معتبر نیست.',
                          code='xe_invalid_response')
    rates = {}
    for item in entries:
        if not isinstance(item, dict):
            continue
        quote_code = item.get('quotecurrency')
        if quote_code not in code_list:
            continue
        inverse = _valid_inverse(item.get('mid'))
        if inverse is not None:
            rates[quote_code] = inverse

    result = {
        'rates': rates,
        'timestamp': str(payload.get('timestamp') or '')[:40] or None,
        'cached': False,
    }
    try:
        ttl = max(30, min(int(getattr(settings, 'XE_RATES_CACHE_SECONDS', 300)), 1800))
    except (TypeError, ValueError):
        ttl = 300
    if rates:
        cache.set(cache_key, result, timeout=ttl)
    return result
