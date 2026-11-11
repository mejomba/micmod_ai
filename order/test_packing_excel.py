"""Regression tests for the approved four-sheet Packing Excel export."""
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase
from openpyxl import load_workbook

from order.packing_excel import build_packing_workbook


def sample_data():
    cny = SimpleNamespace(pk=2, title='یوان', title_en='RMB')
    usd = SimpleNamespace(pk=1, title='دلار', title_en='Dollar')
    product = SimpleNamespace(
        part_number='PN-100', sku='SKU-100',
        weight=Decimal('0.250'),
        purchase_group=SimpleNamespace(title='PCBA', hs=None),
        hs=SimpleNamespace(code='85340000'), brand=None,
    )
    order = SimpleNamespace(
        pk=100, order_number='ORD-100', final_item=product,
        item=None, item_trade=None, brand=SimpleNamespace(title='Brand A'),
        final_weight=Decimal('0.250'), final_price=Decimal('12.50'),
        currency=cny, currency_id=2, description_trade='Trade description',
        description_sale='Sales description', part_number_mac='',
    )
    packing = SimpleNamespace(
        pk=9, packing_number='PK-009', shipment_type='air',
        origin='Shenzhen', destination='Tehran',
        currency=usd, currency_id=1,
        currency_exchange_rates={
            'target_currency_id': '1', 'rates': {'2': '0.15'},
        },
    )
    first = SimpleNamespace(
        pk=1, order=order, packing=packing, carton_number='C-01',
        carton_quantity=1, brand='Row Brand', category='Electronics',
        main_category='Electronics', part_number='PN-100',
        description='Widget', quantity=4,
        gross_weight_kg=Decimal('1.200'), net_weight_kg=None,
        size='40*30*20', volume=None, volume_is_confirmed=False,
        price=Decimal('12.50'), duty_date=None,
    )

    second_product = SimpleNamespace(
        part_number='PN-200', sku='SKU-200',
        weight=Decimal('0.500'),
        purchase_group=SimpleNamespace(title='Mechanical', hs=None),
        hs=SimpleNamespace(code='84818000'), brand=None,
    )
    second_order = SimpleNamespace(
        pk=101, order_number='ORD-101', final_item=second_product,
        item=None, item_trade=None, brand=SimpleNamespace(title='Brand B'),
        final_weight=Decimal('0.500'), final_price=Decimal('4.00'),
        currency=cny, currency_id=2, description_trade='Trade description',
        description_sale='Sales description', part_number_mac='',
    )
    second = SimpleNamespace(
        pk=2, order=second_order, packing=packing, carton_number='C-01',
        carton_quantity=2, brand='Row Brand B', category='Mechanical',
        main_category='Mechanical', part_number='PN-200',
        description='Mechanical widget', quantity=2,
        gross_weight_kg=Decimal('0.800'), net_weight_kg=None,
        size='40*30*20', volume=None, volume_is_confirmed=False,
        price=Decimal('4.00'), duty_date=None,
    )
    third = SimpleNamespace(
        pk=3, order=order, packing=packing, carton_number='C-02',
        carton_quantity=1, brand='Row Brand', category='Electronics',
        main_category='Electronics', part_number='PN-100',
        description='Widget', quantity=4,
        gross_weight_kg=Decimal('0.900'), net_weight_kg=None,
        size='20*20*20', volume=None, volume_is_confirmed=False,
        price=Decimal('12.50'), duty_date=None,
    )
    return packing, [first, second, third]


