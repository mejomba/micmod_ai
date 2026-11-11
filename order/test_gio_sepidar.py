"""Regression tests for safe per-vendor/currency GIO Sepidar integration."""
from collections import OrderedDict
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase, override_settings

from order.gio_sepidar import (
    GIOSepidarError, gio_is_locked, parse_gio_response, send_gio_groups,
    snapshot_for_group, user_can_send_gio,
)
from order.models import GIO, GIOSepidarGroup
from sepidar.api_call import SepidarApiCall


def good_response(key, base=100):
    return {key: {'gio': {'sepidar': [{
        'purchase_invoice': {'id': base + 1, 'number': base + 11},
        'before_central_wh_receipt': {'id': base + 2, 'number': base + 12},
        'voucher': {'id': base + 3, 'number': base + 13},
    }]}}}


class GIOResponseTests(SimpleTestCase):
    def test_three_complete_documents_are_required(self):
        status, ids, error = parse_gio_response(good_response('123___5'), '123___5')
        self.assertEqual(status, 'success')
        self.assertEqual(ids['invoice_id'], 101)
        self.assertEqual(ids['receipt_id'], 102)
        self.assertEqual(ids['voucher_id'], 103)
        self.assertEqual(error, '')
        for response in (
            {'123___5': {'gio': {'sepidar': []}}},
            {'wrong___5': good_response('wrong___5')['wrong___5']},
            {'123___5': {'gio': {'sepidar': [{
                'purchase_invoice': {'id': 1, 'number': 2},
            }]}}},
            {'123___5': {'gio': {'sepidar': [{
                'purchase_invoice': {'id': 0, 'number': 2},
                'before_central_wh_receipt': {'id': 2, 'number': 2},
                'voucher': {'id': 3, 'number': 3},
            }]}}},
        ):
            with self.subTest(response=response):
                self.assertEqual(parse_gio_response(response, '123___5')[0], 'unknown')

    def test_error_is_failed_but_uncertain_error_is_blocked(self):
        self.assertEqual(parse_gio_response({'errors': 'validation'}, '1___1')[0], 'failed')
        self.assertEqual(parse_gio_response(
            {'errors': 'HTTP 500', 'uncertain': True}, '1___1',
        )[0], 'unknown')
        self.assertEqual(parse_gio_response(None, '1___1')[0], 'unknown')

    def test_selected_group_success_is_not_masked_by_unrelated_unknown_group(self):
        import json
        from django.test import RequestFactory
        from order.views import OrderAndSepidar
        groups = [
            {'key': '201___1', 'status': 'success'},
            {'key': '202___2', 'status': 'unknown'},
        ]
        request = RequestFactory().post(
            '/order/ajax/order_and_sepidar/?view_name=trade_buy_factor',
            data=json.dumps({'gio_id': 17, 'group_key': '201___1'}),
            content_type='application/json',
        )
        request.user = SimpleNamespace(is_authenticated=True)
        with patch('order.views.user_can_send_gio', return_value=True), patch(
            'order.views.GIO.objects.filter',
        ) as filtered, patch(
            'order.views.send_gio_groups', return_value=groups,
        ):
            filtered.return_value.first.return_value = SimpleNamespace(pk=17)
            response = OrderAndSepidar.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)['group_key'], '201___1')
        self.assertEqual(json.loads(response.content)['res'], 'success')

    def test_selected_group_unknown_is_still_blocked_even_if_others_succeeded(self):
        import json
        from django.test import RequestFactory
        from order.views import OrderAndSepidar
        groups = [
            {'key': '201___1', 'status': 'success'},
            {'key': '202___2', 'status': 'unknown'},
        ]
        request = RequestFactory().post(
            '/order/ajax/order_and_sepidar/?view_name=trade_buy_factor',
            data=json.dumps({'gio_id': 17, 'group_key': '202___2'}),
            content_type='application/json',
        )
        request.user = SimpleNamespace(is_authenticated=True)
        with patch('order.views.user_can_send_gio', return_value=True), patch(
            'order.views.GIO.objects.filter',
        ) as filtered, patch(
            'order.views.send_gio_groups', return_value=groups,
        ):
            filtered.return_value.first.return_value = SimpleNamespace(pk=17)
            response = OrderAndSepidar.as_view()(request)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(json.loads(response.content)['group_key'], '202___2')

    def test_order_document_ledger_is_idempotent(self):
        from order.gio_sepidar import _record_order_documents
        document = SimpleNamespace(
            data={'payment': {'sepidar': [{'id': 9}]}}, save=Mock(),
        )
        group = SimpleNamespace(
            invoice_id=101, invoice_number='11',
            receipt_id=102, receipt_number='12',
            voucher_id=103, voucher_number='13',
        )
        rows = [SimpleNamespace(order_id=7), SimpleNamespace(order_id=7)]
        with patch('order.gio_sepidar.SepidarOrderDocument.objects.select_for_update') as selected:
            selected.return_value.get_or_create.return_value = (document, False)
            _record_order_documents(group, rows)
            _record_order_documents(group, rows)
        self.assertEqual(len(document.data['gio']['sepidar']), 1)
        self.assertEqual(document.data['gio']['sepidar'][0]['voucher']['id'], 103)
        self.assertEqual(document.data['payment'], {'sepidar': [{'id': 9}]})
        self.assertEqual(document.save.call_count, 2)

    def test_access_matches_template_mac_exclusion(self):
        user = SimpleNamespace(
            is_authenticated=True, is_superuser=False,
            groups=SimpleNamespace(filter=lambda **k: SimpleNamespace(exists=lambda: False)),
        )
        self.assertTrue(user_can_send_gio(user))
        user.is_superuser = True
        self.assertFalse(user_can_send_gio(user))
        user.is_superuser = False
        user.groups = SimpleNamespace(filter=lambda **k: SimpleNamespace(exists=lambda: True))
        self.assertFalse(user_can_send_gio(user))
        user.is_authenticated = False
        self.assertFalse(user_can_send_gio(user))

    @override_settings(SEPIDAR_CUSTOM_API_VERSION='v2')
    def test_api_posts_one_invoice_and_classifies_http_5xx_as_uncertain(self):
        response = SimpleNamespace(ok=False, status_code=503, text='gateway timeout')
        with patch.object(SepidarApiCall, 'setup'), patch.object(
            SepidarApiCall, 'endpoints', {'v2': {'gio': 'http://fake/gio'}},
        ), patch.object(SepidarApiCall, 'headers', {'Authorization': 'test'}, create=True), patch(
            'sepidar.api_call.requests.post', return_value=response,
        ) as post:
            result = SepidarApiCall.gio_to_sepidar(buy_factor_list=[{'example': 1}])
        self.assertEqual(result['uncertain'], True)
        self.assertEqual(post.call_args.kwargs['timeout'], (10, 90))
        self.assertEqual(post.call_args.kwargs['json'], {'buy_factor_list': [{'example': 1}]})


