"""Tests for the inline PackingItem volume field and its future formula hook."""
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from order.models import PackingItem
from order.packing_volume import (
    calculate_packing_volume, parse_packing_volume, resolve_packing_volume,
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

    def test_formula_not_guessed_and_manual_value_wins(self):
        self.assertIsNone(calculate_packing_volume(quantity=10, size='30x30x30'))
        self.assertIsNone(PackingItem(quantity=10).calculated_volume)
        self.assertIsNone(resolve_packing_volume(None, quantity=10))
        with patch('order.packing_volume.calculate_packing_volume',
                   return_value=Decimal('1.234567')):
            self.assertEqual(resolve_packing_volume(None, quantity=10), Decimal('1.234567'))
            self.assertEqual(
                resolve_packing_volume(Decimal('2.000000'), quantity=10),
                Decimal('2.000000'),
            )

    def test_new_row_parses_volume(self):
        view = QuickPackingView()
        request = SimpleNamespace(user=Mock(is_superuser=False), POST={
            'form-TOTAL_FORMS': '2', 'form-1-order': '14',
            'form-1-quantity': '5', 'form-1-volume': '1.000001',
        })
        self.assertEqual(view._parse_rows(request)[0]['volume'], Decimal('1.000001'))

    def test_existing_row_volume_is_optional_on_partial_post(self):
        view = QuickPackingView()
        post = {'existing-101-id': '101', 'existing-101-quantity': '5',
                'existing-101-volume': '2.123456'}
        self.assertEqual(
            view._parse_existing_rows(SimpleNamespace(POST=post))[0]['volume'],
            Decimal('2.123456'),
        )
        del post['existing-101-volume']
        self.assertNotIn('volume', view._parse_existing_rows(SimpleNamespace(POST=post))[0])

    def test_warehouse_only_ignores_tampered_volume(self):
        view = QuickPackingView()
        row = view._parse_existing_rows(SimpleNamespace(POST={
            'existing-101-id': '101', 'existing-101-volume': '3.5',
        }), warehouse_stage=True)[0]
        self.assertNotIn('volume', row)


class PackingVolumeTemplateTests(SimpleTestCase):
    def test_volume_and_warning_live_on_existing_packing_page(self):
        html = (
            Path(settings.BASE_DIR)
            / 'order/templates/order/packing/quick_packing_create.html'
        ).read_text(encoding='utf-8')
        self.assertIn('name="form-${index}-volume"', html)
        self.assertIn('name="existing-{{ packing_item.pk }}-volume"', html)
        self.assertIn('data-packing-volume', html)
        self.assertIn('pk-volume-warning', html)
        self.assertIn('packing_volume_override_warning', html)
        self.assertIn('volume_preview', html)
        self.assertIn('body.calculated_volume', html)
        self.assertIn('Math.abs(entered - calculated)', html)
