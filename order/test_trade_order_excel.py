"""Workbook tests can run without Django or the portal database."""
from datetime import date, datetime
from types import SimpleNamespace
from unittest import TestCase

from openpyxl import load_workbook

from order.trade_order_excel import build_order_export, selected_fields


TODAY = date(2026, 11, 28)


def currency(name):
    return SimpleNamespace(title_en=name)


def payment(pk, day, amount, paid=False, cur=None, header=None, deleted=False):
    return SimpleNamespace(
        pk=pk, is_deleted=deleted, is_pay=paid,
        pay_date=date(2026, 11, day) if day else None,
        total_amount=amount, payment_id=header.pk if header else None,
        currency=cur, payment=header, get_payment_item_type_display=lambda: 'payment',
    )


def order():
    item = SimpleNamespace(sku='000123', part_number='=HYPERLINK("bad")')
    return SimpleNamespace(
        pk=1, order_number='000001', po_number_trade='0000123', po_number_mac='0000456',
        last_work_flow=SimpleNamespace(current_state_name='تایید بازرگانی'),
        get_order_type_display=lambda: 'china', creator_user='trade user',
        final_item=item, item=SimpleNamespace(sku='WRONG'),
        get_transportation_method_display=lambda: 'air', final_total_weight=12.3456,
        list_order_currency_title='RMB',
        list_payment_items=[
            payment(1, 25, 100), payment(2, 28, 50),
            payment(3, 29, 30), payment(4, 29, 20, True),
            payment(5, 20, 40, True, currency('USD')),
            payment(6, None, 5), payment(7, None, 7, True),
            payment(8, 30, 9999, deleted=True),
            payment(9, 30, 2.5, cur=currency('RMB'), header=SimpleNamespace(pk=4, currency=currency('USD'))),
        ],
        export_gio_items=[
            SimpleNamespace(gio_id=12, quantity=5, is_deleted=False),
            SimpleNamespace(gio_id=12, quantity=3, is_deleted=False),
            SimpleNamespace(gio_id=14, quantity=99, is_deleted=True),
        ],
        export_packing_items=[SimpleNamespace(packing_id=22, quantity=4, is_deleted=False)],
    )


class TradeOrderWorkbookTests(TestCase):
    def workbook(self, keys, orders=None, details=False):
        return load_workbook(build_order_export([order()] if orders is None else orders, keys, TODAY, details))

    def test_selected_columns_and_excel_types(self):
        wb = self.workbook(['total_weight', 'part_number', 'po_number_trade', 'sku', 'order_number'])
        ws = wb['Orders']
        self.assertEqual(list(next(ws.values)), ['شماره سفارش', 'PO Number Trade', 'SKU (Final Item)', 'Part Number (Final Item)', 'وزن کل'])
        self.assertEqual(ws['A2'].value, '000001')
        self.assertEqual(ws['B2'].value, '0000123')
        self.assertEqual(ws['C2'].value, '000123')
        self.assertEqual(ws['D2'].data_type, 's')
        self.assertEqual(ws['D2'].value, '=HYPERLINK("bad")')
        self.assertEqual(ws['E2'].value, 12.3456)
        self.assertEqual(ws['E2'].data_type, 'n')
        self.assertEqual(ws.freeze_panes, 'A2')
        self.assertEqual(ws.auto_filter.ref, 'A1:E2')
        self.assertTrue(ws.sheet_view.rightToLeft)
        self.assertEqual(wb.sheetnames, ['Orders'])

    def test_payment_totals_and_dates(self):
        ws = self.workbook(['payments', 'future_payments', 'past_payments', 'paid', 'overdue', 'today', 'scheduled', 'undated'])['Orders']
        values = list(ws.values)[1]
        self.assertIn('بدون سربرگ', values[0])
        self.assertNotIn('9,999', values[0])
        self.assertIn('20 RMB | 2026/11/29 | پرداخت شده', values[1])
        self.assertIn('50 RMB | 2026/11/28', values[1])
        self.assertIn('100 RMB | 2026/11/25', values[2])
        self.assertEqual(values[3], '27 RMB\n40 USD')
        self.assertEqual(values[4], '100 RMB')
        self.assertEqual(values[5], '50 RMB')
        self.assertEqual(values[6], '30 RMB\n2.5 USD')
        self.assertEqual(values[7], '5 RMB')

    def test_detail_sheet_keeps_numbers_and_dates_native(self):
        wb = self.workbook(['order_number'], details=True)
        ws = wb['Payment details']
        rows = list(ws.values)[1:]
        self.assertEqual(len(rows), 8)
        row = next(row for row in rows if row[1] == 9)
        self.assertEqual(row[2], 4)
        self.assertEqual(row[4:6], (2.5, 'USD'))
        self.assertEqual(row[6], datetime(2026, 11, 30))
        self.assertEqual(row[7], 'خیر')
        self.assertEqual(ws.auto_filter.ref, 'A1:I9')

    def test_grouped_gio_packing_and_duplicate_orders(self):
        obj = order()
        ws = self.workbook(['gio', 'packing'], [obj, obj])['Orders']
        self.assertEqual(list(ws.values)[1:], [('#12 | 8', '#22 | 4')])

    def test_empty_results_and_invalid_fields(self):
        ws = self.workbook(['order_number'], [])['Orders']
        self.assertEqual(list(ws.values), [('شماره سفارش',)])
        self.assertEqual(ws.auto_filter.ref, 'A1:A1')
        for keys in ([], ['invalid'], ['order_number', 'order_number']):
            with self.subTest(keys=keys), self.assertRaises(ValueError):
                selected_fields(keys)

    def test_missing_final_item_and_control_characters(self):
        obj = order()
        obj.final_item = None
        obj.po_number_trade = 'PO\x00-01'
        ws = self.workbook(['po_number_trade', 'sku', 'part_number'], [obj])['Orders']
        self.assertEqual(ws['A2'].value, 'PO-01')
        self.assertIsNone(ws['B2'].value)
        self.assertIsNone(ws['C2'].value)
