"""Four-sheet, carton-oriented Excel export for Quick Packing.

The workbook mirrors the approved PL / Summary / Invoice / Packing List layout.
All financial values are converted only from the rates saved on the Packing;
the exporter never fetches or invents an exchange rate.
"""
from collections import OrderedDict, defaultdict
from decimal import Decimal, InvalidOperation
from io import BytesIO
import re

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from .packing_volume import resolve_packing_volume


XLSX_CONTENT_TYPE = (
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
)

SENSITIVE_MAIN_CATEGORIES = {
    'fuse': 'Fuse',
    'lcd display': 'LCD Display',
    'sensor': 'Sensor',
    'telescopic antenna': 'Telescopic antenna',
    'ic-memory': 'IC-Memory',
}

REFERENCE_CATEGORY_ORDER = [
    'SMD Electronic Components',
    'Diode & Transistor',
    'Connector',
    'Capacitor',
    'SMD Resistor',
    'SMD ICs',
    'PCB',
    'Relay',
    'GSM Module',
]

CURRENCY_ALIASES = {
    'RMB': 'CNY',
    'RENMINBI': 'CNY',
    'YUAN': 'CNY',
    'DOLLAR': 'USD',
    'ERO': 'EUR',
    'EMIRATES DIRHAM': 'AED',
}


def _decimal(value):
    if value is None or str(value).strip() == '':
        return None
    try:
        number = Decimal(str(value).strip())
        return number if number.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _text(value):
    return '' if value is None else str(value).strip()


def _safe_get(obj, name, default=None):
    if obj is None:
        return default
    try:
        return getattr(obj, name, default)
    except Exception:
        return default


def _related_title(value):
    if value is None:
        return ''
    if isinstance(value, str):
        return value.strip()
    return (
        _text(_safe_get(value, 'title'))
        or _text(_safe_get(value, 'name'))
        or _text(value)
    )


def _currency_code(currency):
    raw = _text(_safe_get(currency, 'title_en') or _safe_get(currency, 'title'))
    normalized = re.sub(r'\s+', ' ', raw).upper()
    return CURRENCY_ALIASES.get(normalized, normalized)


def _currency_id(currency, fallback=None):
    value = _safe_get(currency, 'pk') or _safe_get(currency, 'id') or fallback
    return str(value) if value not in (None, '') else ''


def _natural_key(value):
    return tuple(
        int(part) if part.isdigit() else part.casefold()
        for part in re.split(r'(\d+)', _text(value))
    )


def _size_key(value):
    size = re.sub(r'\s+', '', _text(value)).casefold()
    return re.sub(r'[×x*]', 'x', size)


def _first_nonempty(values):
    return next((value for value in values if value not in (None, '')), None)


def _sum_available(values):
    """Excel SUM semantics: ignore blanks, but do not invent a zero total."""
    available = [value for value in values if value is not None]
    return sum(available, Decimal('0')) if available else None


def _sum_complete(values):
    if not values or any(value is None for value in values):
        return None
    return sum(values, Decimal('0'))


def _representative(values):
    """Most common non-empty value; ties keep the first encountered value."""
    counts = OrderedDict()
    for value in values:
        value = _text(value)
        if value:
            key = _size_key(value)
            counts[key] = counts.get(key, [0, value])
            counts[key][0] += 1
    if not counts:
        return ''
    return max(counts.values(), key=lambda item: item[0])[1]


def _product_for_order(order):
    product = _safe_get(order, 'final_item')
    if product is None:
        product = _safe_get(order, 'item_trade') or _safe_get(order, 'item')
    return product


