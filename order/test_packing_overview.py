"""Regression coverage for read-only per-Packing Overview calculations.

Saved positive volume participates in CBM regardless of how it was obtained.
The legacy confirmation marker is deliberately not consulted by Overview.
"""
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.http import QueryDict
from django.test import SimpleTestCase

from order.packing_volume import (
    calculate_packing_volume,
    parse_packing_volume,
    resolve_packing_volume,
)
from order.views import QuickPackingView


class PackingOverviewVolumeTests(SimpleTestCase):
    def test_calculated_volume_is_accepted_without_confirmation(self):
        generated = calculate_packing_volume(
            quantity=10, size='40x30x20', carton_quantity=5, order_id=24,
        )
        self.assertGreater(generated, Decimal('0'))
        self.assertEqual(
            resolve_packing_volume(
                None, quantity=10, size='40x30x20',
                carton_quantity=5, order_id=24,
            ),
            generated,
        )
        self.assertEqual(parse_packing_volume(str(generated)), generated)

    def test_manual_volume_remains_authoritative(self):
        entered = Decimal('0.123456')
        self.assertEqual(
            resolve_packing_volume(
                entered, quantity=10, size='40x30x20',
                carton_quantity=5, order_id=24,
            ),
            entered,
        )

    def test_missing_or_invalid_volume(self):
        self.assertIsNone(parse_packing_volume(''))
        self.assertIsNone(parse_packing_volume(None))
        for value in ('-1', 'NaN', 'Infinity', '1.1234567'):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_packing_volume(value)

    def test_new_row_needs_no_checkbox_for_manual_volume(self):
        post = QueryDict(mutable=True)
        post.update({
            'form-TOTAL_FORMS': '2',
            'form-1-order': '24',
            'form-1-quantity': '100',
            'form-1-volume': '0.321',
        })
        view = QuickPackingView()
        request = SimpleNamespace(
            POST=post, user=SimpleNamespace(is_superuser=False),
        )
        row = view._parse_rows(request)[0]
        self.assertEqual(row['volume'], Decimal('0.321000'))
        self.assertNotIn('volume_confirm', row)

    def test_existing_row_needs_no_checkbox_for_manual_volume(self):
        post = QueryDict(mutable=True)
        post.update({
            'existing-17-id': '17',
            'existing-17-quantity': '20',
            'existing-17-volume': '0.123',
        })
        view = QuickPackingView()
        request = SimpleNamespace(POST=post)
        row = view._parse_existing_rows(request)[0]
        self.assertEqual(row['volume'], Decimal('0.123000'))
        self.assertNotIn('volume_confirm', row)
        post['existing-17-volume'] = ''
        self.assertIsNone(view._parse_existing_rows(request)[0]['volume'])


class PackingOverviewTemplateTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.html = (
            Path(settings.BASE_DIR)
            / 'order/templates/order/packing/quick_packing_create.html'
        ).read_text(encoding='utf-8')

    def test_overview_is_separate_accessible_tab_for_existing_packing(self):
        self.assertIn('{% if packing_object %}\n            <div class="pk-ov-tabs"', self.html)
        for expected in (
            'id="pk-tab-details"', 'id="pk-tab-overview"',
            'id="pk-overview-panel"', 'role="tabpanel"',
            'aria-selected="true"', 'ovShowTab(name)', 'ovRender()',
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, self.html)

    def test_only_authorized_users_receive_financial_overview_elements(self):
        self.assertIn(
            '{% if can_view_prices %}\n                    <div class="pk-ov-kpi">',
            self.html,
        )
        self.assertIn(
            '{% if can_view_prices %}\n                    <article class="pk-ov-card">',
            self.html,
        )
        self.assertIn('const currencyId = canViewPrices ?', self.html)
        self.assertIn('const unitPrice = canViewPrices ?', self.html)
        self.assertIn('const target = canViewPrices ?', self.html)

    def test_saved_volume_counts_without_checkbox_or_legacy_marker(self):
        self.assertIn('data-overview-volume="{{ packing_item.volume', self.html)
        self.assertIn(
            'const volume = isSaved ? ovNumber(row.dataset.overviewVolume) : null;',
            self.html,
        )
        self.assertNotIn('overviewVolumeConfirmed', self.html)
        self.assertNotIn('volume_confirm', self.html)
        self.assertNotIn('pk-volume-confirm', self.html)
        self.assertIn(
            'const allVolume = rows.length > 0 && incomplete.volume === 0',
            self.html,
        )
        self.assertIn(
            "put('pk-ov-cbm',allVolume?ovCbm(volume):'—')",
            self.html,
        )

    def test_missing_volume_is_visible_not_invented(self):
        self.assertIn("if (r.volume === null) incomplete.volume++", self.html)
        self.assertIn("put('pk-ov-cbm',allVolume?ovCbm(volume):'—')", self.html)
        self.assertIn('Volume is missing or invalid', self.html)

    def test_duplicate_outer_cartons_are_counted_once(self):
        self.assertIn('const groups = new Map(), cartons = new Map()', self.html)
        self.assertIn('if (!cartons.has(key)) cartons.set(key,new Set())', self.html)
        self.assertIn(
            "put('pk-ov-cartons',allCartons?ovCount(cartons.size):'—')",
            self.html,
        )

    def test_labels_exist_in_both_languages(self):
        self.assertEqual(self.html.count('packing_overview_missing_volume:'), 2)
        self.assertEqual(self.html.count('packing_overview_value_categories:'), 2)
        self.assertEqual(self.html.count('packing_overview_note:'), 2)
        self.assertNotIn('packing_volume_manual_confirm:', self.html)
