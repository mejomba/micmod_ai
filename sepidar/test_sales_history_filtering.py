"""Read-only regression tests for SQL-backed sales history column filters."""
from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from sepidar.sales_history_service import (
    COLUMN_LABELS, _column_constraints, _column_date_bounds,
    _history_date,
)


class SalesHistoryColumnFilterTests(SimpleTestCase):
    def test_eighteen_report_columns(self):
        self.assertEqual(len(COLUMN_LABELS), 18)

    def test_source_restricts_query_before_loading(self):
        self.assertEqual(_column_constraints({'col_0': 'portal'}, 'sepidar'), ([], [], True))
        self.assertEqual(_column_constraints({'col_0': 'sepidar'}, 'portal'), ([], [], True))

    def test_customer_search_uses_bound_parameters(self):
        value = "تهران' OR 1=1--"
        expressions, params, skipped = _column_constraints({'col_2': value}, 'portal')
        self.assertFalse(skipped)
        self.assertEqual(len(expressions), 1)
        self.assertIn('ILIKE %s', expressions[0])
        self.assertNotIn(value, expressions[0])
        self.assertEqual(params, ['%' + value + '%'])

    def test_numeric_filter_is_server_side_and_exact(self):
        sql, params, skipped = _column_constraints({'col_12': '۲۵', 'col_13': '1,000'}, 'sepidar')
        self.assertFalse(skipped)
        self.assertEqual(len(sql), 2)
        self.assertEqual(params, [Decimal('25'), Decimal('1000')])

    def test_invalid_types_and_numbers_are_rejected(self):
        with self.assertRaises(ValueError):
            _column_constraints({'col_6': 'not_a_document_type'}, 'portal')
        with self.assertRaises(ValueError):
            _column_constraints({'col_13': 'not_a_number'}, 'portal')
        with self.assertRaises(ValueError):
            _column_constraints({'col_0': 'unexpected_source'}, 'portal')

    def test_gregorian_and_jalali_input(self):
        self.assertEqual(_history_date('2026-11-04'), date(2026, 11, 4))
        self.assertEqual(_history_date('۱۴۰۵/۰۸/۱۳'), date(2026, 11, 4))

    def test_jalali_month_range(self):
        start, end = _column_date_bounds('۱۴۰۵/۰۸')
        self.assertLess(start, end)
        self.assertEqual(start, _history_date('۱۴۰۵/۰۸/۰۱'))
        self.assertEqual(end, _history_date('۱۴۰۵/۰۹/۰۱'))

    def test_date_bounds_use_inclusive_start_exclusive_end(self):
        sql, params, skipped = _column_constraints(
            {'date_from': '1405/08/01', 'date_to': '1405/08/13'}, 'portal'
        )
        self.assertFalse(skipped)
        self.assertEqual(len(sql), 2)
        self.assertIn(' >= %s', sql[0])
        self.assertIn(' < %s', sql[1])
        self.assertEqual(params[0], _history_date('1405/08/01'))
        self.assertEqual(params[1], date(2026, 11, 5))

    def test_reversed_date_bounds_rejected(self):
        with self.assertRaises(ValueError):
            _column_constraints(
                {'date_from': '1405/08/13', 'date_to': '1405/08/01'}, 'sepidar'
            )
