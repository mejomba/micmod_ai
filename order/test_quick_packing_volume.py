"""Tests for Packing CBM calculation, validation, and manual overrides."""
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import SimpleTestCase

from order.forms import PackingItemForm
from order.models import PackingItem
from order.packing_volume import (
    calculate_packing_volume, parse_packing_size, parse_packing_volume,
    resolve_packing_volume,
)
from order.views import QuickPackingView


class QuickPackingVolumeTests(SimpleTestCase):
    def test_volume_field_is_nullable_decimal_with_nonnegative_validator(self):
        field = PackingItem._meta.get_field('volume')
        self.assertEqual((field.max_digits, field.decimal_places), (18, 6))
        self.assertTrue(field.null)
        self.assertTrue(field.blank)
        field.run_validators(Decimal('0'))
        with self.assertRaises(ValidationError):
            field.run_validators(Decimal('-1'))

    def test_manual_volume_is_exact_and_nullable(self):
        self.assertEqual(parse_packing_volume('0.123456'), Decimal('0.123456'))
        self.assertIsNone(parse_packing_volume(''))
        self.assertIsNone(parse_packing_volume(None))
        for value in ('-1', 'abc', 'NaN', 'Infinity', '0.0000001', '1000000000000'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_packing_volume(value)

    def test_size_parser_accepts_supported_separators(self):
        expected = (Decimal('40'), Decimal('30'), Decimal('20'))
        for size in ('40*30*20', '40x30x20', '40 × 30 × 20', '40 X 30 X 20'):
            with self.subTest(size=size):
                self.assertEqual(parse_packing_size(size), expected)
        self.assertIsNone(parse_packing_size(''))

    def test_size_parser_rejects_missing_extra_or_nonpositive_dimensions(self):
        for size in ('40*30', '40*30*20*10', '40/30/20', '0*30*20', '-1*30*20', 'a*30*20'):
            with self.subTest(size=size), self.assertRaises(ValueError):
                parse_packing_size(size)

    def test_calculates_cbm_from_length_width_height(self):
        self.assertEqual(
            calculate_packing_volume(size='30*30*30'),
            Decimal('0.027000'),
        )
        self.assertEqual(
            calculate_packing_volume(size='40 × 30 x 20'),
            Decimal('0.024000'),
        )
        self.assertIsNone(calculate_packing_volume(size=''))


    def test_calculated_volume_rejects_values_outside_decimal_field_range(self):
        with self.assertRaises(ValueError):
            calculate_packing_volume(size='1000000*1000000*1000000')

    def test_manual_volume_is_preserved_only_when_confirmed(self):
        params = {'size': '30*30*30'}
        manual = Decimal('0.500000')
        self.assertEqual(
            resolve_packing_volume(manual, is_confirmed=True, **params),
            manual,
        )
        self.assertEqual(
            resolve_packing_volume(manual, is_confirmed=False, **params),
            Decimal('0.027000'),
        )
        self.assertEqual(
            resolve_packing_volume(None, is_confirmed=False, **params),
            Decimal('0.027000'),
        )


    def test_effective_volume_uses_formula_unless_manual_value_is_confirmed(self):
        item = PackingItem(
            size='30*30*30',
            volume=Decimal('0.500000'),
            volume_is_confirmed=False,
        )
        self.assertEqual(item.calculated_volume, Decimal('0.027000'))
        self.assertEqual(item.effective_volume, Decimal('0.027000'))
        item.volume_is_confirmed = True
        self.assertEqual(item.effective_volume, Decimal('0.500000'))

    def test_new_row_validates_size_and_parses_volume_confirmation(self):
        view = QuickPackingView()
        request = SimpleNamespace(user=Mock(is_superuser=False), POST={
            'form-TOTAL_FORMS': '2', 'form-1-order': '14',
            'form-1-quantity': '5', 'form-1-size': '30*30*30',
            'form-1-volume': '0.500000',
            'form-1-volume_is_confirmed': '1',
        })
        row = view._parse_rows(request)[0]
        self.assertEqual(row['volume'], Decimal('0.500000'))
        self.assertTrue(row['volume_is_confirmed'])
        self.assertEqual(row['size'], '30*30*30')

    def test_new_row_rejects_invalid_size_on_server(self):
        view = QuickPackingView()
        request = SimpleNamespace(user=Mock(is_superuser=False), POST={
            'form-TOTAL_FORMS': '2', 'form-1-order': '14',
            'form-1-quantity': '5', 'form-1-size': '30*20',
        })
        with self.assertRaises(ValueError):
            view._parse_rows(request)

    def test_existing_row_volume_is_optional_on_partial_post(self):
        view = QuickPackingView()
        post = {
            'existing-101-id': '101',
            'existing-101-quantity': '5',
            'existing-101-size': '30*30*30',
            'existing-101-volume': '0.123456',
            'existing-101-volume_is_confirmed': '1',
        }
        row = view._parse_existing_rows(SimpleNamespace(POST=post))[0]
        self.assertEqual(row['volume'], Decimal('0.123456'))
        self.assertTrue(row['volume_is_confirmed'])
        del post['existing-101-volume']
        self.assertNotIn('volume', view._parse_existing_rows(SimpleNamespace(POST=post))[0])

    def test_warehouse_only_ignores_tampered_volume(self):
        view = QuickPackingView()
        row = view._parse_existing_rows(SimpleNamespace(POST={
            'existing-101-id': '101',
            'existing-101-volume': '3.5',
            'existing-101-size': '30*30*30',
            'existing-101-volume_is_confirmed': '1',
        }), warehouse_stage=True)[0]
        self.assertNotIn('volume', row)
        self.assertNotIn('volume_is_confirmed', row)


class PackingVolumeTemplateTests(SimpleTestCase):
    def test_volume_and_size_validation_live_on_existing_packing_page(self):
        html = (
            Path(settings.BASE_DIR)
            / 'order/templates/order/packing/quick_packing_create.html'
        ).read_text(encoding='utf-8')
        self.assertIn('name="form-${index}-volume"', html)
        self.assertIn('name="form-${index}-volume_is_confirmed"', html)
        self.assertIn('name="existing-{{ packing_item.pk }}-volume_is_confirmed"', html)
        self.assertIn('data-packing-volume', html)
        self.assertIn('pk-volume-warning', html)
        self.assertIn('pk-size-format-warning', html)
        self.assertIn('packing_size_format_invalid', html)
        self.assertIn('packing_volume_calculation_hint', html)
        self.assertIn('volume_preview', html)
        self.assertIn('body.calculated_volume', html)
        self.assertIn('parsePackingSizeClient', html)
        self.assertNotIn('packing_volume_test_hint', html)
        self.assertNotIn('temporary stable pseudo-random', html)


class PackingVolumePermissionTests(SimpleTestCase):
    def test_warehouse_model_form_keeps_volume_readonly(self):
        source = (
            Path(settings.BASE_DIR) / 'order/forms.py'
        ).read_text(encoding='utf-8')
        self.assertIn("'gross_weight_kg',\n                    'volume',", source)

    def test_same_page_preview_requires_create_permission(self):
        view = QuickPackingView()
        request = SimpleNamespace(
            GET={'volume_preview': '1', 'size': '30*30*30'},
            user=Mock(),
        )
        with patch.object(view, '_assert_create_access', side_effect=PermissionDenied):
            with self.assertRaises(PermissionDenied):
                view.get(request)

    def test_preview_returns_calculated_cbm(self):
        import json
        view = QuickPackingView()
        request = SimpleNamespace(
            GET={'volume_preview': '1', 'size': '30*30*30'}, user=Mock(),
        )
        with patch.object(view, '_assert_create_access'):
            response = view.get(request)
        self.assertEqual(response.status_code, 200)
        result = Decimal(json.loads(response.content)['calculated_volume'])
        self.assertEqual(result, Decimal('0.027000'))

    def test_preview_returns_localizable_error_for_invalid_size(self):
        import json
        view = QuickPackingView()
        request = SimpleNamespace(
            GET={'volume_preview': '1', 'size': '30*20'}, user=Mock(),
        )
        with patch.object(view, '_assert_create_access'):
            response = view.get(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content)['error_code'],
            'packing_err_invalid_size',
        )
