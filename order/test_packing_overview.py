"""Regression coverage for read-only per-Packing Overview calculations.

Automatic CBM is derived from dimensions; confirmed manual values are preserved.
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
    def test_calculated_volume_uses_dimensions_and_is_available_without_manual_confirmation(self):
        generated = calculate_packing_volume(size='40x30x20')
        self.assertEqual(generated, Decimal('0.024000'))
        self.assertEqual(
            resolve_packing_volume(
                None, size='40x30x20', is_confirmed=False,
            ),
            generated,
        )
        self.assertEqual(parse_packing_volume(str(generated)), generated)

    def test_manual_volume_remains_authoritative_when_confirmed(self):
        entered = Decimal('0.123456')
        self.assertEqual(
            resolve_packing_volume(
                entered, size='40x30x20', is_confirmed=True,
            ),
            entered,
        )
        self.assertEqual(
            resolve_packing_volume(
                entered, size='40x30x20', is_confirmed=False,
            ),
            Decimal('0.024000'),
        )

    def test_missing_or_invalid_volume(self):
        self.assertIsNone(parse_packing_volume(''))
        self.assertIsNone(parse_packing_volume(None))
        for value in ('-1', 'NaN', 'Infinity', '1.1234567'):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_packing_volume(value)

    def test_new_row_marks_manual_volume_as_confirmed(self):
        post = QueryDict(mutable=True)
        post.update({
            'form-TOTAL_FORMS': '2',
            'form-1-order': '24',
            'form-1-quantity': '100',
            'form-1-size': '40x30x20',
            'form-1-volume': '0.321',
            'form-1-volume_is_confirmed': '1',
        })
        view = QuickPackingView()
        request = SimpleNamespace(
            POST=post, user=SimpleNamespace(is_superuser=False),
        )
        row = view._parse_rows(request)[0]
        self.assertEqual(row['volume'], Decimal('0.321000'))
        self.assertTrue(row['volume_is_confirmed'])

    def test_existing_row_marks_manual_volume_as_confirmed(self):
        post = QueryDict(mutable=True)
        post.update({
            'existing-17-id': '17',
            'existing-17-quantity': '20',
            'existing-17-size': '40x30x20',
            'existing-17-volume': '0.123',
            'existing-17-volume_is_confirmed': '1',
        })
        view = QuickPackingView()
        request = SimpleNamespace(POST=post)
        row = view._parse_existing_rows(request)[0]
        self.assertEqual(row['volume'], Decimal('0.123000'))
        self.assertTrue(row['volume_is_confirmed'])
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
        self.assertIn('data-overview-volume="{{ packing_item.effective_volume', self.html)
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

    def test_overview_includes_general_packing_and_shipment_metadata(self):
        for expected in (
            'packing_object.packing_number',
            'packing_object.shipment_type',
            'packing_object.bl_number',
            'packing_object.bl_date',
            'packing_object.transportation_company',
            'packing_object.origin',
            'packing_object.destination',
            'packing_object.departure_date',
            'packing_object.arrival_date',
            'packing_object.estimated_shipping_start_date',
            'packing_object.estimated_arrive_to_wh_date',
            'packing_object.order_registration_number',
            'packing_object.proforma_pi_number',
            'packing_object.commercial_card',
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, self.html)

    def test_financial_breakdown_uses_existing_currency_permission_and_rates(self):
        self.assertIn(
            '{% if can_view_prices %}\n                <article class="pk-ov-card pk-ov-finance-card">',
            self.html,
        )
        for expected in (
            'id="pk-ov-target-currency"',
            'id="pk-ov-source-totals"',
            'id="pk-ov-finance-status"',
            'data-overview-price="{{ packing_item.price|default_if_none:',
            'const allMoney = allSourceMoney && incomplete.rate === 0;',
            'const rate = target ? fxRateFor(source.id) : null;',
            'fxMoney(source.amount*rate)',
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, self.html)

    def test_row_level_price_data_is_guarded_by_finance_permission(self):
        row_start = self.html.index('class="packing-selected-row packing-existing-row"')
        permission_start = self.html.index('{% if can_view_prices %}', row_start)
        price_attribute = self.html.index('data-overview-price=', row_start)
        permission_end = self.html.index('{% endif %}', permission_start)
        self.assertLess(permission_start, price_attribute)
        self.assertLess(price_attribute, permission_end)

    def test_aggregated_order_part_category_and_warehouse_values(self):
        for expected in (
            'id="pk-ov-row-count"',
            'id="pk-ov-order-count"',
            'id="pk-ov-part-count"',
            'id="pk-ov-category-count"',
            'id="pk-ov-inner-cartons"',
            'innerCartonCount',
            'innerCartons += r.innerCartonCount',
            'id="pk-ov-received"',
            'id="pk-ov-good"',
            'id="pk-ov-damaged"',
            'id="pk-ov-remaining"',
            'data-overview-part-number="{{ packing_item.part_number',
            'data-overview-received="{{ packing_item.wh_receipt_quantity',
            'data-overview-damaged="{{ packing_item.ruined_quantity',
            'goodTotal += r.received - r.damaged',
            'remainingTotal += r.qty - r.received',
            "put('pk-ov-order-count',allOrders?ovCount(orders.size):'—')",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, self.html)

    def test_overview_issues_identify_affected_row_and_item(self):
        for expected in (
            'row.querySelector(\'.pk-row-part span:first-child b\')',
            'rows.push({rowNumber:rows.length+1',
            'const sku = String(',
            'const affectedRows = rows.filter(row => hasIssue(row,field))',
            "list.className='pk-ov-issue-list'",
            "const item=document.createElement('li')",
            "'Row {row} — Item: {item}'",
            "'ردیف {row} — کالا: {item}'",
            "['qty','packing_overview_missing_quantity']",
            "['order','packing_overview_missing_order']",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, self.html)

    def test_category_colors_match_between_value_and_quantity_charts(self):
        color_map = (
            'const categoryColors = new Map(',
            '[...groups.keys()].sort((a,b)=>a.localeCompare(b))',
            'bar.style.backgroundColor=categoryColors.get(name) || ovPalette[0]',
            'const hue=categoryColors.get(name) || ovPalette[0]',
        )
        for expected in color_map:
            with self.subTest(expected=expected):
                self.assertIn(expected, self.html)

    def test_category_charts_show_percentage_of_total(self):
        self.assertIn(
            "function ovPercent(value) {\n        return Number(value).toLocaleString('en-US', {maximumFractionDigits: 1});\n    }",
            self.html,
        )
        percentage_features = (
            'function ovPercent(value)',
            'values.value*100/totalValue',
            "bar.style.width=share+'%'",
            "percent.textContent=ovPercent(share)+'%'",
            'id="pk-ov-donut-labels"',
            'values.quantity*100/quantity',
            'share >= 6',
            "right.textContent=ovCount(values.quantity)+' · '+ovPercent(share)+'%'",
        )
        for expected in percentage_features:
            with self.subTest(expected=expected):
                self.assertIn(expected, self.html)

    def test_labels_exist_in_both_languages(self):
        for key in (
            'packing_overview_missing_volume:',
            'packing_overview_value_categories:',
            'packing_overview_note:',
            'packing_overview_meta:',
            'packing_overview_finance:',
            'packing_overview_received:',
            'packing_overview_missing_receipt:',
            'packing_overview_missing_price:',
            'packing_overview_inner_cartons:',
            'packing_overview_rate_direction:',
            'packing_overview_missing_inner_cartons:',
            'packing_overview_missing_quantity:',
            'packing_overview_missing_order:',
            'packing_overview_row_item:',
            'packing_overview_unknown_item:',
        ):
            with self.subTest(key=key):
                self.assertEqual(self.html.count(key), 2)
        self.assertNotIn('packing_volume_manual_confirm:', self.html)
