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
