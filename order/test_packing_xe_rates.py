"""Mock-based XE integration tests (no network access or real credentials)."""
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase, TestCase, override_settings

from micmod_base.base import Currency
from order.models import Packing
from order.views import QuickPackingView
from order.xe_currency_rates import (
    XeRateError, _get_xe_quotes, _valid_inverse, xe_configured, xe_iso_code,
)


@override_settings(
    XE_CURRENCY_API_KEY='unit-test-xe-token',
    XE_CURRENCY_USERNAME='', XE_CURRENCY_PASSWORD='',
    XE_RATES_CACHE_SECONDS=300,
)
class XeClientTests(SimpleTestCase):
    def test_iso_alias_and_custom_currency_fallback(self):
        self.assertEqual(xe_iso_code(' rmb '), 'CNY')
        self.assertEqual(xe_iso_code('usd'), 'USD')
        self.assertIsNone(xe_iso_code('تومان'))
        self.assertIsNone(xe_iso_code('TOMAN'))

    def test_inverse_is_source_to_destination_and_capped_at_8_decimals(self):
        self.assertEqual(_valid_inverse(Decimal('0.8')), '1.25')
        self.assertEqual(_valid_inverse(Decimal('2')), '0.5')
        for wrong in (None, 0, -1, 'NaN', 'Infinity', 'not-a-rate'):
            self.assertIsNone(_valid_inverse(wrong))

    @patch('order.xe_currency_rates.cache')
    @patch('order.xe_currency_rates.requests.get')
    def test_authenticated_xe_request_batches_sources_and_inverts_mid_quotes(self, http, cache):
        cache.get.return_value = None
        http.return_value.status_code = 200
        http.return_value.json.return_value = {
            'from': 'USD', 'amount': 1.0,
            'timestamp': '2026-11-09T08:00:00Z',
            'to': [
                {'quotecurrency': 'EUR', 'mid': 0.8},
                {'quotecurrency': 'GBP', 'mid': 0.5},
            ],
        }
        result = _get_xe_quotes('USD', ['GBP', 'EUR'])
        self.assertEqual(result['rates'], {'EUR': '1.25', 'GBP': '2'})
        self.assertEqual(result['timestamp'], '2026-11-09T08:00:00Z')
        self.assertFalse(result['cached'])
        args, kwargs = http.call_args
        self.assertEqual(args[0], 'https://xecdapi.xe.com/v1/convert_from.json/')
        self.assertEqual(kwargs['params']['from'], 'USD')
        self.assertEqual(kwargs['params']['to'], 'EUR,GBP')
        self.assertEqual(kwargs['params']['amount'], '1')
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer unit-test-xe-token')
        self.assertEqual(kwargs['timeout'], (3, 8))
        self.assertEqual(cache.set.call_args.kwargs['timeout'], 300)

    @patch('order.xe_currency_rates.cache')
    @patch('order.xe_currency_rates.requests.get')
    def test_cached_quote_does_not_spend_another_xe_request(self, http, cache):
        cache.get.return_value = {
            'rates': {'EUR': '1.25'}, 'timestamp': '2026-11-09T08:00:00Z',
            'cached': False,
        }
        result = _get_xe_quotes('USD', ['EUR'])
        self.assertTrue(result['cached'])
        self.assertEqual(result['rates']['EUR'], '1.25')
        http.assert_not_called()

    @patch('order.xe_currency_rates.cache')
    @patch('order.xe_currency_rates.requests.get')
    def test_network_and_service_failures_keep_manual_entry_possible(self, http, cache):
        cache.get.return_value = None
        http.side_effect = requests.Timeout()
        with self.assertRaises(XeRateError) as caught:
            _get_xe_quotes('USD', ['EUR'])
        self.assertEqual(caught.exception.code, 'connection_failed')
        http.side_effect = None
        for status, code in ((401, 'xe_auth_or_quota'), (403, 'xe_auth_or_quota'),
                             (429, 'xe_rate_limited'), (500, 'xe_unavailable')):
            with self.subTest(status=status):
                http.return_value.status_code = status
                with self.assertRaises(XeRateError) as caught:
                    _get_xe_quotes('USD', ['EUR'])
                self.assertEqual(caught.exception.code, code)

    @override_settings(XE_CURRENCY_API_KEY='', XE_CURRENCY_USERNAME='', XE_CURRENCY_PASSWORD='')
    def test_unconfigured_api_never_attempts_network_call(self):
        self.assertFalse(xe_configured())
        with patch('order.xe_currency_rates.requests.get') as http:
            with self.assertRaises(XeRateError) as caught:
                _get_xe_quotes('USD', ['EUR'])
        self.assertEqual(caught.exception.code, 'not_configured')
        http.assert_not_called()

    @override_settings(XE_CURRENCY_API_KEY='', XE_CURRENCY_USERNAME='user',
                       XE_CURRENCY_PASSWORD='password')
    @patch('order.xe_currency_rates.cache')
    @patch('order.xe_currency_rates.requests.get')
    def test_basic_auth_supported_without_an_api_key(self, http, cache):
        cache.get.return_value = None
        http.return_value.status_code = 200
        http.return_value.json.return_value = {
            'from': 'USD', 'to': [{'quotecurrency': 'EUR', 'mid': 0.8}],
        }
        self.assertEqual(_get_xe_quotes('USD', ['EUR'])['rates']['EUR'], '1.25')
        self.assertEqual(http.call_args.kwargs['auth'], ('user', 'password'))
        self.assertNotIn('Authorization', http.call_args.kwargs['headers'])