def _item_data(item):
    order = _safe_get(item, 'order')
    product = _product_for_order(order)

    quantity = _decimal(_safe_get(item, 'quantity'))
    saved_calculated_weight = _decimal(_safe_get(item, 'net_weight_kg'))
    if quantity == 0:
        calculated_weight = Decimal('0')
    elif saved_calculated_weight is not None and saved_calculated_weight > 0:
        # The saved net weight is already the product-derived row snapshot.
        calculated_weight = saved_calculated_weight
    else:
        unit_weight = _decimal(_safe_get(order, 'final_weight')) if order else None
        calculated_weight = (
            unit_weight * quantity
            if unit_weight is not None and unit_weight > 0 and quantity is not None
            else None
        )

    size = _safe_get(item, 'size')
    try:
        volume = resolve_packing_volume(
            _safe_get(item, 'volume'),
            size=size,
            is_confirmed=bool(_safe_get(item, 'volume_is_confirmed', False)),
        )
    except (ValueError, TypeError, InvalidOperation):
        volume = None
    volume = _decimal(volume)

    order_brand = _safe_get(order, 'brand') if order else None
    row_brand = _safe_get(item, 'brand')
    product_brand = _safe_get(product, 'brand')
    brand = (
        _related_title(order_brand)
        or _related_title(row_brand)
        or _related_title(product_brand)
    )

    purchase_group_obj = _safe_get(product, 'purchase_group')
    purchase_group = _related_title(purchase_group_obj)

    hs_obj = _safe_get(product, 'hs')
    if hs_obj is None:
        hs_obj = _safe_get(purchase_group_obj, 'hs')
    hs_code = _text(_safe_get(hs_obj, 'code'))

    part_number = (
        _text(_safe_get(item, 'part_number'))
        or _text(_safe_get(product, 'part_number'))
        or _text(_safe_get(order, 'part_number_mac'))
    )
    description = (
        _text(_safe_get(item, 'description'))
        or _text(_safe_get(order, 'description_trade'))
        or _text(_safe_get(order, 'description_sale'))
    )

    currency = _safe_get(order, 'currency') if order else None
    unit_price = _decimal(_safe_get(item, 'price'))
    if unit_price is None and order is not None:
        unit_price = _decimal(_safe_get(order, 'final_price'))

    return {
        'pk': _safe_get(item, 'pk'),
        'order_number': (
            _text(_safe_get(order, 'order_number'))
            or _text(_safe_get(order, 'pk'))
        ) if order else '',
        'carton_number': _text(_safe_get(item, 'carton_number')),
        'carton_quantity': _decimal(_safe_get(item, 'carton_quantity')),
        'brand': brand,
        'category': _text(_safe_get(item, 'category')),
        'main_category': _text(_safe_get(item, 'main_category')),
        'description': description,
        'part_number': part_number,
        'sku': _text(_safe_get(product, 'sku')),
        'purchase_group': purchase_group,
        'quantity': quantity,
        'declared_weight': _decimal(_safe_get(item, 'gross_weight_kg')),
        'size': _text(size),
        'volume': volume,
        'calculated_weight': calculated_weight,
        'unit_price': unit_price,
        'currency': currency,
        'currency_id': _currency_id(
            currency, _safe_get(order, 'currency_id') if order else None
        ),
        'currency_code': _currency_code(currency),
        'hs_code': hs_code,
        'duty_date': (
            _safe_get(item, 'duty_date')
            or _safe_get(product, 'duty_date')
        ),
        'carton_weight': _decimal(
            _first_nonempty([
                _safe_get(item, 'cartone_weight_kg'),
                _safe_get(item, 'carton_weight_kg'),
                _safe_get(item, 'carton_weight'),
            ])
        ),
    }


def _carton_groups(rows):
    groups = OrderedDict()
    for index, row in enumerate(rows):
        carton = row['carton_number']
        key = _size_key(carton) if carton else f'__unassigned_{index}'
        groups.setdefault(key, []).append(row)
    return groups


def _carton_volume(group):
    """A carton has one volume, even when it contains several item rows."""
    representative_size = _representative(row['size'] for row in group)
    if not representative_size:
        return None
    matching = [
        row for row in group
        if _size_key(row['size']) == _size_key(representative_size)
    ]
    return _first_nonempty(row['volume'] for row in matching)


def _carton_summary(group):
    rows = list(group)
    quantities_by_main = OrderedDict()
    for row in rows:
        name = row['main_category'] or 'Uncategorized'
        quantities_by_main.setdefault(name, Decimal('0'))
        if row['quantity'] is not None:
            quantities_by_main[name] += row['quantity']

    categories = {
        row['category'].casefold()
        for row in rows if row['category']
    }
    max_category = ''
    primary_category = ''
    if quantities_by_main:
        max_category = max(
            quantities_by_main.items(), key=lambda pair: pair[1]
        )[0]
        primary_row = next(
            (row for row in rows if (row['main_category'] or 'Uncategorized') == max_category),
            rows[0],
        )
        primary_category = primary_row['category'] or max_category
    if len(quantities_by_main) <= 1:
        max_category = ''

    carton_quantity = _sum_available(
        [row['carton_quantity'] for row in rows]
    )
    return {
        'rows': rows,
        'number': rows[0]['carton_number'],
        'carton_quantity': carton_quantity,
        'calculated_weight': _sum_available(
            [row['calculated_weight'] for row in rows]
        ),
        'declared_weight': _sum_available(
            [row['declared_weight'] for row in rows]
        ),
        'volume': _carton_volume(rows),
        'carton_weight': _first_nonempty(
            row['carton_weight'] for row in rows
        ),
        'size': _representative(row['size'] for row in rows),
        'mixed': len(categories) > 1,
        'max_category': max_category,
        'primary_category': primary_category,
    }


