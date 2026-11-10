"""Four-sheet Excel export for Quick Packing."""
from decimal import Decimal, InvalidOperation
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from .packing_volume import resolve_packing_volume


XLSX_CONTENT_TYPE = (
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
)


def _decimal(value):
    if value is None or str(value).strip() == '':
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _text(value):
    return '' if value is None else str(value)


def _item_data(item):
    order = getattr(item, 'order', None)
    product = None
    if order is not None:
        product = getattr(order, 'final_item', None)
        if product is None:
            product = getattr(order, 'item_trade', None) or getattr(order, 'item', None)

    quantity = _decimal(getattr(item, 'quantity', None))
    unit_weight = _decimal(getattr(order, 'final_weight', None)) if order else None
    calculated_weight = _decimal(getattr(item, 'net_weight_kg', None))
    if calculated_weight is None and unit_weight is not None and quantity is not None:
        calculated_weight = unit_weight * quantity

    size = getattr(item, 'size', None)
    try:
        volume = resolve_packing_volume(
            getattr(item, 'volume', None),
            size=size,
            is_confirmed=bool(getattr(item, 'volume_is_confirmed', False)),
        )
    except ValueError:
        volume = None

    brand = getattr(item, 'brand', None)
    if not brand and order is not None:
        brand_obj = getattr(order, 'brand', None)
        brand = getattr(brand_obj, 'title', None) if brand_obj else None

    part_number = (
        getattr(item, 'part_number', None)
        or getattr(product, 'part_number', None)
        or (getattr(order, 'part_number_mac', None) if order else None)
    )
    description = (
        getattr(item, 'description', None)
        or getattr(product, 'description', None)
        or (getattr(order, 'description_trade', None) if order else None)
        or (getattr(order, 'description_sale', None) if order else None)
    )
    currency = getattr(order, 'currency', None) if order else None
    currency_name = (
        getattr(currency, 'title_en', None)
        or getattr(currency, 'title', None)
        if currency else None
    )
    unit_price = _decimal(getattr(item, 'price', None))
    if unit_price is None and order is not None:
        unit_price = _decimal(getattr(order, 'final_price', None))

    return {
        'order_number': (
            getattr(order, 'order_number', None) or getattr(order, 'pk', None)
        ) if order else '',
        'carton_number': getattr(item, 'carton_number', None),
        'carton_quantity': getattr(item, 'carton_quantity', None),
        'brand': brand,
        'category': getattr(item, 'category', None),
        'main_category': getattr(item, 'main_category', None),
        'part_number': part_number,
        'description': description,
        'quantity': quantity,
        'declared_weight': _decimal(getattr(item, 'gross_weight_kg', None)),
        'size': size,
        'volume': volume,
        'unit_weight': unit_weight,
        'calculated_weight': calculated_weight,
        'unit_price': unit_price,
        'amount': (
            unit_price * quantity
            if unit_price is not None and quantity is not None else None
        ),
        'currency': currency_name,
    }


def _complete_sum(values):
    if not values:
        return Decimal('0')
    if any(value is None for value in values):
        return None
    return sum(values, Decimal('0'))


def _style_header(ws, row=1):
    for cell in ws[row]:
        cell.fill = PatternFill('solid', fgColor='1F4E78')
        cell.font = Font(name='Calibri', color='FFFFFF', bold=True)
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = Border(bottom=Side(style='thin', color='D9E2F3'))
    ws.row_dimensions[row].height = 30


def _finish_table(ws, header_row=1):
    _style_header(ws, header_row)
    ws.freeze_panes = f'A{header_row + 1}'
    if ws.max_row >= header_row:
        ws.auto_filter.ref = (
            f'A{header_row}:{ws.cell(ws.max_row, ws.max_column).coordinate}'
        )
    for row in ws.iter_rows(min_row=header_row + 1):
        for cell in row:
            cell.alignment = Alignment(vertical='center', wrap_text=True)
            cell.border = Border(bottom=Side(style='hair', color='E7E6E6'))
    for column in ws.columns:
        letter = column[0].column_letter
        max_length = max(
            (len(str(cell.value)) for cell in column if cell.value is not None),
            default=10,
        )
        ws.column_dimensions[letter].width = min(max(max_length + 2, 12), 42)


