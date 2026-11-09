"""The per-Packing Overview must not report synthetic volumes or leak money."""
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.http import QueryDict
from django.test import SimpleTestCase

from order.models import PackingItem
from order.packing_volume import is_confirmed_packing_volume
from order.views import QuickPackingView


class ConfirmedVolumeTests(SimpleTestCase):
    def test_legacy_packing_volume_is_unverified_by_default(self):
        field = PackingItem._meta.get_field('volume_is_confirmed')
        self.assertEqual(field.get_internal_type(), 'BooleanField')
        self.assertIs(field.default, False)

    def test_only_positive_explicitly_approved_volume_is_reportable(self):
        self.assertTrue(is_confirmed_packing_volume(Decimal('0.123456'), True))
        self.assertFalse(is_confirmed_packing_volume(
            Decimal('0.123456'), True, generated=Decimal('0.123456'),
        ))
        self.assertTrue(is_confirmed_packing_volume(
            Decimal('0.123457'), True, generated=Decimal('0.123456'),
        ))
        for value, approved in (
            (Decimal('0.123456'), False),
            (None, True), ('', True), ('0', True), ('-1', True),
            ('NaN', True), ('Infinity', True), ('1.0000001', True),
        ):
            with self.subTest(value=value, approved=approved):
                self.assertFalse(is_confirmed_packing_volume(value, approved))

    def test_new_row_needs_explicit_volume_confirmation(self):
        post = QueryDict(mutable=True)
        post.update({
            'form-TOTAL_FORMS': '2',
            'form-1-order': '24',
            'form-1-quantity': '100',
            'form-1-volume': '0.321',
        })
        view = QuickPackingView()
        request = SimpleNamespace(POST=post, user=SimpleNamespace(is_superuser=False))
        self.assertFalse(view._parse_rows(request)[0]['volume_confirm'])
        post['form-1-volume_confirm'] = '1'
        self.assertTrue(view._parse_rows(request)[0]['volume_confirm'])

    def test_existing_row_supports_confirming_legacy_manual_volume(self):
        post = QueryDict(mutable=True)
        post.update({
            'existing-17-id': '17',
            'existing-17-quantity': '20',
            'existing-17-volume': '0.123',
        })
        view = QuickPackingView()
        request = SimpleNamespace(POST=post)
        self.assertFalse(view._parse_existing_rows(request)[0]['volume_confirm'])
        post['existing-17-volume_confirm'] = '1'
        self.assertTrue(view._parse_existing_rows(request)[0]['volume_confirm'])
        post['existing-17-volume'] = ''
        self.assertIsNone(view._parse_existing_rows(request)[0]['volume'])
        self.assertFalse(is_confirmed_packing_volume(
            view._parse_existing_rows(request)[0]['volume'],
            view._parse_existing_rows(request)[0]['volume_confirm'],
        ))


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

    def test_volume_comes_from_confirmed_saved_values_not_generated_proposal(self):
        self.assertIn(
            'data-overview-volume-confirmed="{{ packing_item.volume_is_confirmed',
            self.html,
        )
        self.assertIn(
            "row.dataset.overviewVolumeConfirmed === 'true'",
            self.html,
        )
        self.assertIn(
            'ovNumber(row.dataset.overviewVolume)',
            self.html,
        )
        self.assertIn(
            'name="existing-{{ packing_item.pk }}-volume_confirm"',
            self.html,
        )
        self.assertIn('name="form-${index}-volume_confirm"', self.html)
        self.assertIn("const allVolume = rows.length > 0 && incomplete.volume === 0", self.html)
        self.assertIn("put('pk-ov-cbm',allVolume?ovCbm(volume):'—')", self.html)

    def test_duplicate_outer_cartons_are_counted_once(self):
        self.assertIn("const groups = new Map(), cartons = new Map()", self.html)
        self.assertIn('if (!cartons.has(key)) cartons.set(key,new Set())', self.html)
        self.assertIn("put('pk-ov-cartons',allCartons?ovCount(cartons.size):'—')", self.html)

    def test_labels_exist_in_both_languages(self):
        self.assertEqual(self.html.count("packing_overview_missing_volume:"), 2)
        self.assertEqual(self.html.count("packing_overview_value_categories:"), 2)
        self.assertEqual(self.html.count("packing_volume_manual_confirm:"), 2)
