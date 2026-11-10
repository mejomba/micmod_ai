"""Tests for the four-sheet Quick Packing Excel export."""
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

from django.test import SimpleTestCase
from openpyxl import load_workbook

from order.packing_excel import build_packing_workbook


def sample_data():
    product = SimpleNamespace(
        part_number='PN-100',
        description='Widget',
    )
    order = SimpleNamespace(
        pk=100,
        order_number='ORD-100',
        final_item=product,
        item=None,
        item_trade=None,
        brand=SimpleNamespace(title='Brand A'),
        final_weight=Decimal('0.250'),
        final_price=Decimal('12.50'),
        currency=SimpleNamespace(title='USD', title_en='Dollar'),
        description_trade='Trade description',
        description_sale='Sales description',
        part_number_mac='',
    )
    packing = SimpleNamespace(
        pk=9,
        packing_number='PK-009',
        bl_number='BL-009',
        bl_date=None,
        transportation_company='Carrier',
        origin='Shenzhen',
        destination='Tehran',
        estimated_shipping_start_date=None,
        estimated_arrive_to_wh_date=None,
    )
    item = SimpleNamespace(
        pk=1,
        order=order,
        packing=packing,
        carton_number='C-01',
        carton_quantity=3,
        brand='Brand A',
        category='Electronics',
        main_category='Hardware',
        part_number='PN-100',
        description='Widget',
        quantity=4,
        gross_weight_kg=Decimal('1.500'),
        net_weight_kg=Decimal('1.000'),
        size='40*30*20',
        volume=None,
        volume_is_confirmed=False,
        price=Decimal('12.50'),
    )
    return packing, [item]


class PackingExcelTests(SimpleTestCase):
    def load_export(self, include_prices):
        packing, items = sample_data()
        output = build_packing_workbook(
            packing, items, include_prices=include_prices,
        )
        self.assertIsInstance(output, BytesIO)
        return load_workbook(output, data_only=True)

    def test_export_contains_the_four_agreed_sheets(self):
        workbook = self.load_export(include_prices=True)
        self.assertEqual(
            workbook.sheetnames,
            ['Packing', 'Summary', 'Invoice', 'Packing List'],
        )

    def test_packing_sheet_preserves_agreed_a_b_i_and_m_columns(self):
        workbook = self.load_export(include_prices=True)
        sheet = workbook['Packing']
        self.assertEqual(sheet['A1'].value, 'Carton Number')
        self.assertEqual(sheet['B1'].value, 'Carton Quantity')
        self.assertEqual(sheet['C1'].value, 'Brand')
        self.assertEqual(sheet['I1'].value, 'Declared Weight (kg)')
        self.assertEqual(sheet['M1'].value, 'Calculated Weight (kg)')
        self.assertEqual(sheet['A2'].value, 'C-01')
        self.assertEqual(sheet['B2'].value, 3)
        self.assertEqual(sheet['C2'].value, 'Brand A')
        self.assertEqual(float(sheet['I2'].value), 1.5)
        self.assertEqual(float(sheet['M2'].value), 1.0)
        self.assertAlmostEqual(float(sheet['K2'].value), 0.024)
        summary = workbook['Summary']
        category_row = next(
            row for row in range(1, summary.max_row + 1)
            if summary.cell(row, 1).value == 'Category'
        )
        self.assertEqual(
            summary.auto_filter.ref,
            f'A{category_row}:D{summary.max_row}',
        )


    def test_export_button_is_present_on_the_packing_page(self):
        from pathlib import Path
        from django.conf import settings
        html = (
            Path(settings.BASE_DIR)
            / 'order/templates/order/packing/quick_packing_create.html'
        ).read_text(encoding='utf-8')
        self.assertIn('?export_excel=1', html)
        self.assertIn('packing_export_excel', html)

    def test_excel_export_requires_document_view_permission(self):
        from django.core.exceptions import PermissionDenied
        from unittest.mock import patch
        from types import SimpleNamespace
        from order.views import QuickPackingView

        packing = SimpleNamespace(
            user_can_view_workflow=lambda user: False,
        )
        view = QuickPackingView()
        request = SimpleNamespace(GET={'export_excel': '1'}, user=object())
        with patch.object(view, 'get_object', return_value=packing):
            with self.assertRaises(PermissionDenied):
                view.get(request, pk=9)

    def test_invoice_financial_columns_are_removed_without_permission(self):
        workbook = self.load_export(include_prices=False)
        headers = [cell.value for cell in workbook['Invoice'][1]]
        self.assertNotIn('Unit Price', headers)
        self.assertNotIn('Amount', headers)
        self.assertNotIn('Currency', headers)

    def test_invoice_financial_columns_are_present_with_permission(self):
        workbook = self.load_export(include_prices=True)
        sheet = workbook['Invoice']
        headers = [cell.value for cell in sheet[1]]
        self.assertIn('Unit Price', headers)
        self.assertIn('Amount', headers)
        self.assertEqual(float(sheet['G2'].value), 12.5)
        self.assertEqual(float(sheet['H2'].value), 50.0)