def _fx_context(packing, rows):
    saved = _safe_get(packing, 'currency_exchange_rates') or {}
    if not isinstance(saved, dict):
        saved = {}
    target_currency = _safe_get(packing, 'currency')
    target_id = _currency_id(
        target_currency, _safe_get(packing, 'currency_id')
    )
    saved_target_id = str(saved.get('target_currency_id') or '')
    rates = saved.get('rates') if isinstance(saved.get('rates'), dict) else {}
    if not target_id or saved_target_id != target_id:
        rates = {}

    target_code = _currency_code(target_currency)
    currencies = {}
    for row in rows:
        if row['currency_id'] and row['currency_code']:
            currencies.setdefault(row['currency_code'], row['currency_id'])

    def rate_to_target(currency_id, currency_code=''):
        if not target_id:
            return None
        if currency_id and currency_id == target_id:
            return Decimal('1')
        if currency_code and currency_code == target_code:
            return Decimal('1')
        raw = rates.get(str(currency_id)) if currency_id else None
        return _decimal(raw)

    cny_id = currencies.get('CNY')
    usd_id = currencies.get('USD')
    cny_to_target = rate_to_target(cny_id, 'CNY') if cny_id else (
        Decimal('1') if target_code == 'CNY' else None
    )
    usd_to_target = rate_to_target(usd_id, 'USD') if usd_id else (
        Decimal('1') if target_code == 'USD' else None
    )
    cny_to_usd = None
    if cny_to_target is not None and usd_to_target is not None and usd_to_target > 0:
        cny_to_usd = cny_to_target / usd_to_target

    return {
        'target_id': target_id,
        'target_code': target_code,
        'target_currency': target_currency,
        'rates': rates,
        'rate_to_target': rate_to_target,
        'cny_to_usd': cny_to_usd,
        'has_saved_rates': bool(rates),
    }


def _convert_amount(amount, row, fx):
    if amount is None:
        return None, None
    source_id = row['currency_id']
    source_code = row['currency_code']
    rate_to_target = fx['rate_to_target'](source_id, source_code)
    if rate_to_target is None:
        if source_code == 'CNY':
            return amount, None
        if source_code == 'USD':
            return None, amount
        return None, None

    target_amount = amount * rate_to_target
    cny_id = fx.get('cny_id')
    usd_id = fx.get('usd_id')
    if cny_id:
        cny_to_target = fx['rate_to_target'](cny_id, 'CNY')
    else:
        cny_to_target = Decimal('1') if fx['target_code'] == 'CNY' else None
    if usd_id:
        usd_to_target = fx['rate_to_target'](usd_id, 'USD')
    else:
        usd_to_target = Decimal('1') if fx['target_code'] == 'USD' else None

    cny = (
        target_amount / cny_to_target
        if cny_to_target is not None and cny_to_target > 0 else None
    )
    usd = (
        target_amount / usd_to_target
        if usd_to_target is not None and usd_to_target > 0 else None
    )
    return cny, usd


def _prepare_financial_rows(rows, packing, include_prices):
    fx = _fx_context(packing, rows)
    if not include_prices:
        for row in rows:
            row.update({
                'amount': None, 'unit_price_cny': None, 'amount_cny': None,
                'unit_price_usd': None, 'amount_usd': None,
            })
        return fx

    fx['cny_id'] = next(
        (row['currency_id'] for row in rows if row['currency_code'] == 'CNY'),
        None,
    )
    fx['usd_id'] = next(
        (row['currency_id'] for row in rows if row['currency_code'] == 'USD'),
        None,
    )

    for row in rows:
        amount = (
            row['unit_price'] * row['quantity']
            if row['unit_price'] is not None and row['quantity'] is not None
            else None
        )
        unit_cny, unit_usd = _convert_amount(row['unit_price'], row, fx)
        amount_cny, amount_usd = _convert_amount(amount, row, fx)
        row.update({
            'amount': amount,
            'unit_price_cny': unit_cny,
            'amount_cny': amount_cny,
            'unit_price_usd': unit_usd,
            'amount_usd': amount_usd,
        })
    return fx


