"""Server-calculated financial and diversity totals for sales history.

The full filtered snapshot is processed on the server, never sent to the
browser. Monetary values remain separated by normalized currency; no
cross-currency total is ever computed. Values use 6-place scaled integers
(as strings) for exact display in JavaScript without floating-point drift.
"""
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
import re
import unicodedata

from .sales_history_service import get_sales_history_list


SCALE = Decimal('1000000')


def _scaled(value):
    try:
        value = Decimal(str(value if value is not None else 0))
        if not value.is_finite():
            return 0
        return int((value * SCALE).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except (ValueError, TypeError, ArithmeticError):
        return 0


def _currency(value):
    original = str(value or '').strip()
    norm = unicodedata.normalize('NFKC', original)
    norm = norm.replace('ي', 'ی').replace('ى', 'ی').replace('ك', 'ک')
    norm = re.sub(r'[\u200c-\u200f\u202a-\u202e\u2066-\u2069]', '', norm)
    norm = re.sub(r'[ًٌٍَُِّْـ]', '', norm)
    norm = re.sub(r'\s+', ' ', norm).strip().lower()
    compact = re.sub(r'[\s()\[\]._\-/:]', '', norm)
    names = {
        'IRR': {'ریال', 'ریالایران', 'ریالایرانی', 'ریالirr', 'ریالrial',
                'rial', 'rials', 'irr', 'irrrial', 'rialirr', 'iranianrial', 'iranrial'},
        'CNY': {'یوان', 'یوانچین', 'یوانrmb', 'یوانcny', 'rmb', 'cny',
                'yuan', 'chineseyuan', 'renminbi'},
        'USD': {'دلار', 'دلارآمریکا', 'دلارusd', 'usd', 'usdol',
                'usdollar', 'usddollar', 'unitedstatesdollar'},
        'EUR': {'یورو', 'euro', 'eur', 'ero'},
        'AED': {'درهم', 'درهمامارات', 'aed', 'emiratesdirham', 'uaedirham'},
    }
    labels = {
        'IRR': 'ریال (IRR)', 'CNY': 'یوان (RMB/CNY)', 'USD': 'دلار (USD)',
        'EUR': 'یورو (EUR)', 'AED': 'درهم (AED)',
    }
    for key, aliases in names.items():
        if compact in aliases:
            return key, labels[key]
    if not compact:
        return 'UNKNOWN', 'ارز نامشخص'
    return norm, original.replace('ي', 'ی').replace('ك', 'ک')


def _unique(value):
    norm = unicodedata.normalize('NFKC', str(value or '')).strip()
    norm = norm.replace('ي', 'ی').replace('ى', 'ی').replace('ك', 'ک')
    norm = re.sub(r'[\u200c-\u200f\u202a-\u202e]', '', norm)
    norm = re.sub(r'\s+', ' ', norm).strip().casefold()
    return '' if norm in ('', '-', '—', 'none') else norm


def summarize_sales_history(rows, truncated=False):
    """Calculate totals across all filtered server rows, not loaded scroll rows."""
    currencies = {}
    unique = {name: set() for name in ('document', 'customer', 'item', 'purchase', 'sales')}
    sources = {'sepidar': 0, 'portal': 0}
    qty_total = 0
    for row in rows:
        source = str(row.get('source') or '').lower()
        if source in sources:
            sources[source] += 1
        doc = _unique(row.get('Number'))
        if doc:
            unique['document'].add((source, _unique(row.get('doc_type')),
                                    _unique(row.get('year_title')), doc))
        for name, field in (
            ('customer', 'customer_code'), ('item', 'item_code'),
            ('purchase', 'purchase_group'), ('sales', 'sales_group'),
        ):
            value = _unique(row.get(field))
            if value:
                unique[name].add(value)

        qty = _scaled(row.get('Quantity'))
        fee = _scaled(row.get('Fee'))
        price = _scaled(row.get('Price'))
        qty_total += qty
        key, label = _currency(row.get('currency'))
        if key not in currencies:
            currencies[key] = {'key': key, 'label': label,
                               'value': 0, 'weight': 0, 'feeWeighted': 0}
        bucket = currencies[key]
        bucket['value'] += price
        bucket['weight'] += abs(qty)
        bucket['feeWeighted'] += fee * abs(qty)

    # No float values cross the JSON boundary.
    result = []
    for bucket in currencies.values():
        result.append({key: str(value) if isinstance(value, int) else value
                       for key, value in bucket.items()})
    return {
        'currencies': sorted(result, key=lambda b: b['key']),
        'quantity_scaled': str(qty_total),
        'sources': sources,
        'distinct': {k: len(v) for k, v in unique.items()},
        'row_count': len(rows),
        'truncated': bool(truncated),
    }


def get_sales_history_summary(filters):
    rows, truncated = get_sales_history_list(filters)
    return summarize_sales_history(rows, truncated=truncated)