@override_settings(XE_CURRENCY_API_KEY='unit-test-xe-token',
                   XE_CURRENCY_USERNAME='', XE_CURRENCY_PASSWORD='')
class XeEndpointTests(TestCase):
    def setUp(self):
        self.usd = Currency.objects.create(title='دلار', title_en='USD')
        self.eur = Currency.objects.create(title='یورو', title_en='EUR')
        self.custom = Currency.objects.create(title='تومان', title_en='TOMAN')
        self.user = Mock(is_superuser=False)
        self.view = QuickPackingView()
        self.view._assert_create_access = Mock()
        self.view._build_form = Mock(return_value=SimpleNamespace(
            fields={'currency': object(), 'currency_exchange_rates': object()},
        ))

    def call(self, price_access=True, target=None, sources=None):
        request = SimpleNamespace(
            user=self.user,
            GET={
                'xe_rates': '1', 'target': str(target or self.usd.pk),
                'sources': sources or str(self.eur.pk),
            },
        )
        self.view.request = request
        with patch.object(Packing, 'user_can_view_prices', return_value=price_access):
            return self.view.get(request)

    @patch('order.views._get_xe_quotes')
    def test_endpoint_maps_currency_ids_and_returns_no_credential(self, service):
        service.return_value = {
            'rates': {'EUR': '1.25'},
            'timestamp': '2026-11-09T08:00:00Z', 'cached': False,
        }
        response = self.call()
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload['rates'], {str(self.eur.pk): '1.25'})
        self.assertEqual(payload['source'], 'XE')
        self.assertEqual(payload['rate_type'], 'mid-market')
        self.assertNotIn('unit-test-xe-token', response.content.decode('utf-8'))
        service.assert_called_once_with('USD', ['EUR'])

    @patch('order.views._get_xe_quotes')
    def test_no_price_access_blocks_provider_without_call(self, service):
        with self.assertRaises(PermissionDenied):
            self.call(price_access=False)
        service.assert_not_called()

    @patch('order.views._get_xe_quotes')
    def test_fields_readonly_block_provider_without_call(self, service):
        self.view._build_form.return_value.fields = {'currency': object()}
        with self.assertRaises(PermissionDenied):
            self.call()
        service.assert_not_called()

    @patch('order.views._get_xe_quotes')
    def test_unsupported_source_is_returned_for_manual_entry(self, service):
        service.return_value = {'rates': {}, 'timestamp': None, 'cached': False}
        resp = self.call(sources=f'{self.eur.pk},{self.custom.pk}')
        payload = json.loads(resp.content)
        self.assertEqual(payload['unsupported'], [str(self.custom.pk)])
        self.assertEqual(payload['missing'], [str(self.eur.pk)])

    @patch('order.views._get_xe_quotes')
    def test_invalid_ids_are_rejected_before_outbound_api(self, service):
        for value in ('0', 'abc', '1,1', '99999999999999999999'):
            with self.subTest(value=value):
                response = self.call(sources=value)
                self.assertEqual(response.status_code, 400)
        service.assert_not_called()


class XeUIContractTests(SimpleTestCase):
    def test_provider_rates_are_suggestions_and_manual_rates_remain_editable(self):
        html = (
            Path(settings.BASE_DIR)
            / 'order/templates/order/packing/quick_packing_create.html'
        ).read_text(encoding='utf-8')
        for token in (
            'data-xe-configured=', 'pk-fx-xe-fetch', 'pk-fx-xe-status',
            'fxXeQuotes', 'fxFetchXeRates', 'fxXeQuotes.get(source.id)',
            'input.addEventListener(\'input\'', 'apply.addEventListener(\'click\'',
            "fxRates[sourceId] = quote", "if (!String(fxRates[sourceId] || '').trim())",
            'fxSyncHidden()', 'fxUpdateConvertedTotal', 'packing_fx_xe_unconfigured',
        ):
            self.assertIn(token, html)
        self.assertNotIn("data-xe-api-key=", html)
        self.assertNotIn('name="converted_total"', html)