def _style_cell(cell, *, fill='FFFFFFFF', bold=False, color='FF202934',
                size=8, number_format=None, horizontal='center'):
    cell.font = Font(name='Aptos', size=size, bold=bold, color=color)
    cell.fill = PatternFill('solid', fgColor=fill)
    cell.alignment = Alignment(
        horizontal=horizontal, vertical='center', wrap_text=True,
    )
    thin = Side(style='thin', color='FFD5DEE7')
    cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
    if number_format:
        cell.number_format = number_format


def _style_range(ws, min_row, max_row, min_col, max_col, *,
                 fill='FFFFFFFF', bold=False, size=8):
    for row in ws.iter_rows(
        min_row=min_row, max_row=max_row,
        min_col=min_col, max_col=max_col,
    ):
        for cell in row:
            _style_cell(cell, fill=fill, bold=bold, size=size)


def _style_header(ws, row=1, max_col=None):
    max_col = max_col or ws.max_column
    _style_range(
        ws, row, row, 1, max_col,
        fill='FFDDEBF5', bold=True,
    )
    ws.row_dimensions[row].height = 32


def _format_number(cell, pattern='#,##0.0000'):
    if cell.value is not None:
        cell.number_format = pattern


def _sheet_title(packing):
    number = _text(_safe_get(packing, 'packing_number')) or 'Packing'
    shipment = _text(_safe_get(packing, 'shipment_type')).upper()
    title = f'{number} {shipment}'.strip() if shipment else number
    title = re.sub(r'[\[\]:*?/\\]', '-', title)
    return title[:31]


def _main_sheet(workbook, packing, rows, cartons, include_prices):
    ws = workbook.active
    ws.title = _sheet_title(packing)
    ws.sheet_view.showGridLines = False
    headers = [
        'Ctn NMMO#.', 'Carton No.', 'Description', 'Brand', 'Name or PN.',
        'Purchase Group', 'Main Category', 'Category', 'Our Weight', 'Max',
        'QTY (PCS)', 'SIZE (CM)', 'WEIGHT (kg)', 'Volume(CBM)',
        'Unit Price (CNY)', 'Amount (CNY)', 'Unit Price (USD)',
        'Amount (USD)', 'Order No', 'SKU', 'duty date', 'Item Weight (kg)',
        'HS', 'Cartone Weight', 'Carton audit (internal)',
    ]
    ws.append(headers)
    _style_header(ws, 1, len(headers))
    widths = {
        'A': 14, 'B': 10, 'C': 20, 'D': 13, 'E': 30, 'F': 19,
        'G': 21, 'H': 21, 'I': 12, 'J': 24, 'K': 13, 'L': 14,
        'M': 14, 'N': 14, 'O': 14, 'P': 15, 'Q': 14, 'R': 15,
        'S': 12, 'T': 10, 'U': 12, 'V': 14, 'W': 12, 'X': 13, 'Y': 17,
    }
    for column, width in widths.items():
        ws.column_dimensions[column].width = width

    current_row = 2
    for carton_key, group in cartons.items():
        group_start = current_row
        summary = _carton_summary(group)
        carton_number = summary['number']
        max_label = (
            f"{carton_number} / {summary['max_category']}"
            if summary['max_category'] and carton_number else ''
        )
        for index, row in enumerate(group):
            data = [
                carton_number if index == 0 else None,
                summary['carton_quantity'] if index == 0 else None,
                row['description'],
                row['brand'],
                row['part_number'],
                row['purchase_group'],
                row['main_category'],
                row['category'],
                row['declared_weight'],
                max_label,
                row['quantity'],
                row['size'],
                summary['calculated_weight'] if index == 0 else None,
                summary['volume'] if index == 0 else None,
                row['unit_price_cny'] if include_prices else None,
                row['amount_cny'] if include_prices else None,
                row['unit_price_usd'] if include_prices else None,
                row['amount_usd'] if include_prices else None,
                row['order_number'],
                row['sku'],
                row['duty_date'],
                row['calculated_weight'],
                row['hs_code'],
                summary['carton_weight'] if index == 0 else None,
                '1|' if index == 0 and carton_number else '',
            ]
            ws.append(data)
            fill = 'FFFAFBFD' if len(group) > 1 else 'FFFFFFFF'
            for cell in ws[current_row]:
                _style_cell(cell, fill=fill)
            current_row += 1

        group_end = current_row - 1
        if carton_number and group_end > group_start:
            for column in (1, 2, 13, 14, 24):
                ws.merge_cells(
                    start_row=group_start, start_column=column,
                    end_row=group_end, end_column=column,
                )
                top = ws.cell(group_start, column)
                top.alignment = Alignment(
                    horizontal='center', vertical='center', wrap_text=True,
                )
                top.fill = PatternFill('solid', fgColor='FFF6F1FB')
                top.border = Border(
                    left=Side(style='thin', color='FFD5DEE7'),
                    right=Side(style='thin', color='FFD5DEE7'),
                    top=Side(style='thin', color='FFD5DEE7'),
                    bottom=Side(style='thin', color='FFD5DEE7'),
                )

    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = f'A1:Y{ws.max_row}'
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.print_title_rows = '1:1'
    for row in range(2, ws.max_row + 1):
        for col in (9, 13, 22, 24):
            _format_number(ws.cell(row, col), '#,##0.0000')
        _format_number(ws.cell(row, 11), '#,##0')
        _format_number(ws.cell(row, 14), '#,##0.000000')
        for col in (15, 17):
            _format_number(ws.cell(row, col), '#,##0.00000000')
        for col in (16, 18):
            _format_number(ws.cell(row, col), '#,##0.00')
    return ws


