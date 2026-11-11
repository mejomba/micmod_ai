"""Source-currency breakdown and validated, persisted FX preferences."""
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from micmod_base.base import Currency
from order.forms import PackingSafeForm
from order.models import Packing
from order.packing_currency_rates import normalize_packing_currency_rates
from order.views import QuickPackingView, QuickPackingDataTableListView


class PackingExchangePreferenceTests(SimpleTestCase):
    def test_model_stores_preferences_but_never_computed_total(self):
        field = Packing._meta.get_field('currency_exchange_rates')
        self.assertEqual(field.get_default(), {})
        self.assertEqual(field.get_internal_type(), 'JSONField')
        self.assertIsNone(Packing().currency_id)
        self.assertFalse(any(
            name in (f.name for f in Packing._meta.fields)
            for name in ('converted_total', 'fx_total', 'converted_value')
        ))

    def test_normalized_fx_rates_are_positive_decimal_strings(self):
        data = {
            'target_currency_id': '3',
            'rates': {'1': '1.25000000', '2': '1200.12345678'},
        }
        normalized = normalize_packing_currency_rates(
            data, 3, valid_currency_ids=(1, 2, 3),
        )
        self.assertEqual(normalized, {
            'target_currency_id': '3',
            'rates': {'1': '1.25', '2': '1200.12345678'},
        })
        self.assertEqual(
            normalize_packing_currency_rates({}, None, valid_currency_ids=(1,2)),
            {},
        )

    def test_reject_invalid_rates_and_stale_destination(self):
        for raw in ('-1', '0', 'NaN', 'Infinity', 'abc', '1.000000001', True):
            with self.subTest(raw=raw), self.assertRaises(ValidationError):
                normalize_packing_currency_rates({
                    'target_currency_id': '3', 'rates': {'1': raw},
                }, 3, valid_currency_ids=(1, 2, 3))
        with self.assertRaises(ValidationError):
            normalize_packing_currency_rates({
                'target_currency_id': '3', 'rates': {'1': '1.2'},
            }, 2, valid_currency_ids=(1, 2, 3))
        with self.assertRaises(ValidationError):
            normalize_packing_currency_rates({
                'target_currency_id': '3', 'rates': {'44': '1.2'},
            }, 3, valid_currency_ids=(1, 2, 3))
        with self.assertRaises(ValidationError):
            normalize_packing_currency_rates({
                'target_currency_id': '3', 'rates': {'3': '1'},
            }, 3, valid_currency_ids=(1, 2, 3))

    def test_partial_workflow_posts_keep_target_and_rates(self):
        view = QuickPackingView()
        view.request = SimpleNamespace(user=Mock(is_superuser=False))
        view._workflow_constraint = Mock(return_value={
            'form_state': 2, 'wf_access': True,
            'form_constraint': [{'read': []} for _ in range(10)],
        })
        view._is_warehouse_stage = Mock(return_value=False)
        packing = Mock()
        with patch.object(view, 'form_class') as form_factory, \
             patch.object(Packing, 'user_can_view_prices', return_value=True):
            view._build_form(
                packing_obj=packing, data={'description': 'Workflow-only edit'},
            )
        fields = form_factory.call_args.kwargs['allowed_fields']
        self.assertNotIn('currency', fields)
        self.assertNotIn('currency_exchange_rates', fields)

    def test_rate_preferences_require_currency_and_price_permissions(self):
        view = QuickPackingView()
        user = Mock(is_superuser=False)
        view.request = SimpleNamespace(user=user)
        view._workflow_constraint = Mock(return_value={
            'form_state': 2, 'wf_access': True,
            'form_constraint': [{'read': []} for _ in range(10)],
        })
        view._is_warehouse_stage = Mock(return_value=False)
        submitted = {'currency': '2', 'currency_exchange_rates': '{}'}
        with patch.object(view, 'form_class') as form_factory, \
             patch.object(Packing, 'user_can_view_prices', return_value=True):
            view._build_form(packing_obj=Mock(), data=submitted)
        fields = form_factory.call_args.kwargs['allowed_fields']
        self.assertIn('currency_exchange_rates', fields)
        with patch.object(view, 'form_class') as form_factory, \
             patch.object(Packing, 'user_can_view_prices', return_value=False):
            view._build_form(packing_obj=Mock(), data=submitted)
        fields = form_factory.call_args.kwargs['allowed_fields']
        self.assertNotIn('currency_exchange_rates', fields)
        self.assertNotIn('currency', fields)