class PackingExcelTests(SimpleTestCase):
    def load_export(self, include_prices=True):
        packing, items = sample_data()
        output = build_packing_workbook(
            packing, items, include_prices=include_prices,
        )
        self.assertIsInstance(output, BytesIO)
        return load_workbook(output, data_only=True)

    def test_export_contains_the_four_reference_sheets(self):
        workbook = self.load_export()
        self.assertEqual(
            workbook.sheetnames,
            ['PK-009 AIR', 'Summary', 'Invoice', 'Packing List'],
        )

    def test_main_sheet_matches_reference_columns_and_carton_weight_rules(self):
        workbook = self.load_export()
        sheet = workbook['PK-009 AIR']
        self.assertEqual(sheet.max_column, 25)
        self.assertEqual(sheet['A1'].value, 'Ctn NMMO#.')
        self.assertEqual(sheet['B1'].value, 'Carton No.')
        self.assertEqual(sheet['D1'].value, 'Brand')
        self.assertEqual(sheet['I1'].value, 'Our Weight')
        self.assertEqual(sheet['M1'].value, 'WEIGHT (kg)')
        self.assertEqual(sheet['V1'].value, 'Item Weight (kg)')

        self.assertEqual(sheet['A2'].value, 'C-01')
        self.assertEqual(sheet['B2'].value, 3)
        self.assertEqual(sheet['D2'].value, 'Brand A')
        self.assertEqual(sheet['F2'].value, 'PCBA')
        self.assertEqual(sheet['I2'].value, 1.2)
        self.assertEqual(sheet['J2'].value, 'C-01 / Electronics')
        self.assertEqual(sheet['M2'].value, 2.0)
        self.assertEqual(sheet['V2'].value, 1.0)
        self.assertEqual(sheet['V3'].value, 1.0)
        self.assertEqual(sheet['N2'].value, 0.024)
        self.assertIn('A2:A3', [str(r) for r in sheet.merged_cells.ranges])
        self.assertIn('M2:M3', [str(r) for r in sheet.merged_cells.ranges])

        self.assertEqual(sheet['A4'].value, 'C-02')
        self.assertEqual(sheet['M4'].value, 1.0)
        self.assertEqual(sheet['V4'].value, 1.0)
        self.assertEqual(sheet['N4'].value, 0.008)

    def test_saved_exchange_rate_populates_cny_and_usd_values(self):
        workbook = self.load_export()
        sheet = workbook['PK-009 AIR']
        self.assertEqual(sheet['O2'].value, 12.5)
        self.assertEqual(sheet['P2'].value, 50.0)
        self.assertAlmostEqual(sheet['Q2'].value, 1.875)
        self.assertAlmostEqual(sheet['R2'].value, 7.5)
        self.assertAlmostEqual(workbook['Summary']['B5'].value, 0.15)
        self.assertAlmostEqual(workbook['Summary']['D6'].value, 16.2)
        self.assertEqual(workbook['Summary']['D11'].value, 108.0)

    def test_summary_and_packing_list_aggregate_cartons_and_rows_separately(self):
        workbook = self.load_export()
        summary = workbook['Summary']
        self.assertEqual(summary['D4'].value, 2)
        self.assertEqual(summary['D5'].value, 10)
        self.assertEqual(summary['D7'].value, 2.9)
        self.assertEqual(summary['D8'].value, 3.0)
        self.assertEqual(summary['D9'].value, 0.032)
        self.assertEqual(summary['D10'].value, 1)

        packing_list = workbook['Packing List']
        self.assertEqual(packing_list['A1'].value, 'CTN')
        self.assertEqual(packing_list['B1'].value, 'DESCRIPTION OF GOODS')
        electronics_row = next(
            row for row in range(2, packing_list.max_row + 1)
            if packing_list.cell(row, 2).value == 'Electronics'
        )
        self.assertEqual(packing_list.cell(electronics_row, 1).value, 2)
        self.assertEqual(packing_list.cell(electronics_row, 3).value, 8)

    def test_invoice_and_packing_list_include_only_actual_categories(self):
        """Reference-template categories must not create empty detail rows."""
        for include_prices in (True, False):
            with self.subTest(include_prices=include_prices):
                workbook = self.load_export(include_prices=include_prices)
                invoice = workbook['Invoice']
                packing_list = workbook['Packing List']

                self.assertEqual(
                    [invoice.cell(row, 2).value for row in (5, 6)],
                    ['Electronics', 'Mechanical'],
                )
                self.assertEqual(invoice['A7'].value, 'TOTAL')
                self.assertEqual(invoice['D7'].value, 10)
                self.assertEqual(invoice.max_row, 7)

                self.assertEqual(
                    [packing_list.cell(row, 2).value for row in (2, 3)],
                    ['Electronics', 'Mechanical'],
                )
                self.assertEqual(packing_list['B4'].value, 'TOTAL')
                self.assertEqual(packing_list['C4'].value, 10)
                self.assertEqual(packing_list['A6'].value, 'SAY TOTAL: TWO (2) CARTONS')

    def test_reference_categories_keep_their_order_without_extra_rows(self):
        packing, items = sample_data()
        items[0].category = 'PCB'
        items[1].category = 'SMD ICs'
        items[2].category = 'PCB'
        workbook = load_workbook(
            build_packing_workbook(packing, items, include_prices=True),
            data_only=True,
        )
        self.assertEqual(
            [workbook['Invoice'].cell(row, 2).value for row in (5, 6)],
            ['SMD ICs', 'PCB'],
        )
        self.assertEqual(
            [workbook['Packing List'].cell(row, 2).value for row in (2, 3)],
            ['SMD ICs', 'PCB'],
        )
        self.assertEqual(workbook['Invoice']['A7'].value, 'TOTAL')
        self.assertEqual(workbook['Packing List']['B4'].value, 'TOTAL')

    def test_uncategorized_label_appears_only_when_an_item_has_no_category(self):
        packing, items = sample_data()
        items[1].category = None
        workbook = load_workbook(
            build_packing_workbook(packing, items, include_prices=False),
            data_only=True,
        )
        self.assertEqual(
            [workbook['Invoice'].cell(row, 2).value for row in (5, 6)],
            ['Electronics', 'Uncategorized'],
        )
        self.assertEqual(
            [workbook['Packing List'].cell(row, 2).value for row in (2, 3)],
            ['Electronics', 'Uncategorized'],
        )
        self.assertEqual(workbook['Invoice']['D7'].value, 10)

    def test_invoice_financial_columns_are_removed_without_permission(self):
        workbook = self.load_export(include_prices=False)
        headers = [cell.value for cell in workbook['Invoice'][3]]
        self.assertNotIn('UNIT VALUE', headers)
        self.assertNotIn('TOTAL VALUE', headers)
        self.assertNotIn('UNIT VALUE (CNY)', headers)
        self.assertNotIn('TOTAL VALUE (CNY)', headers)
        self.assertIsNone(workbook['PK-009 AIR']['O2'].value)
        self.assertIsNone(workbook['PK-009 AIR']['R2'].value)

    def test_invoice_financial_columns_are_present_with_permission(self):
        workbook = self.load_export(include_prices=True)
        sheet = workbook['Invoice']
        headers = [cell.value for cell in sheet[3]]
        self.assertIn('UNIT VALUE', headers)
        self.assertIn('TOTAL VALUE', headers)
        self.assertIn('UNIT VALUE (CNY)', headers)
        self.assertIn('TOTAL VALUE (CNY)', headers)
        electronics_row = next(
            row for row in range(5, sheet.max_row)
            if sheet.cell(row, 2).value == 'Electronics'
        )
        self.assertAlmostEqual(sheet.cell(electronics_row, 5).value, 1.875)
        self.assertAlmostEqual(sheet.cell(electronics_row, 6).value, 15.0)

    def test_zero_calculated_weight_is_reported_as_missing_for_positive_quantity(self):
        packing, items = sample_data()
        for item in (items[0], items[2]):
            item.order.final_weight = Decimal('0')
            item.order.final_item.weight = Decimal('0')
            item.net_weight_kg = Decimal('0')
        workbook = load_workbook(
            build_packing_workbook(packing, items, include_prices=True),
            data_only=True,
        )
        self.assertEqual(workbook['Summary']['B10'].value, 2)
        self.assertIsNone(workbook['PK-009 AIR']['V2'].value)
        self.assertIsNone(workbook['PK-009 AIR']['V4'].value)

    def test_export_button_is_present_on_the_packing_page(self):
        html = (
            Path(settings.BASE_DIR)
            / 'order/templates/order/packing/quick_packing_create.html'
        ).read_text(encoding='utf-8')
        self.assertIn('?export_excel=1', html)
        self.assertIn('packing_export_excel', html)

    def test_excel_export_requires_document_view_permission(self):
        from order.views import QuickPackingView

        packing = SimpleNamespace(
            user_can_view_workflow=lambda user: False,
        )
        view = QuickPackingView()
        request = SimpleNamespace(GET={'export_excel': '1'}, user=object())
        with patch.object(view, 'get_object', return_value=packing):
            with self.assertRaises(PermissionDenied):
                view.get(request, pk=9)
