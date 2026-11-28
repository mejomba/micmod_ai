from decimal import Decimal
from unittest import TestCase
from order.gio_weight import parse_manual_weight, summarize_weights


class GioWeightMathTests(TestCase):
    def test_multiple_rows_and_kg(self):
        result = summarize_weights([(1, 1000, '0.002'), (2, 3, '2.5')])
        self.assertEqual(result.calculated_weight_kg, Decimal('9.5'))
        self.assertEqual(result.effective_weight_kg, Decimal('9.5'))

    def test_incomplete_weight_keeps_known_subtotal(self):
        result = summarize_weights([(1, 2, 4), (2, 3, None), (3, 4, -1)])
        self.assertIsNone(result.calculated_weight_kg)
        self.assertEqual(result.known_weight_kg, 8)
        self.assertEqual(result.missing_row_ids, (2, 3))
        self.assertIsNone(result.effective_weight_kg)

    def test_empty_gio_is_unknown(self):
        self.assertIsNone(summarize_weights([]).effective_weight_kg)

    def test_manual_preserved_when_rows_change_and_reset(self):
        manual = parse_manual_weight('16000')
        for rows in ([(1, 12000, 1)], [(1, 15001, 1)], [(2, 2, None)]):
            self.assertEqual(summarize_weights(rows, manual).effective_weight_kg, 16000)
        self.assertEqual(summarize_weights([(1, 15001, 1)]).effective_weight_kg, 15001)

    def test_zero_override(self):
        result = summarize_weights([(1, 2, 4)], parse_manual_weight('0'))
        self.assertTrue(result.is_overridden)
        self.assertEqual(result.effective_weight_kg, 0)

    def test_invalid_manual_values(self):
        for value in (None, '', True, '-1', 'NaN', 'Infinity', '1000000000000', '0.0000001'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_manual_weight(value)

    def test_threshold_precision(self):
        self.assertEqual(parse_manual_weight('15000'), Decimal('15000'))
        self.assertGreater(parse_manual_weight('15000.001'), Decimal('15000'))
        self.assertEqual(summarize_weights([(1, 15000, 1), (2, 1, '0.001')]).effective_weight_kg, Decimal('15000.001'))

    def test_bad_quantity(self):
        for quantity in (0, -1, None, 'NaN', 'Infinity'):
            self.assertIsNone(summarize_weights([(1, quantity, 2)]).effective_weight_kg)