class PackingExchangeFormTests(TestCase):
    def setUp(self):
        self.usd = Currency.objects.create(title='دلار', title_en='USD')
        self.eur = Currency.objects.create(title='یورو', title_en='EUR')

    def test_form_saves_valid_config_with_currency(self):
        raw = {'target_currency_id': str(self.usd.pk),
               'rates': {str(self.eur.pk): '1.23456789'}}
        form = PackingSafeForm(
            instance=Packing(),
            data={
                'currency': str(self.usd.pk),
                'currency_exchange_rates': json.dumps(raw),
            },
            allowed_fields=['currency', 'currency_exchange_rates'],
        )
        self.assertTrue(form.is_valid(), str(form.errors))
        self.assertEqual(form.cleaned_data['currency_exchange_rates'], raw)

    def test_form_rejects_rate_for_wrong_destination(self):
        raw = {'target_currency_id': str(self.eur.pk),
               'rates': {str(self.usd.pk): '1.10'}}
        form = PackingSafeForm(
            instance=Packing(),
            data={
                'currency': str(self.usd.pk),
                'currency_exchange_rates': json.dumps(raw),
            },
            allowed_fields=['currency', 'currency_exchange_rates'],
        )
        self.assertFalse(form.is_valid())
        self.assertIn('currency_exchange_rates', form.errors)


class PackingExchangePageContractTests(SimpleTestCase):
    def test_header_editor_and_summary_reuse_same_quick_packing_page(self):
        path = Path(settings.BASE_DIR) / 'order/templates/order/packing/quick_packing_create.html'
        html = path.read_text(encoding='utf-8')
        self.assertIn('{{ form.currency_exchange_rates }}', html)
        self.assertIn('id="pk-currency-fx"', html)
        self.assertIn('pk-fx-rate-rows', html)
        self.assertIn('fx_can_edit', html)
        self.assertIn('packing-total-value', html)
        self.assertIn('packing-currency-breakdown', html)
        self.assertIn('packing-fx-converted-total', html)
        self.assertIn('fxTarget()', html)
        self.assertIn('fxSourceTotals()', html)
        self.assertIn('fxUpdateConvertedTotal(totals)', html)
        self.assertIn("if (target !== fxActiveTarget)", html)
        self.assertIn('data-currency-pk=', html)
        self.assertNotIn('name="converted_total"', html)
        self.assertIn("if (!canViewPrices || !fxRoot) return;", html)

    def test_datatable_exposes_currency_id_without_fk_join(self):
        view = QuickPackingDataTableListView()
        queryset = view.get_initial_queryset().only('id', 'created_date', 'order_number')
        # SQL must compile even when ajax_datatable defers the Order.currency FK.
        sql = str(queryset.query)
        self.assertIn('currency_id', sql)
        self.assertIn('effective_currency_pk', queryset.query.annotations)
        self.assertFalse(queryset.query.select_related)

