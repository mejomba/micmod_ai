"""Selectable order-list Excel output; independent of DataTables HTML exports."""
from decimal import Decimal, InvalidOperation
from io import BytesIO

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.filters import AutoFilter

from .trade_payment_schedule import payment_currency, payment_amount


# key, label, width, default, group
EXPORT_FIELDS = (
    ('order_number', 'شماره سفارش', 22, True, 'order'),
    ('po_number_trade', 'PO Number Trade', 24, True, 'order'),
    ('po_number_mac', 'PO Number MAC', 24, True, 'order'),
    ('status', 'وضعیت سفارش', 30, True, 'order'),
    ('order_type', 'نوع سفارش', 18, True, 'order'),
    ('creator_user', 'ایجادکننده', 24, True, 'order'),
    ('sku', 'SKU (Final Item)', 22, True, 'order'),
    ('part_number', 'Part Number (Final Item)', 30, True, 'order'),
    ('transportation_method', 'روش حمل', 20, True, 'order'),
    ('total_weight', 'وزن کل', 18, True, 'order'),
    ('payments', 'تمام پرداخت‌ها', 46, False, 'payment'),
    ('future_payments', 'پرداخت‌های آینده', 46, True, 'payment'),
    ('past_payments', 'پرداخت‌های گذشته', 46, True, 'payment'),
    ('paid', 'کل پرداخت شده (به تفکیک ارز)', 30, True, 'payment'),
    ('overdue', 'منقضی شده (پرداخت نشده)', 30, True, 'payment'),
    ('today', 'سررسید امروز (پرداخت نشده)', 30, True, 'payment'),
    ('scheduled', 'آینده (پرداخت نشده)', 30, True, 'payment'),
    ('undated', 'پرداخت نشده بدون تاریخ', 30, False, 'payment'),
    ('gio', 'GIO (شماره و تعداد)', 28, True, 'logistics'),
    ('packing', 'Packing (شماره و تعداد)', 28, True, 'logistics'),
)
FIELD_MAP = {field[0]: field for field in EXPORT_FIELDS}
PAYMENT_KEYS = {field[0] for field in EXPORT_FIELDS if field[4] == 'payment'}
MAX_DATA_ROWS = 1048575


def selected_fields(keys):
    if not keys or any(key not in FIELD_MAP for key in keys):
        raise ValueError('حداقل یک ستون معتبر برای خروجی انتخاب کنید.')
    if len(keys) != len(set(keys)):
        raise ValueError('ستون تکراری مجاز نیست.')
    # Keep the displayed order, independent of checkbox click order.
    return [field for field in EXPORT_FIELDS if field[0] in keys]


def _number(value):
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def _amount_text(value):
    if value is None:
        return '—'
    label = format(value, ',f')
    return label.rstrip('0').rstrip('.') if '.' in label else label


def _payment_status(item, today):
    if item.is_pay:
        return 'paid', 'پرداخت شده'
    if item.pay_date is None:
        return 'undated', 'بدون تاریخ'
    if item.pay_date < today:
        return 'overdue', 'منقضی شده'
    if item.pay_date == today:
        return 'today', 'سررسید امروز'
    return 'scheduled', 'برنامه‌ریزی شده'


def _payment_rows(order, today):
    rows = []
    for item in order.list_payment_items:
        if item.is_deleted:
            continue
        category, status = _payment_status(item, today)
        rows.append((item, category, status, payment_currency(item, order.list_order_currency_title)))
    return sorted(rows, key=lambda row: (row[0].pay_date is None, row[0].pay_date or today, row[0].pk))


def _payment_line(row):
    item, _, status, currency = row
    date = item.pay_date.strftime('%Y/%m/%d') if item.pay_date else 'بدون تاریخ'
    header = '#' + str(item.payment_id) if item.payment_id else 'بدون سربرگ'
    return f'{payment_amount(item)} {currency} | {date} | {status} | {header}'


def _totals(rows, category):
    amounts = {}
    for item, kind, _, currency in rows:
        if category != kind:
            continue
        amount = _number(item.total_amount)
        if amount is not None:
            amounts[currency] = amounts.get(currency, Decimal(0)) + amount
    return '\n'.join(f'{_amount_text(amount)} {currency}' for currency, amount in sorted(amounts.items()))


def _logistics(rows, field):
    grouped = {}
    for row in rows:
        if row.is_deleted:
            continue
        document_id = getattr(row, field + '_id')
        if document_id is None:
            continue
        amount = _number(row.quantity)
        if document_id not in grouped:
            grouped[document_id] = None
        if amount is not None:
            grouped[document_id] = (grouped[document_id] or Decimal(0)) + amount
    return '\n'.join(f'#{pk} | {_amount_text(qty)}' for pk, qty in sorted(grouped.items()))