def _format_numeric_columns(ws, columns, start_row=2):
    for column in columns:
        for row in range(start_row, ws.max_row + 1):
            ws.cell(row, column).number_format = '#,##0.000'
            

def build_packing_workbook(packing, items, include_prices=False):
    """Return an in-memory workbook with Packing, Summary, Invoice and Packing List."""
    rows = [_item_data(item) for item in items]
    rows.sort(key=lambda row: (
        _text(row['carton_number']).casefold(),
        _text(row['part_number']).casefold(),
        _text(row['order_number']).casefold(),
    ))

    workbook = Workbook()
    workbook.properties.creator = 'MicMod Portal'
    workbook.properties.title = 'Packing Export'

    # 1. Packing: preserve the agreed A-M column positions.
    packing_ws = workbook.active
    packing_ws.title = 'Packing'
    packing_ws.append([
        'Carton Number', 'Carton Quantity', 'Brand', 'Category',
        'Main Category', 'Part Number', 'Description', 'Quantity',
        'Declared Weight (kg)', 'Size (L*W*H cm)', 'Volume (m³)',
        'Unit Weight (kg)', 'Calculated Weight (kg)',
    ])
    for row in rows:
        packing_ws.append([
            _text(row['carton_number']),
            row['carton_quantity'],
            _text(row['brand']),
            _text(row['category']),
            _text(row['main_category']),
            _text(row['part_number']),
            _text(row['description']),
            row['quantity'],
            row['declared_weight'],
            _text(row['size']),
            row['volume'],
            row['unit_weight'],
            row['calculated_weight'],
        ])
    _finish_table(packing_ws)
    _format_numeric_columns(packing_ws, (8, 9, 11, 12, 13))
    packing_ws.column_dimensions['A'].width = 18
    packing_ws.column_dimensions['C'].width = 20
    packing_ws.column_dimensions['G'].width = 34
    packing_ws.column_dimensions['J'].width = 20

    # 2. Summary: header and operational totals, followed by Category totals.
    summary_ws = workbook.create_sheet('Summary')
    summary_ws['A1'] = 'Packing Summary'
    summary_ws.merge_cells('A1:D1')
    summary_ws['A1'].font = Font(name='Calibri', size=15, bold=True, color='1F1F1F')
    summary_ws['A1'].fill = PatternFill('solid', fgColor='D9EAF7')
    summary_ws['A1'].alignment = Alignment(horizontal='center')
    summary_ws.append(['Metric', 'Value'])
    _style_header(summary_ws, 2)

    carton_numbers = {
        _text(row['carton_number']).strip().casefold()
        for row in rows if _text(row['carton_number']).strip()
    }
    quantities = [row['quantity'] for row in rows]
    declared_weights = [row['declared_weight'] for row in rows]
    calculated_weights = [row['calculated_weight'] for row in rows]
    volumes = [row['volume'] for row in rows]
    summary_values = [
        ('Packing Number', getattr(packing, 'packing_number', None) or getattr(packing, 'pk', '')),
        ('BL Number', getattr(packing, 'bl_number', None)),
        ('BL Date', getattr(packing, 'bl_date', None)),
        ('Carrier', getattr(packing, 'transportation_company', None)),
        ('Origin', getattr(packing, 'origin', None)),
        ('Destination', getattr(packing, 'destination', None)),
        ('Estimated Shipping Start', getattr(packing, 'estimated_shipping_start_date', None)),
        ('Estimated Warehouse Arrival', getattr(packing, 'estimated_arrive_to_wh_date', None)),
        ('Unique Cartons', len(carton_numbers)),
        ('Packing Item Rows', len(rows)),
        ('Total Quantity', _complete_sum(quantities)),
        ('Total Declared Weight (kg)', _complete_sum(declared_weights)),
        ('Total Calculated Weight (kg)', _complete_sum(calculated_weights)),
        ('Total Volume (m³)', _complete_sum(volumes)),
    ]
    for metric, value in summary_values:
        summary_ws.append([metric, value if value is not None else ''])

    summary_ws.append([])
    summary_ws.append(['Category', 'Item Rows', 'Quantity', 'Unique Cartons'])
    category_header_row = summary_ws.max_row
    _style_header(summary_ws, category_header_row)
    category_groups = {}
    for row in rows:
        name = _text(row['category']).strip() or 'Uncategorized'
        group = category_groups.setdefault(name, {'rows': 0, 'quantity': [], 'cartons': set()})
        group['rows'] += 1
        group['quantity'].append(row['quantity'])
        carton = _text(row['carton_number']).strip().casefold()
        if carton:
            group['cartons'].add(carton)
    for name, group in sorted(category_groups.items(), key=lambda entry: entry[0].casefold()):
        summary_ws.append([
            name,
            group['rows'],
            _complete_sum(group['quantity']),
            len(group['cartons']),
        ])
    summary_ws.auto_filter.ref = (
        f'A{category_header_row}:D{summary_ws.max_row}'
    )
    summary_ws.freeze_panes = 'A3'
    summary_ws.column_dimensions['A'].width = 34
    summary_ws.column_dimensions['B'].width = 24
    summary_ws.column_dimensions['C'].width = 22
    summary_ws.column_dimensions['D'].width = 20
    for row in summary_ws.iter_rows(min_row=3):
        for cell in row:
            cell.alignment = Alignment(vertical='center', wrap_text=True)

    # 3. Invoice: financial columns are absent unless the requester has access.
    invoice_ws = workbook.create_sheet('Invoice')
    invoice_headers = [
        'Order Number', 'Brand', 'Part Number', 'Description', 'Quantity',
    ]
    if include_prices:
        invoice_headers.extend(['Currency', 'Unit Price', 'Amount'])
    invoice_ws.append(invoice_headers)
    for row in rows:
        invoice_row = [
            _text(row['order_number']),
            _text(row['brand']),
            _text(row['part_number']),
            _text(row['description']),
            row['quantity'],
        ]
        if include_prices:
            invoice_row.extend([
                _text(row['currency']),
                row['unit_price'],
                row['amount'],
            ])
        invoice_ws.append(invoice_row)
    _finish_table(invoice_ws)
    _format_numeric_columns(invoice_ws, (5,))
    if include_prices:
        _format_numeric_columns(invoice_ws, (7, 8))
    invoice_ws.column_dimensions['D'].width = 34

    # 4. Packing List: practical carton-oriented view for dispatch/warehouse.
    packing_list_ws = workbook.create_sheet('Packing List')
    packing_list_ws.append([
        'Carton Number', 'Carton Quantity', 'Brand', 'Part Number',
        'Description', 'Category', 'Quantity', 'Size', 'Volume (m³)',
        'Declared Weight (kg)', 'Calculated Weight (kg)',
    ])
    for row in rows:
        packing_list_ws.append([
            _text(row['carton_number']),
            row['carton_quantity'],
            _text(row['brand']),
            _text(row['part_number']),
            _text(row['description']),
            _text(row['category']),
            row['quantity'],
            _text(row['size']),
            row['volume'],
            row['declared_weight'],
            row['calculated_weight'],
        ])
    _finish_table(packing_list_ws)
    _format_numeric_columns(packing_list_ws, (7, 9, 10, 11))
    packing_list_ws.column_dimensions['E'].width = 34
    packing_list_ws.column_dimensions['H'].width = 20

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output