class PackingUnifiedFXLayoutTests(SimpleTestCase):
    """Regression checks for a single cohesive FX card in the header."""

    @staticmethod
    def template():
        return (
            Path(settings.BASE_DIR) /
            'order/templates/order/packing/quick_packing_create.html'
        ).read_text(encoding='utf-8')

    def test_target_rates_and_live_result_share_one_header_card(self):
        html = self.template()
        start = html.index('<section id="pk-currency-fx"')
        end = html.index('</section>', start)
        panel = html[start:end]
        self.assertLess(panel.index("render_field_by_order form form.currency"),
                        panel.index('id="pk-fx-rate-rows"'))
        self.assertLess(panel.index('id="pk-fx-rate-rows"'),
                        panel.index('id="packing-fx-header-total"'))
        for control in ('pk-fx-workspace', 'pk-fx-settings', 'pk-fx-preview',
                        'packing-fx-header-status', 'packing-fx-header-breakdown'):
            self.assertIn(control, panel)
        # A second destination selector in the old header grid is confusing.
        self.assertEqual(html.count('render_field_by_order form form.currency'), 1)
        self.assertNotIn('form.packing_number form.currency', html)

    def test_readonly_viewers_see_target_without_edit_access(self):
        html = self.template()
        panel = html[
            html.index('<section id="pk-currency-fx"'):
            html.index('</section>', html.index('<section id="pk-currency-fx"'))
        ]
        self.assertIn('{% if form.currency %}', panel)
        self.assertIn('{{ packing_object.currency|default:"—" }}', panel)
        self.assertIn('{% if fx_can_edit %}', panel)
        self.assertIn('{{ form.currency_exchange_rates }}', panel)
        self.assertIn('{% if can_view_prices %}', html[:html.index('<section id="pk-currency-fx"')])

    def test_single_calculation_updates_both_header_and_footer(self):
        html = self.template()
        for key in ('packing-fx-header-total', 'packing-fx-converted-total',
                    'packing-fx-header-status', 'packing-fx-status',
                    'packing-fx-header-breakdown', 'packing-currency-breakdown'):
            self.assertIn("document.getElementById('" + key + "')", html)
        self.assertIn("setPreview('—', notices.join(' '), true)", html)
        self.assertIn('fxMoney(source.amount)', html)
        self.assertIn('fxUpdateConvertedTotal(totals)', html)
        self.assertNotIn('name="converted_total"', html)

    def test_responsive_fa_en_workspace(self):
        html = self.template()
        self.assertIn('grid-template-columns:minmax(0,1.55fr)', html)
        self.assertIn('@media(max-width:1050px)', html)
        self.assertIn('@media(max-width:700px)', html)
        for key in ('packing_fx_unified_help', 'packing_fx_rates_title',
                    'packing_fx_preview_title', 'packing_fx_live'):
            self.assertGreaterEqual(html.count(key + ':'), 2)

    def test_financial_summary_collapses_with_visible_live_information(self):
        html = self.template()
        start = html.index('<section id="pk-currency-fx"')
        end = html.index('</section>', start)
        section = html[start:end]
        self.assertIn('<details class="pk-fx-fold" id="pk-fx-fold"', section)
        self.assertIn('<summary class="pk-fx-collapse-head">', section)
        self.assertIn('{% if not packing_object %}open{% endif %}', section)
        self.assertIn('id="packing-fx-collapsed-target"', section)
        self.assertIn('id="packing-fx-collapsed-total"', section)
        self.assertIn('id="packing-fx-collapsed-status"', section)
        self.assertIn('id="packing-fx-collapsed-breakdown"', section)
        self.assertIn('id="pk-fx-rate-rows"', section)
        self.assertIn('form form.currency label=\'on-border\'', section)
        self.assertIn('pk-fx-show-label', section)
        self.assertIn('pk-fx-hide-label', section)
        self.assertIn('pk-fx-fold[open]', html)

    def test_collapsed_summary_uses_same_fx_data_as_expanded_and_footer(self):
        html = self.template()
        for marker in ('packing-fx-collapsed-total',
                       'packing-fx-header-total', 'packing-fx-converted-total',
                       'packing-fx-collapsed-status',
                       'packing-fx-header-status', 'packing-fx-status',
                       'packing-fx-collapsed-breakdown',
                       'packing-fx-header-breakdown', 'packing-currency-breakdown'):
            self.assertIn("document.getElementById('" + marker + "')", html)
        self.assertIn('compactTarget.textContent = target', html)
        self.assertIn("setPreview('—', notices.join(' '), true)", html)
        self.assertIn('fxSyncHidden();', html)
        self.assertNotIn('name="converted_total"', html)

    def test_details_labels_translated_for_fa_and_en(self):
        html = self.template()
        self.assertGreaterEqual(html.count('packing_fx_show_details:'), 2)
        self.assertGreaterEqual(html.count('packing_fx_hide_details:'), 2)
        self.assertIn('نمایش جزئیات', html)
        self.assertIn('بستن جزئیات', html)
        self.assertIn('Show details', html)
        self.assertIn('Hide details', html)
