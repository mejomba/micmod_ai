"""Packing carton/Category reporting without schema changes.

A shared non-empty carton_number is one *outer* carton. carton_quantity is
the count recorded for an item row within that outer carton, not the number
of additional outer cartons.

Computed net weight and manually entered gross weight remain separate: an
incomplete set of row weights never becomes a misleading total or percentage.
"""
from collections import OrderedDict
from decimal import Decimal, InvalidOperation
import re


def carton_key(value):
    """Normalize superficial spelling differences; preserve display separately."""
    return ' '.join(str(value or '').split()).casefold()


def carton_size_key(value):
    """Equivalent separators/spaces are considered equal (40 x 30 -> 40×30)."""
    size = ' '.join(str(value or '').split()).casefold()
    return re.sub(r'\s*[×x*]\s*', 'x', size)


def _number(value):
    if value is None or str(value).strip() == '':
        return None
    try:
        number = Decimal(str(value))
        if number.is_finite() and number >= 0:
            return number
    except (InvalidOperation, TypeError, ValueError):
        pass
    return None


def _total(values):
    return sum(values, Decimal(0)) if values and all(v is not None for v in values) else None


def _percent(part, total):
    return (part * Decimal(100) / total).quantize(Decimal('0.01')) \
        if part is not None and total is not None and total > 0 else None


def _row_info(item):
    order = getattr(item, 'order', None)
    original_item = (
        getattr(order, 'item_trade', None) or getattr(order, 'item', None)
    ) if order else None
    quantity = _number(getattr(item, 'quantity', None))
    snapshot = getattr(item, 'net_weight_kg', None)
    net_weight = _number(snapshot)
    if net_weight is None and order is not None:
        unit = _number(getattr(order, 'final_weight', None))
        if unit is not None and quantity is not None:
            net_weight = unit * quantity
    category = (getattr(item, 'category', None) or '').strip()
    main_category = (getattr(item, 'main_category', None) or '').strip()
    carton = ' '.join(str(getattr(item, 'carton_number', None) or '').split())
    return {
        'id': item.pk,
        'order_number': (getattr(order, 'order_number', None) or str(order.pk))
                        if order else '—',
        'part_number': getattr(item, 'part_number', None)
                       or getattr(original_item, 'part_number', None) or '—',
        'brand': getattr(item, 'brand', None) or '—',
        'category': category or 'بدون دسته‌بندی',
        'main_category': main_category or '—',
        'carton_number': carton or '—',
        'carton_quantity': getattr(item, 'carton_quantity', None),
        'quantity': quantity,
        'net_weight': net_weight,
        'entered_weight': _number(getattr(item, 'gross_weight_kg', None)),
        'volume': _number(getattr(item, 'volume', None)),
        'size': (getattr(item, 'size', None) or '').strip() or '—',
    }


def build_carton_report(items):
    """Build independent outer-carton and Category projections from same rows."""
    cartons = OrderedDict()
    categories = OrderedDict()
    all_rows = []
    for item in items:
        row = _row_info(item)
        all_rows.append(row)
        name = row['carton_number']
        key = carton_key(name) if name != '—' else 'missing-' + str(row['id'])
        category_name = row['category']
        cartons.setdefault(key, {
            'number': name if name != '—' else 'بدون شماره (ردیف ' + str(row['id']) + ')',
            'is_unassigned': name == '—',
            'rows': [],
        })['rows'].append(row)
        categories.setdefault(category_name, {'name': category_name, 'rows': []})['rows'].append(row)

    for carton in cartons.values():
        carton_rows = carton['rows']
        # Persisted volume is a temporary test value until the real formula.
        carton_rows.sort(
            key=lambda row: (
                row['volume'] is not None,
                row['volume'] or Decimal(0),
                row['net_weight'] or Decimal(0),
                row['quantity'] or Decimal(0),
            ), reverse=True,
        )
        net_total = _total([row['net_weight'] for row in carton_rows])
        entered_total = _total([row['entered_weight'] for row in carton_rows])
        volume_total = _total([row['volume'] for row in carton_rows])
        sizes = {
            carton_size_key(row['size'])
            for row in carton_rows if row['size'] != '—'
        }
        carton.update({
            'row_count': len(carton_rows),
            'item_count': len(carton_rows),
            'size': next((row['size'] for row in carton_rows if row['size'] != '—'), '—'),
            'size_conflict': len(sizes) > 1,
            'computed_weight': net_total,
            'entered_weight': entered_total,
            'volume': volume_total,
            'main_item': carton_rows[0] if carton_rows else None,
            'row_carton_quantity': sum(
                (row['carton_quantity'] or 0) for row in carton_rows
            ),
        })
        for row in carton_rows:
            row['net_percent'] = _percent(row['net_weight'], net_total)
            row['entered_percent'] = _percent(row['entered_weight'], entered_total)
    for category in categories.values():
        category['row_count'] = len(category['rows'])
        category['quantity'] = _total([r['quantity'] for r in category['rows']])
        category['cartons_count'] = len({
            carton_key(r['carton_number'])
            for r in category['rows'] if r['carton_number'] != '—'
        })
        category['rows'].sort(key=lambda r: (r['carton_number'], r['part_number']))

    carton_list = list(cartons.values())
    return {
        'cartons': carton_list,
        'category_groups': list(categories.values()),
        'unique_carton_count': sum(not c['is_unassigned'] for c in carton_list),
        'unassigned_row_count': sum(c['is_unassigned'] for c in carton_list),
        'size_conflicts': sum(c['size_conflict'] for c in carton_list),
    }
