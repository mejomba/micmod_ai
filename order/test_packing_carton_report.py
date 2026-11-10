"""Deterministic checks for outer-carton and independent Category views."""
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from order.packing_carton_report import (
    build_carton_report, carton_key, carton_size_key,
)


def row(pk, carton, category, part, qty, net, entered, volume, cartons=1, size='40x30x20'):
    order = SimpleNamespace(pk=pk, order_number='ORD-' + str(pk),
                            item=None, item_trade=None, final_weight=None)
    return SimpleNamespace(
        pk=pk, order=order, quantity=qty, carton_number=carton,
        carton_quantity=cartons, category=category, main_category='Independent',
        part_number=part, net_weight_kg=net, gross_weight_kg=entered,
        volume=volume, volume_is_confirmed=True, size=size, brand='Example',
    )


class CartonReportTests(SimpleTestCase):
    def test_same_carton_is_one_outer_carton_with_correct_weight_shares(self):
        items = [
            row(1, 'A-1', 'Electronics', 'Small', 10, 2, 3, '0.200000', 2),
            row(2, 'A-1', 'Mechanical', 'Large', 5, 6, 9, '0.700000', 3),
            row(3, 'B-2', 'Electronics', 'Other', 1, 1, 1, '0.050000', 1),
        ]
        report = build_carton_report(items)
        self.assertEqual(report['unique_carton_count'], 2)
        first = report['cartons'][0]
        self.assertEqual(first['number'], 'A-1')
        self.assertEqual(first['row_count'], 2)
        self.assertEqual(first['row_carton_quantity'], 5)
        self.assertEqual(first['main_item']['part_number'], 'Large')
        self.assertEqual(first['computed_weight'], Decimal('8'))
        self.assertEqual(first['entered_weight'], Decimal('12'))
        self.assertEqual(first['volume'], Decimal('0.900000'))
        self.assertEqual(first['rows'][0]['net_percent'], Decimal('75.00'))
        self.assertEqual(first['rows'][0]['entered_percent'], Decimal('75.00'))
        self.assertEqual(first['rows'][1]['net_percent'], Decimal('25.00'))
        self.assertEqual(first['rows'][1]['carton_quantity'], 2)
        self.assertEqual(len(report['category_groups']), 2)
        self.assertEqual(report['category_groups'][0]['cartons_count'], 2)
        self.assertEqual(report['category_groups'][1]['cartons_count'], 1)

    def test_missing_manual_weight_does_not_fake_a_total_or_percent(self):
        report = build_carton_report([
            row(1, 'C', 'A', 'A', 3, 1, 3, None),
            row(2, 'C', 'B', 'B', 7, 3, None, None),
        ])
        carton = report['cartons'][0]
        self.assertIsNone(carton['entered_weight'])
        self.assertIsNone(carton['rows'][0]['entered_percent'])
        row_a = next(row for row in carton['rows'] if row['part_number'] == 'A')
        self.assertEqual(row_a['net_percent'], Decimal('25.00'))

    def test_missing_numbers_are_not_counted_as_the_same_carton(self):
        report = build_carton_report([
            row(1, None, 'A', 'A', 1, 1, 1, None),
            row(2, '', 'A', 'B', 1, 1, 1, None),
        ])
        self.assertEqual(report['unique_carton_count'], 0)
        self.assertEqual(report['unassigned_row_count'], 2)
        self.assertEqual(len(report['cartons']), 2)


    def test_unconfirmed_saved_volume_is_replaced_by_dimension_formula(self):
        item = row(1, 'C-1', 'Electronics', 'Widget', 2, 1, 1, '0.900000')
        item.volume_is_confirmed = False
        report = build_carton_report([item])
        self.assertEqual(report['cartons'][0]['volume'], Decimal('0.024000'))

    def test_size_conflict_and_equivalent_case_or_spacing(self):
        self.assertEqual(carton_key('  A-1  '), carton_key('a-1'))
        self.assertEqual(carton_size_key('40 × 30 x 20'),
                         carton_size_key('40x30x20'))
        report = build_carton_report([
            row(1, 'C', 'A', 'A', 1, 1, 1, None, size='40x30x20'),
            row(2, 'C', 'A', 'B', 1, 1, 1, None, size='20x20x20'),
        ])
        self.assertEqual(report['size_conflicts'], 1)
        self.assertTrue(report['cartons'][0]['size_conflict'])