def _summary_sheet(workbook, packing, rows, cartons, fx, include_prices):
    ws = workbook.create_sheet('Summary')
    ws.sheet_view.showGridLines = False
    title = _sheet_title(packing)
    ws.merge_cells('A1:D1')
    ws['A1'] = f'{title}  |  CARGO OVERVIEW'
    _style_range(ws, 1, 1, 1, 4, fill='FFDDEBF5', bold=True)
    ws.row_dimensions[1].height = 26
    ws.merge_cells('A3:B3')
    ws.merge_cells('C3:D3')
    ws['A3'] = 'EXCHANGE RATE'
    ws['C3'] = 'CARGO INFORMATION'
    _style_range(ws, 3, 3, 1, 2, fill='FFEBF4FA', bold=True)
    _style_range(ws, 3, 3, 3, 4, fill='FFE4F3EE', bold=True)

    cny_to_usd = fx.get('cny_to_usd')
    exchange_rows = [
        ('Exchange source', 'XE.com' if include_prices and fx.get('has_saved_rates') else ''),
        ('1 CNY → USD', cny_to_usd if include_prices and cny_to_usd is not None else ''),
        ('Rate date', ''),  # The current Packing FX schema does not persist a date.
        ('Quote pair', 'CNY → USD' if include_prices and cny_to_usd is not None else ''),
        ('Quote mode', 'Saved / editable' if include_prices and fx.get('has_saved_rates') else ''),
        ('Sensitive lines', None),
        ('Missing weight lines', sum(
            1 for row in rows if row['calculated_weight'] is None
        )),
        ('Packing origin', _safe_get(packing, 'origin') or ''),
    ]

    sensitive_rows = []
    for row in rows:
        reason = SENSITIVE_MAIN_CATEGORIES.get(row['main_category'].casefold())
        if reason:
            sensitive_rows.append((
                row['carton_number'],
                row['part_number'] or row['description'],
                row['quantity'],
                reason,
            ))
    exchange_rows[5] = ('Sensitive lines', len(sensitive_rows))

    carton_count = len({
        _size_key(row['carton_number'])
        for row in rows if row['carton_number']
    })
    total_quantity = _sum_available([row['quantity'] for row in rows])
    gross_weight = _sum_available([row['declared_weight'] for row in rows])
    net_weight = _sum_available([row['calculated_weight'] for row in rows])
    volume = _sum_available([
        _carton_summary(group)['volume']
        for group in cartons.values() if group[0]['carton_number']
    ])
    mixed_cartons = sum(
        1 for group in cartons.values()
        if group[0]['carton_number'] and _carton_summary(group)['mixed']
    )
    invoice_usd = (
        _sum_complete([row['amount_usd'] for row in rows])
        if include_prices else None
    )
    invoice_cny = (
        _sum_complete([row['amount_cny'] for row in rows])
        if include_prices else None
    )
    cargo_rows = [
        ('Total cartons', carton_count),
        ('Total quantity (PCS)', total_quantity),
        ('Invoice value (USD)', invoice_usd if invoice_usd is not None else ''),
        ('Gross weight (kg)', gross_weight),
        ('Net weight (kg)', net_weight),
        ('Volume (CBM)', volume),
        ('Mixed cartons', mixed_cartons),
        ('Invoice value (CNY)', invoice_cny if invoice_cny is not None else ''),
    ]

    for index, (label, value) in enumerate(exchange_rows, start=4):
        ws.cell(index, 1, label)
        ws.cell(index, 2, value if value is not None else '')
        _style_range(ws, index, index, 1, 2, fill='FFFFFFFF')
    for index, (label, value) in enumerate(cargo_rows, start=4):
        ws.cell(index, 3, label)
        ws.cell(index, 4, value if value is not None else '')
        _style_range(ws, index, index, 3, 4, fill='FFE4F3EE')

    ws['B5'].number_format = '0.00000000'
    ws['D4'].number_format = '#,##0'
    ws['D5'].number_format = '#,##0'
    ws['D6'].number_format = '#,##0.00'
    ws['D7'].number_format = '#,##0.0000'
    ws['D8'].number_format = '#,##0.0000'
    ws['D9'].number_format = '#,##0.000000'
    ws['D10'].number_format = '#,##0'
    ws['D11'].number_format = '#,##0.00'

    ws.merge_cells('A12:D12')
    ws['A12'] = 'SENSITIVE ITEM DETAILS'
    _style_range(ws, 12, 12, 1, 4, fill='FFEDE8F7', bold=True)
    for col, value in enumerate(
        ['Carton', 'Item description', 'QTY (PCS)', 'Reason(s)'], start=1
    ):
        ws.cell(13, col, value)
    _style_header(ws, 13, 4)
    for row_index, values in enumerate(sensitive_rows, start=14):
        for col, value in enumerate(values, start=1):
            ws.cell(row_index, col, value)
        _style_range(
            ws, row_index, row_index, 1, 4,
            fill='FFFAFBFD' if row_index % 2 == 0 else 'FFFFFFFF',
        )
        ws.cell(row_index, 3).number_format = '#,##0'
    ws.freeze_panes = 'A4'
    for col, width in {'A': 18, 'B': 42, 'C': 24, 'D': 30}.items():
        ws.column_dimensions[col].width = width
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    return ws