def _order_value(order, key, rows, today):
    if key == 'status':
        return getattr(order.last_work_flow, 'current_state_name', '') or ''
    if key == 'creator_user':
        return str(order.creator_user) if order.creator_user else ''
    if key == 'order_type':
        return str(order.get_order_type_display() or '')
    if key == 'transportation_method':
        return str(order.get_transportation_method_display() or '')
    if key in ('sku', 'part_number'):
        return str(getattr(order.final_item, key, '') or '')
    if key == 'total_weight':
        return _number(order.final_total_weight)
    if key in ('order_number', 'po_number_trade', 'po_number_mac'):
        return str(getattr(order, key) or '')
    if key == 'payments':
        return '\n'.join(map(_payment_line, rows))
    if key in ('future_payments', 'past_payments'):
        def future(item):
            return item.pay_date > today or (item.pay_date == today and not item.is_pay)
        dated = [row for row in rows if row[0].pay_date and future(row[0]) == (key == 'future_payments')]
        if key == 'past_payments':
            dated.sort(key=lambda row: (row[0].is_pay, row[0].pay_date, row[0].pk))
        return '\n'.join(map(_payment_line, dated))
    if key in ('paid', 'overdue', 'today', 'scheduled', 'undated'):
        return _totals(rows, key)
    if key == 'gio':
        return _logistics(order.export_gio_items, 'gio')
    if key == 'packing':
        return _logistics(order.export_packing_items, 'packing')
    raise ValueError('Unknown export field')


def _cell(sheet, value, *, header=False, numeric=False, date_cell=False):
    cell = WriteOnlyCell(sheet, value=value)
    if isinstance(value, str):
        if len(value) > 32767:
            raise ValueError('طول یکی از سلول‌ها بیش از ظرفیت اکسل است؛ ستون جزئیات را حذف و شیت ردیف پرداخت را انتخاب کنید.')
        # Force literal strings; preserve leading zeros and prevent formula injection.
        cell.data_type = 's'
    if header:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='2563A6')
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    else:
        cell.alignment = Alignment(vertical='top', wrap_text=True)
        if numeric:
            cell.number_format = '#,##0.############'
        if date_cell:
            cell.number_format = 'yyyy/mm/dd'
    return cell


def _sheet(workbook, title, headers, widths):
    sheet = workbook.create_sheet(title)
    sheet.sheet_view.rightToLeft = True
    sheet.freeze_panes = 'A2'
    sheet.row_dimensions[1].height = 30
    for index, width in enumerate(widths, 1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.append([_cell(sheet, label, header=True) for label in headers])
    return sheet


def _finish(sheet, count, columns):
    sheet.auto_filter = AutoFilter(ref=f'A1:{get_column_letter(columns)}{count + 1}')


def build_order_export(orders, keys, today, payment_details=False):
    fields = selected_fields(keys)
    workbook = Workbook(write_only=True)
    sheet = _sheet(workbook, 'Orders', [f[1] for f in fields], [f[2] for f in fields])
    detail_headers = ['شماره سفارش', 'شناسه ردیف پرداخت', 'شناسه سربرگ پرداخت', 'نوع پرداخت',
                      'مبلغ', 'ارز', 'تاریخ سررسید (میلادی)', 'پرداخت شده', 'وضعیت']
    detail = _sheet(workbook, 'Payment details', detail_headers, [22, 18, 18, 22, 20, 18, 23, 16, 23]) if payment_details else None
    need_payments = bool(PAYMENT_KEYS.intersection(keys)) or payment_details
    seen = set()
    count = detail_count = 0
    for order in orders:
        if order.pk in seen:
            continue
        seen.add(order.pk)
        count += 1
        if count > MAX_DATA_ROWS:
            raise ValueError('تعداد سفارش‌ها بیش از ظرفیت یک شیت اکسل است؛ فیلتر را محدود کنید.')
        rows = _payment_rows(order, today) if need_payments else []
        values = [_order_value(order, field[0], rows, today) for field in fields]
        lines = max((str(value).count('\n') + 1 for value in values if value is not None), default=1)
        if lines > 1:
            sheet.row_dimensions[count + 1].height = min(400, 15 * lines + 6)
        sheet.append([_cell(sheet, value, numeric=field[0] == 'total_weight') for field, value in zip(fields, values)])
        if detail is not None:
            for item, _, status, currency in rows:
                detail_count += 1
                if detail_count > MAX_DATA_ROWS:
                    raise ValueError('تعداد ردیف‌های پرداخت بیش از ظرفیت اکسل است؛ فیلتر را محدود کنید.')
                data = [str(order.order_number or ''), item.pk, item.payment_id,
                        str(item.get_payment_item_type_display() or ''), _number(item.total_amount),
                        currency, item.pay_date, 'بله' if item.is_pay else 'خیر', status]
                detail.append([_cell(detail, value, numeric=index == 4, date_cell=index == 6)
                               for index, value in enumerate(data)])
    _finish(sheet, count, len(fields))
    if detail is not None:
        _finish(detail, detail_count, len(detail_headers))
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output