class GIOSepidarSendTests(TestCase):
    def setUp(self):
        self.gio = GIO.objects.create(gio_date=date(2026, 11, 10))
        self.request = SimpleNamespace(user=SimpleNamespace(sepidar_code=1))
        def row(pk, order_id):
            return SimpleNamespace(
                pk=pk, order_id=order_id, quantity=3,
                order=SimpleNamespace(
                    item=SimpleNamespace(sepidar_id_0=pk + 100),
                    final_price=20, final_discount=0, final_addition=0,
                ),
            )
        self.rows = OrderedDict([
            ('201___1', [row(1, 11)]),
            ('202___2', [row(2, 12)]),
        ])

    def _send(self, responses, *, group_key=None):
        def payload(key, rows, request):
            return {'vendordlref': key, 'inventorypurchaseinvoice_item': [{'itemref': 1}]}

        def api(*args, **kwargs):
            key = kwargs['buy_factor_list'][0]['vendordlref']
            return responses[key]

        with patch('order.gio_sepidar.plan_gio_groups', return_value=self.rows), patch(
            'order.gio_sepidar.SepidarDataFactory.get_trade_inventory_purchase_invoice_data',
            side_effect=payload,
        ), patch('order.gio_sepidar.SepidarApiCall.gio_to_sepidar', side_effect=api) as call, patch(
            'order.gio_sepidar._record_order_documents',
        ):
            states = send_gio_groups(self.gio, self.request, group_key=group_key)
            return states, call.call_count

    def test_success_writes_three_ids_per_group_and_blocks_duplicate_sends(self):
        states, calls = self._send({
            '201___1': good_response('201___1', 100),
            '202___2': good_response('202___2', 200),
        })
        self.assertEqual(calls, 2)
        self.assertTrue(all(x['status'] == 'success' for x in states))
        self.gio.refresh_from_db()
        self.assertEqual(self.gio.sepidar_buy_factor_response_json['purchase_invoice'], [101, 201])
        self.assertTrue(gio_is_locked(self.gio))
        self.assertEqual(GIOSepidarGroup.objects.filter(gio=self.gio).count(), 2)
        self.assertTrue(all(x.attempt_count == 1 for x in GIOSepidarGroup.objects.all()))
        with self.assertRaises(GIOSepidarError):
            self._send({
                '201___1': good_response('201___1'), '202___2': good_response('202___2'),
            })

    def test_retries_only_definitively_rejected_group(self):
        first, count = self._send({
            '201___1': good_response('201___1'),
            '202___2': {'errors': 'Validation error'},
        })
        self.assertEqual(count, 2)
        self.assertEqual({x['status'] for x in first}, {'success', 'failed'})
        self.gio.refresh_from_db()
        self.assertIsNone(self.gio.sepidar_buy_factor_response_json)
        self.assertTrue(gio_is_locked(self.gio))
        second, count = self._send({
            '201___1': good_response('201___1'),
            '202___2': good_response('202___2', 200),
        })
        self.assertEqual(count, 1)
        self.assertTrue(all(x['status'] == 'success' for x in second))
        self.assertEqual(
            list(GIOSepidarGroup.objects.order_by('group_key').values_list('attempt_count', flat=True)),
            [1, 2],
        )

    def test_single_group_retry_does_not_touch_other_pending_groups(self):
        states, count = self._send({
            '201___1': good_response('201___1'),
        }, group_key='201___1')
        self.assertEqual(count, 1)
        self.assertEqual([x['key'] for x in states], ['201___1'])
        self.assertFalse(GIOSepidarGroup.objects.filter(gio=self.gio, group_key='202___2').exists())
        with self.assertRaises(GIOSepidarError):
            self._send({
                '201___1': good_response('201___1'),
            }, group_key='201___1')
        states, count = self._send({
            '202___2': good_response('202___2', 200),
        }, group_key='202___2')
        self.assertEqual(count, 1)
        self.assertTrue(all(x['status'] == 'success' for x in states))

    def test_unknown_group_stays_blocked_and_can_not_be_sent_again(self):
        initial, count = self._send({
            '201___1': good_response('201___1'),
            '202___2': {'errors': 'HTTP 500', 'uncertain': True},
        })
        self.assertEqual(count, 2)
        self.assertEqual([s['status'] for s in initial], ['success', 'unknown'])
        second, count = self._send({
            '201___1': good_response('201___1'),
            '202___2': good_response('202___2'),
        })
        self.assertEqual(count, 0)
        self.assertEqual(second, initial)
        self.assertEqual(
            GIOSepidarGroup.objects.get(gio=self.gio, group_key='202___2').attempt_count, 1,
        )

    def test_transport_exception_becomes_unknown(self):
        from requests.exceptions import Timeout
        def payload(key, rows, request):
            return {'vendordlref': key, 'inventorypurchaseinvoice_item': [{'itemref': 1}]}
        with patch('order.gio_sepidar.plan_gio_groups', return_value=self.rows), patch(
            'order.gio_sepidar.SepidarDataFactory.get_trade_inventory_purchase_invoice_data',
            side_effect=payload,
        ), patch('order.gio_sepidar.SepidarApiCall.gio_to_sepidar', side_effect=Timeout('timeout')):
            states = send_gio_groups(self.gio, self.request, group_key='201___1')
        self.assertEqual(states[0]['status'], 'unknown')
        self.assertEqual(GIOSepidarGroup.objects.get(gio=self.gio).attempt_count, 1)

    def test_malformed_response_is_unknown_not_failed(self):
        states, calls = self._send({
            '201___1': good_response('201___1'),
            '202___2': {'202___2': {'gio': {'sepidar': []}}},
        })
        self.assertEqual(calls, 2)
        self.assertEqual(states[1]['status'], 'unknown')

    def test_snapshot_detects_mutated_group(self):
        self._send({
            '201___1': good_response('201___1'),
            '202___2': {'errors': 'validation'},
        })
        self.rows['201___1'][0].quantity = 99
        with self.assertRaises(GIOSepidarError):
            self._send({
                '201___1': good_response('201___1'),
                '202___2': good_response('202___2'),
            })

    def test_delete_confirmation_for_unsent_gio_and_locked_gio(self):
        """GIO confirm must use globally imported apps, not a packing-only local."""
        from django.test import RequestFactory
        from core.views import delete_confirm
        factory = RequestFactory()
        request = factory.get('/core/delete/confirm/', {
            'app_label': 'order',
            'model': 'gio',
            'object_id': str(self.gio.pk),
        })
        request.user = SimpleNamespace(is_authenticated=True)
        response = delete_confirm(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'delete-confirm', response.content)
        GIOSepidarGroup.objects.create(
            gio=self.gio, group_key='201___1', status='unknown',
        )
        locked_response = delete_confirm(request)
        self.assertEqual(locked_response.status_code, 409)

    def test_delete_confirmation_for_unsent_gio_item(self):
        """Exercise the same confirmation path reached by Quick GIO row delete."""
        from django.test import RequestFactory
        from core.views import delete_confirm
        from order.models import GIOItem
        row = GIOItem.objects.create(gio=self.gio, quantity=1)
        request = RequestFactory().get('/core/delete/confirm/', {
            'app_label': 'order',
            'model': 'gioitem',
            'object_id': str(row.pk),
        })
        request.user = SimpleNamespace(is_authenticated=True)
        response = delete_confirm(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'delete-confirm', response.content)
        GIOSepidarGroup.objects.create(
            gio=self.gio, group_key='201___1', status='unknown',
        )
        self.assertEqual(delete_confirm(request).status_code, 409)

    def test_server_rejects_edit_and_delete_during_unknown_status(self):
        import json
        from django.test import RequestFactory
        from order.views import QuickGIOView
        from core.views import delete_ajax
        GIOSepidarGroup.objects.create(
            gio=self.gio, group_key='201___1', status='unknown',
        )
        factory = RequestFactory()
        request = factory.post(
            '/order/quick_gio/%s/' % self.gio.pk,
            data=json.dumps({'gio_id': self.gio.pk, 'form-TOTAL_FORMS': 1}),
            content_type='application/json',
        )
        request.user = SimpleNamespace(is_authenticated=True)
        edit_response = QuickGIOView.as_view()(request, pk=self.gio.pk)
        self.assertEqual(edit_response.status_code, 409)
        delete_request = factory.post(
            '/core/delete/',
            data=json.dumps({'app_label': 'order', 'model': 'gio', 'object_id': self.gio.pk}),
            content_type='application/json',
        )
        delete_request.user = SimpleNamespace(is_authenticated=True)
        delete_response = delete_ajax(delete_request)
        self.assertEqual(delete_response.status_code, 409)
        self.gio.refresh_from_db()
        self.assertFalse(self.gio.is_deleted)

    def test_legacy_response_is_always_locked(self):
        GIO.objects.filter(pk=self.gio.pk).update(
            sepidar_buy_factor_response_json={'purchase_invoice': [101]},
        )
        self.gio.refresh_from_db()
        self.assertTrue(gio_is_locked(self.gio))
        with self.assertRaises(GIOSepidarError):
            self._send({
                '201___1': good_response('201___1'),
                '202___2': good_response('202___2'),
            })
