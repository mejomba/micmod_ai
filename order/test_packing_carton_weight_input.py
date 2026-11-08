"""User-entered row gross weight is optional and never guessed to be 0."""
from types import SimpleNamespace

from django.test import SimpleTestCase

from order.views import QuickPackingView


class PackingCartonWeightInputTests(SimpleTestCase):
    def test_blank_manual_weight_is_none_not_zero(self):
        view = QuickPackingView()
        self.assertIsNone(view._parse_gross_weight(None))
        self.assertIsNone(view._parse_gross_weight(''))
        self.assertEqual(view._parse_gross_weight('0'), 0.0)
        self.assertEqual(view._parse_gross_weight('1.5'), 1.5)

    def test_negative_or_invalid_weight_is_rejected(self):
        view = QuickPackingView()
        for raw in ('-1', 'NaN', 'Infinity', 'abc'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                view._parse_gross_weight(raw)

    def test_create_missing_manual_weight_has_no_fake_default(self):
        view = QuickPackingView()
        row = view._parse_rows(SimpleNamespace(
            POST={'form-TOTAL_FORMS': '2', 'form-1-order': '12', 'form-1-quantity': '2'},
            user=SimpleNamespace(is_superuser=False),
        ))[0]
        self.assertIsNone(row['gross_weight_kg'])

    def test_legacy_partial_post_does_not_clear_entered_weight(self):
        view = QuickPackingView()
        values = {'existing-4-id': '4', 'existing-4-quantity': '2'}
        row = view._parse_existing_rows(SimpleNamespace(POST=values))[0]
        self.assertNotIn('gross_weight_kg', row)
        values['existing-4-gross_weight_kg'] = ''
        row = view._parse_existing_rows(SimpleNamespace(POST=values))[0]
        self.assertIn('gross_weight_kg', row)
        self.assertIsNone(row['gross_weight_kg'])
        values['existing-4-gross_weight_kg'] = '0'
        row = view._parse_existing_rows(SimpleNamespace(POST=values))[0]
        self.assertEqual(row['gross_weight_kg'], 0.0)