def _invoice_groups(rows):
    """Return only categories represented by actual Packing item rows.

    Keep the reference category ordering for matching categories, followed
    by other categories in their first-seen order. Never emit a category
    solely because it existed in the reference spreadsheet.
    """
    groups = OrderedDict()
    for row in rows:
        category = row['category'] or 'Uncategorized'
        groups.setdefault(category, []).append(row)

    category_order = [name for name in REFERENCE_CATEGORY_ORDER if name in groups]
    category_order.extend(name for name in groups if name not in REFERENCE_CATEGORY_ORDER)
    return OrderedDict((name, groups[name]) for name in category_order)


def _invoice_sheet(workbook, packing, rows, include_prices):
    ws = workbook.create_sheet('Invoice')
    ws.sheet_view.showGridLines = False
    for merge in ('A1:B1', 'C1:D1', 'E1:F1', 'G1:G4'):
        ws.merge_cells(merge)
    meta = [
        ('A1', 'Country of Origin'), ('A2', '原产地'),
        ('B2', _safe_get(packing, 'origin') or ''),
        ('C1', 'Country of Export'), ('C2', '出口国'),
        ('D2', _safe_get(packing, 'origin') or ''),
        ('E1', 'Country of destination'), ('E2', '进口国'),
        ('F2', _safe_get(packing, 'destination') or ''),
        ('G1', 'HS Code'),
    ]
    for cell, value in meta:
        ws[cell] = value
    for row in range(1, 5):
        _style_range(ws, row, row, 1, 10, fill='FFEBF4FA')
    ws.merge_cells('B3:C3')
    ws.merge_cells('B4:C4')
    for cell, value in {
        'A3': 'ITEMS', 'B3': 'DESCRIPTION OF GOODS',
        'A4': '项目', 'B4': '货物描述',
        'D3': 'QUANTITY', 'D4': '数量(PCS)',
    }.items():
        ws[cell] = value
    if include_prices:
        for cell, value in {
            'E3': 'UNIT VALUE', 'E4': '单价(USD/PCS)',
            'F3': 'TOTAL VALUE', 'F4': '总价(USD)',
            'H3': 'UNIT VALUE (CNY)', 'H4': '单价(CNY/PCS)',
            'I3': 'TOTAL VALUE (CNY)', 'I4': '总价(CNY)',
            'J3': 'USD / KG (NET)',
        }.items():
            ws[cell] = value
    else:
        ws['E3'] = 'HS CODE'
        ws['E4'] = '海关编码'

    headers_end = 10 if include_prices else 5
    _style_header(ws, 3, headers_end)
    _style_range(ws, 4, 4, 1, headers_end, fill='FFDDEBF5', bold=True)
    ws.row_dimensions[3].height = 28
    ws.row_dimensions[4].height = 28

    current = 5
    for index, (category, group) in enumerate(_invoice_groups(rows).items(), start=1):
        quantity = _sum_available([row['quantity'] for row in group])
        net_weight = _sum_available([row['calculated_weight'] for row in group])
        ws.cell(current, 1, index)
        ws.cell(current, 2, category)
        ws.cell(current, 4, quantity if quantity is not None else Decimal('0'))
        if not include_prices:
            ws.cell(current, 5, '')
        if include_prices:
            amount_usd = _sum_complete([row['amount_usd'] for row in group])
            amount_cny = _sum_complete([row['amount_cny'] for row in group])
            unit_usd = (
                amount_usd / quantity
                if amount_usd is not None and quantity is not None and quantity > 0
                else (Decimal('0') if quantity == 0 else None)
            )
            unit_cny = (
                amount_cny / quantity
                if amount_cny is not None and quantity is not None and quantity > 0
                else (Decimal('0') if quantity == 0 else None)
            )
            usd_per_kg = (
                amount_usd / net_weight
                if amount_usd is not None and net_weight is not None and net_weight > 0
                else None
            )
            ws.cell(current, 5, float(unit_usd) if unit_usd is not None else None)
            ws.cell(current, 6, float(amount_usd) if amount_usd is not None else None)
            ws.cell(current, 8, float(unit_cny) if unit_cny is not None else None)
            ws.cell(current, 9, float(amount_cny) if amount_cny is not None else None)
            ws.cell(current, 10, float(usd_per_kg) if usd_per_kg is not None else None)
        _style_range(
            ws, current, current, 1, headers_end,
            fill='FFFFFFFF' if index % 2 else 'FFFAFBFD',
        )
        ws.merge_cells(
            start_row=current, start_column=2,
            end_row=current, end_column=3,
        )
        current += 1

    total_row = current
    ws.cell(total_row, 1, 'TOTAL')
    ws.cell(
        total_row, 4,
        float(_sum_available([row['quantity'] for row in rows]) or Decimal('0')),
    )
    if include_prices:
        total_usd = _sum_complete([row['amount_usd'] for row in rows])
        total_cny = _sum_complete([row['amount_cny'] for row in rows])
        ws.cell(total_row, 6, float(total_usd) if total_usd is not None else None)
        ws.cell(total_row, 9, float(total_cny) if total_cny is not None else None)
    _style_range(ws, total_row, total_row, 1, headers_end, fill='FFE7F0ED', bold=True)

    for row in range(5, total_row + 1):
        ws.cell(row, 4).number_format = '#,##0'
        if include_prices:
            for col in (5, 8, 10):
                ws.cell(row, col).number_format = '0.00000000'
            for col in (6, 9):
                ws.cell(row, col).number_format = '#,##0.00'
    ws.freeze_panes = 'A5'
    widths = {
        'A': 9, 'B': 26, 'C': 12, 'D': 14, 'E': 18, 'F': 18,
        'G': 14, 'H': 18, 'I': 19, 'J': 19,
    }
    for col, width in widths.items():
        ws.column_dimensions[col].width = width if include_prices or col <= 'E' else 3
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    return ws


