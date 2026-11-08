"""One size per outer carton (carton_number), across existing and new rows.

This service is independent of the browser; saves are validated within the
Packing transaction against locked, non-deleted PackingItem records.
"""
from collections import defaultdict

from .packing_carton_report import carton_key, carton_size_key


def normalize_carton_text(value):
    return ' '.join(str(value or '').split())


def reconcile_carton_sizes(saved_items, edited_rows, new_rows):
    """Validate final carton sizes, fill missing sizes, return persisted fixes.

    Edited and new row dictionaries may be modified in place. Persisted
    items with blank sizes that share a known size are returned as (item, size)
    pairs so callers can save them with normal audit attribution.
    """
    posted = {row['id']: row for row in edited_rows}
    groups = defaultdict(list)
    touched = set()
    fills = []
    for item in saved_items:
        row = posted.get(item.pk)
        if row is not None and row.get('delete'):
            continue
        old_number = normalize_carton_text(item.carton_number)
        old_size = normalize_carton_text(item.size)
        number = normalize_carton_text(row.get('carton_number', old_number) if row else old_number)
        size = normalize_carton_text(row.get('size', old_size) if row else old_size)
        old_key, key = carton_key(old_number), carton_key(number)
        if row is not None and (old_key != key or carton_size_key(old_size) != carton_size_key(size)):
            if old_key:
                touched.add(old_key)
            if key:
                touched.add(key)
        if key:
            groups[key].append({'item': item, 'row': row, 'size': size, 'number': number})
    for row in new_rows:
        number = normalize_carton_text(row.get('carton_number'))
        size = normalize_carton_text(row.get('size'))
        key = carton_key(number)
        if key:
            groups[key].append({'item': None, 'row': row, 'size': size, 'number': number})
            touched.add(key)

    for key, entries in groups.items():
        if key not in touched:
            continue  # Do not block unrelated edits due to old legacy data.
        defined = {}
        for entry in entries:
            size = entry['size']
            if size:
                defined.setdefault(carton_size_key(size), size)
        number = entries[0]['number']
        if len(defined) > 1:
            raise ValueError(
                f'شماره کارتن «{number}» دارای سایزهای متفاوت است. '
                'سایز تمام ردیف‌های این کارتن باید یکسان باشد.'
            )
        if not defined:
            raise ValueError(
                f'برای شماره کارتن «{number}» باید یک سایز ثبت شود.'
            )
        size = next(iter(defined.values()))
        for entry in entries:
            if entry['size']:
                continue
            if entry['row'] is not None:
                entry['row']['size'] = size
            elif entry['item'] is not None:
                fills.append((entry['item'], size))
    return fills
