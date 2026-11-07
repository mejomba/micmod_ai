"""Read-only regression tests for SQL-backed sales history column filters."""
from datetime import date
from unittest.mock import patch, MagicMock
from decimal import Decimal

from django.test import SimpleTestCase

from sepidar.sales_history_service import (
    COLUMN_LABELS, _column_constraints, _column_date_bounds,
    _history_date, _document_types, _sepidar_invoice_needed,
    _read_sepidar_unique_rows, _sepidar_history, PORTAL_INVOICE_START,
    _portal_sepidar_quotation_matches, _matches_portal_quotation,
    get_sales_history_list,
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


class SalesHistorySourceOptimizationTests(SimpleTestCase):
    def test_cutoff_is_jalali_1405_02_10(self):
        self.assertEqual(PORTAL_INVOICE_START, date(2026, 4, 30))

    def test_no_sepidar_connection_for_portal_only_source(self):
        with patch('sepidar.sales_history_service._read_sepidar_unique_rows') as remote:
            self.assertEqual(_sepidar_history({'col_0': 'portal'}), [])
            remote.assert_not_called()

    def test_recent_invoice_only_needs_no_sepidar_query(self):
        for filters in (
            {'doc_type': 'invoice', 'date_from': '1405/02/10'},
            {'col_6': 'invoice', 'col_7': '1405/03'},
            {'doc_type': 'invoice', 'fisicalyearref': '48', 'date_from': '1405/02/10'},
        ):
            with self.subTest(filters=filters):
                self.assertFalse(_sepidar_invoice_needed(filters))
                with patch('sepidar.sales_history_service._portal_sepidar_quotation_matches') as ids:
                    with patch('sepidar.sales_history_service._read_sepidar_unique_rows') as remote:
                        self.assertEqual(_sepidar_history(filters), [])
                        ids.assert_not_called()
                        remote.assert_not_called()

    def test_old_invoices_still_read_from_sepidar(self):
        self.assertTrue(_sepidar_invoice_needed(
            {'doc_type': 'invoice', 'date_to': '1405/02/09'}))
        self.assertTrue(_sepidar_invoice_needed({'doc_type': 'invoice'}))

    def test_portal_quotation_query_excludes_linked_sepidar_quotation(self):
        # A Portal-linked quotation always stays in Portal; Sepidar does not
        # need a second matching row.
        cursor = MagicMock()
        cursor.description = [('doc_type',), ('sepidar_doc_id',), ('itemid',)]
        cursor.fetchmany.side_effect = [
            [('quotation', 71, 1), ('quotation', 72, 2),
             ('quotation', 71, 3), ('invoice', None, 4)],
            [],
        ]
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor
        with patch('sepidar.sales_history_service.connections', {'sepidar': connection}):
            rows = _read_sepidar_unique_rows('SELECT ...', [], {71}, set())
        self.assertEqual([(r['doc_type'], r['itemId']) for r in rows],
                         [('quotation', 2), ('invoice', 4)])
        cursor.execute.assert_called_once_with('SELECT ...', [])

    def test_different_quotations_and_invoice_types_are_not_confused(self):
        self.assertEqual(_document_types({'doc_type': 'quotation'}), {'quotation'})
        self.assertEqual(_document_types({'doc_type': 'invoice'}), {'invoice'})
        self.assertEqual(_document_types({'doc_type': 'invoice', 'col_6': 'quotation'}), set())
        self.assertEqual(_document_types({'doc_type': 'quotation', 'col_6': 'invoice'}), set())
        self.assertEqual(_document_types({'doc_type': 'invoice', 'col_6': 'invoice'}), {'invoice'})

    def test_conflicting_valid_document_types_do_not_query_sepidar(self):
        for filters in (
            {'doc_type': 'invoice', 'col_6': 'quotation'},
            {'doc_type': 'quotation', 'col_6': 'invoice'},
        ):
            with self.subTest(filters=filters):
                with patch('sepidar.sales_history_service._portal_sepidar_quotation_matches') as local:
                    with patch('sepidar.sales_history_service._read_sepidar_unique_rows') as remote:
                        self.assertEqual(_sepidar_history(filters), [])
                        local.assert_not_called()
                        remote.assert_not_called()

    def test_invalid_document_type_still_raises_validation_error(self):
        for key in ('doc_type', 'col_6'):
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, 'نوع سند انتخاب‌شده نامعتبر است'):
                    _document_types({key: 'unknown_type'})

    def test_combined_result_has_no_second_sepidar_lookup(self):
        with patch('sepidar.sales_history_service._sepidar_history', return_value=[]) as sepidar:
            with patch('sepidar.sales_history_service._portal_history', return_value=[]) as portal:
                rows, truncated = get_sales_history_list({'doc_type': 'invoice', 'date_from': '1405/02/10'})
        self.assertEqual(rows, [])
        self.assertFalse(truncated)
        sepidar.assert_called_once()
        portal.assert_called_once()

    def test_portal_number_2022_is_loaded_with_its_fiscal_year(self):
        # The user's reported example: sepidar_number, NOT the internal ID.
        queryset = MagicMock()
        queryset.values_list.return_value = [
            (None, 2022, date(2026, 5, 12)),
            (813, None, date(2026, 5, 15)),
            (None, 2022, date(2025, 5, 12)),
            (None, None, date(2026, 5, 12)),
        ]
        manager = MagicMock()
        manager.using.return_value.filter.return_value.exclude.return_value = queryset
        with patch('sepidar.sales_history_service.Quotation.objects', manager):
            ids, numbers = _portal_sepidar_quotation_matches()
        self.assertEqual(ids, {813})
        self.assertEqual(numbers, {(48, 2022), (46, 2022)})
        manager.using.assert_called_once_with('default')

    def test_number_2022_matches_without_matching_internal_id(self):
        ids = set()
        numbers = {(48, 2022)}
        duplicate = {'doc_type': 'quotation', 'sepidar_doc_id': 99999,
                     'fiscalyearref': 48, 'number': 2022}
        other_year = dict(duplicate, fiscalyearref=46)
        other_number = dict(duplicate, number=2023)
        other_type = dict(duplicate, doc_type='invoice')
        self.assertTrue(_matches_portal_quotation(duplicate, ids, numbers))
        self.assertFalse(_matches_portal_quotation(other_year, ids, numbers))
        self.assertFalse(_matches_portal_quotation(other_number, ids, numbers))
        self.assertFalse(_matches_portal_quotation(other_type, ids, numbers))
        self.assertTrue(_matches_portal_quotation(
            dict(other_year, sepidar_doc_id=813), {813}, numbers
        ))

    def test_sql_excludes_portal_number_2022_before_top(self):
        with patch('sepidar.sales_history_service._portal_sepidar_quotation_matches',
                   return_value=(set(), {(48, 2022)})):
            with patch('sepidar.sales_history_service._read_sepidar_unique_rows',
                       return_value=[]) as read:
                self.assertEqual(_sepidar_history({'doc_type': 'quotation'}), [])
        sql, params, ids, numbers = read.call_args.args
        self.assertIn('SELECT TOP (3001)', sql)
        self.assertIn('docs.FiscalYearRef = %s AND docs.Number IS NOT NULL', sql)
        self.assertIn('AND docs.Number IN (%s)', sql)
        self.assertIn("docs.doc_type <> 'quotation' OR NOT", sql)
        self.assertIn('docs.FiscalYearRef,', sql)
        self.assertEqual(params[-2:], [48, 2022])
        self.assertEqual(ids, set())
        self.assertEqual(numbers, {(48, 2022)})

    def test_small_linked_ids_and_numbers_are_excluded_in_one_sql_query(self):
        with patch('sepidar.sales_history_service._portal_sepidar_quotation_matches',
                   return_value=({71, 72}, {(48, 2022)})):
            with patch('sepidar.sales_history_service._read_sepidar_unique_rows',
                       return_value=[]) as read:
                self.assertEqual(_sepidar_history({'doc_type': 'quotation'}), [])
        sql, params, ids, numbers = read.call_args.args
        self.assertIn('SELECT TOP (3001)', sql)
        self.assertIn('docs.sepidar_doc_id IN (%s, %s)', sql)
        self.assertIn('docs.FiscalYearRef = %s AND docs.Number IS NOT NULL', sql)
        self.assertIn('AND docs.Number IN (%s)', sql)
        self.assertEqual(params[-4:], [71, 72, 48, 2022])
        self.assertEqual(ids, {71, 72})
        self.assertEqual(numbers, {(48, 2022)})

    def test_large_linked_quotation_set_uses_single_cursor_stream(self):
        ids = set(range(1, 1002))
        with patch('sepidar.sales_history_service._portal_sepidar_quotation_matches',
                   return_value=(ids, {(48, 2022)})):
            with patch('sepidar.sales_history_service._read_sepidar_unique_rows',
                       return_value=[]) as read:
                self.assertEqual(_sepidar_history({'doc_type': 'quotation'}), [])
        sql, params, excluded_ids, excluded_numbers = read.call_args.args
        self.assertNotIn('SELECT TOP (3001)', sql)
        self.assertNotIn('docs.sepidar_doc_id IN (', sql)
        self.assertNotIn('docs.FiscalYearRef = %s AND docs.Number IN (', sql)
        self.assertEqual(excluded_ids, ids)
        self.assertEqual(excluded_numbers, {(48, 2022)})

    def test_streamed_rows_remove_matching_number_and_preserve_other_year(self):
        cursor = MagicMock()
        cursor.description = [
            ('doc_type',), ('sepidar_doc_id',), ('fiscalyearref',),
            ('number',), ('itemid',),
        ]
        cursor.fetchmany.side_effect = [[
            ('quotation', 900, 48, 2022, 1),
            ('quotation', 901, 46, 2022, 2),
            ('quotation', 902, 48, 2023, 3),
        ], []]
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor
        with patch('sepidar.sales_history_service.connections', {'sepidar': connection}):
            rows = _read_sepidar_unique_rows(
                'SELECT ...', [], set(), {(48, 2022)}
            )
        self.assertEqual([row['itemId'] for row in rows], [2, 3])
        cursor.execute.assert_called_once_with('SELECT ...', [])