def _number_words(number):
    units = [
        'ZERO', 'ONE', 'TWO', 'THREE', 'FOUR', 'FIVE', 'SIX', 'SEVEN',
        'EIGHT', 'NINE', 'TEN', 'ELEVEN', 'TWELVE', 'THIRTEEN',
        'FOURTEEN', 'FIFTEEN', 'SIXTEEN', 'SEVENTEEN', 'EIGHTEEN',
        'NINETEEN',
    ]
    tens = [
        '', '', 'TWENTY', 'THIRTY', 'FORTY', 'FIFTY', 'SIXTY',
        'SEVENTY', 'EIGHTY', 'NINETY',
    ]

    def under_thousand(value):
        parts = []
        if value >= 100:
            parts.append(units[value // 100] + ' HUNDRED')
            value %= 100
        if value >= 20:
            text = tens[value // 10]
            if value % 10:
                text += ' ' + units[value % 10]
            parts.append(text)
        elif value:
            parts.append(units[value])
        return ' '.join(parts)

    value = max(int(number or 0), 0)
    if value < 1000:
        return under_thousand(value)
    groups = []
    for scale in ('', 'THOUSAND', 'MILLION', 'BILLION'):
        if value <= 0:
            break
        chunk = value % 1000
        if chunk:
            text = under_thousand(chunk)
            groups.append((text + (' ' + scale if scale else '')).strip())
        value //= 1000
    return ' '.join(reversed(groups))


def _packing_list_sheet(workbook, rows, cartons):
    ws = workbook.create_sheet('Packing List')
    ws.sheet_view.showGridLines = False
    ws.append([
        'CTN', 'DESCRIPTION OF GOODS', 'QUANTITY(PCS/ KG)', 'HS Code',
        'NET WEIGHT (KGS)', 'GROSS WEIGHT(KGS)', 'L(CM)*W(CM)*H(CM)',
    ])
    _style_header(ws, 1, 7)
    category_groups = _invoice_groups(rows)
    carton_counts = defaultdict(int)
    for group in cartons.values():
        if not group[0]['carton_number']:
            continue
        primary_category = _carton_summary(group)['primary_category']
        if primary_category:
            carton_counts[primary_category] += 1

    for index, (category, group) in enumerate(category_groups.items(), start=2):
        carton_count = carton_counts.get(category, 0)
        quantity = _sum_available([row['quantity'] for row in group])
        net = _sum_available([row['calculated_weight'] for row in group])
        gross = _sum_available([row['declared_weight'] for row in group])
        size = _representative(row['size'] for row in group)
        values = [
            carton_count, category, quantity, '', net, gross, size or '—',
        ]
        for col, value in enumerate(values, start=1):
            ws.cell(index, col, value)
        _style_range(
            ws, index, index, 1, 7,
            fill='FFFAFBFD' if index % 2 == 0 else 'FFFFFFFF',
        )
        ws.cell(index, 1).number_format = '#,##0'
        ws.cell(index, 3).number_format = '#,##0'
        ws.cell(index, 5).number_format = '#,##0.0000'
        ws.cell(index, 6).number_format = '#,##0.0000'

    total_row = ws.max_row + 1
    total_cartons = len({
        _size_key(row['carton_number'])
        for row in rows if row['carton_number']
    })
    total_quantity = _sum_available([row['quantity'] for row in rows])
    total_net = _sum_available([row['calculated_weight'] for row in rows])
    total_gross = _sum_available([row['declared_weight'] for row in rows])
    total_volume = _sum_available([
        _carton_summary(group)['volume']
        for group in cartons.values() if group[0]['carton_number']
    ])
    for col, value in enumerate([
        total_cartons, 'TOTAL', total_quantity, '',
        total_net, total_gross, total_volume,
    ], start=1):
        ws.cell(total_row, col, value)
    _style_range(ws, total_row, total_row, 1, 7, fill='FFE7F0ED', bold=True)
    ws.cell(total_row, 1).number_format = '#,##0'
    ws.cell(total_row, 3).number_format = '#,##0'
    ws.cell(total_row, 5).number_format = '#,##0.0000'
    ws.cell(total_row, 6).number_format = '#,##0.0000'
    ws.cell(total_row, 7).number_format = '#,##0.000000'

    say_total_row = total_row + 2
    ws.merge_cells(
        start_row=say_total_row, start_column=1,
        end_row=say_total_row, end_column=7,
    )
    ws.cell(
        say_total_row, 1,
        f'SAY TOTAL: {_number_words(total_cartons)} ({total_cartons}) CARTONS',
    )
    _style_range(
        ws, say_total_row, say_total_row, 1, 7,
        fill='FFEDE8F7', bold=True,
    )
    for col, width in {
        'A': 11, 'B': 34, 'C': 19, 'D': 15,
        'E': 19, 'F': 19, 'G': 25,
    }.items():
        ws.column_dimensions[col].width = width
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    return ws


def build_packing_workbook(packing, items, include_prices=False):
    """Build the approved carton-oriented four-sheet Packing workbook."""
    rows = [_item_data(item) for item in items]
    rows.sort(key=lambda row: (
        _natural_key(row['carton_number']) if row['carton_number'] else ('~',),
        _natural_key(row['pk']),
    ))
    cartons = _carton_groups(rows)
    fx = _prepare_financial_rows(rows, packing, include_prices)

    workbook = Workbook()
    workbook.properties.creator = 'MicMod Portal'
    workbook.properties.title = 'Packing Export'
    workbook.properties.subject = 'Packing, Summary, Invoice and Packing List'

    _main_sheet(workbook, packing, rows, cartons, include_prices)
    _summary_sheet(workbook, packing, rows, cartons, fx, include_prices)
    _invoice_sheet(workbook, packing, rows, include_prices)
    _packing_list_sheet(workbook, rows, cartons)

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output
