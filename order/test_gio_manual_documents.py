"""Superuser-only manual entry of three already existing Sepidar documents."""
import json
from collections import OrderedDict
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase

from order.gio_sepidar import (
    GIOSepidarError, gio_is_locked, gio_preview_groups,
    manual_save_gio_sepidar_documents, snapshot_for_group,
)
from order.models import GIO, GIOSepidarGroup, GIOSepidarManualDocumentEntry
from order.views import OrderAndSepidar


class ManualSepidarDocumentTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            username='gio_docs_admin', is_superuser=True,
            is_staff=True, password='not-used',
        )
        self.other_user = User.objects.create_user(
            username='gio_docs_other', password='not-used',
        )
        self.gio = GIO.objects.create(gio_date=date(2026, 11, 11))
        self.key1 = '201___1'
        self.key2 = '202___2'

        def row(pk, supplier, currency):
            return SimpleNamespace(
                pk=pk, order_id=pk + 500, quantity=3, description='test',
                order=SimpleNamespace(
                    pk=pk + 500, order_number='ORD-' + str(pk),
                    item=SimpleNamespace(sepidar_id_0=pk + 900),
                    final_item=SimpleNamespace(part_number='PN-' + str(pk), sku='SKU-' + str(pk)),
                    final_supplier=SimpleNamespace(dlref=supplier),
                    currency=SimpleNamespace(title_en='Dollar', title='USD', sepidar_id=currency),
                    final_price=20, final_discount=0, final_addition=0,
                ),
            )
        self.rows = OrderedDict([
            (self.key1, [row(11, 201, 1)]),
            (self.key2, [row(12, 202, 2)]),
        ])
        self.plan = patch('order.gio_sepidar.plan_gio_groups', return_value=self.rows)
        self.plan.start()
        self.addCleanup(self.plan.stop)

    def docs(self, base=1000):
        return {
            'invoice': {'id': str(base + 1), 'number': 'INV-' + str(base + 11)},
            'receipt': {'id': str(base + 2), 'number': 'REC-' + str(base + 12)},
            'voucher': {'id': str(base + 3), 'number': 'ACC-' + str(base + 13)},
        }

    def save(self, group_key=None, **kwargs):
        values = {
            'group_key': group_key or self.key1,
            'confirmed_group': group_key or self.key1,
            'reason': 'هر سه سند در سپیدار با تأمین‌کننده و ارز این گروه مطابقت دارند.',
            'documents': self.docs(),
            'verified': True,
            'overwrite_confirmed': False,
        }
        values.update(kwargs)
        return manual_save_gio_sepidar_documents(self.gio, self.admin, **values)

    def test_manual_saves_one_group_without_creating_any_remote_documents(self):
        with patch('order.gio_sepidar._record_order_documents') as ledger, patch(
            'order.gio_sepidar.SepidarApiCall.gio_to_sepidar',
        ) as api:
            record = self.save()
        api.assert_not_called()
        ledger.assert_called_once()
        record.refresh_from_db()
        self.assertEqual(record.status, 'success')
        self.assertEqual(record.invoice_id, 1001)
        self.assertEqual(record.invoice_number, 'INV-1011')
        self.assertEqual(record.receipt_id, 1002)
        self.assertEqual(record.voucher_number, 'ACC-1013')
        self.assertEqual(record.attempt_count, 0)
        self.assertIsNone(record.sent_at)
        self.assertTrue(gio_is_locked(self.gio))
        self.assertEqual(GIOSepidarGroup.objects.count(), 1)
        self.assertFalse(GIOSepidarGroup.objects.filter(group_key=self.key2).exists())
        self.gio.refresh_from_db()
        self.assertIsNone(self.gio.sepidar_buy_factor_response_json)
        event = GIOSepidarManualDocumentEntry.objects.get(group=record)
        self.assertEqual(event.actor_id, self.admin.pk)
        self.assertEqual(event.previous_documents, {})
        self.assertEqual(event.previous_status, '')
        self.assertEqual(event.new_documents['voucher']['id'], 1003)

    def test_all_groups_succeed_then_legacy_summary_has_three_lists(self):
        with patch('order.gio_sepidar._record_order_documents'):
            self.save()
            self.save(self.key2, documents=self.docs(2000))
        self.gio.refresh_from_db()
        self.assertEqual(
            self.gio.sepidar_buy_factor_response_json,
            {'purchase_invoice': [1001, 2001],
             'before_central_wh_receipt': [1002, 2002],
             'voucher': [1003, 2003]},
        )
        self.assertEqual(
            list(GIOSepidarGroup.objects.order_by('group_key').values_list('status', flat=True)),
            ['success', 'success'],
        )

    def test_unknown_existing_group_can_be_reconciled_and_previous_api_evidence_kept(self):
        previous = GIOSepidarGroup.objects.create(
            gio=self.gio, group_key=self.key1, status='unknown',
            items_snapshot=snapshot_for_group(self.rows[self.key1]),
            response_payload={'uncertain': True, 'errors': 'timeout'},
            last_error='timeout', attempt_count=1,
        )
        with patch('order.gio_sepidar._record_order_documents'):
            record = self.save()
        record.refresh_from_db()
        self.assertEqual(record.pk, previous.pk)
        self.assertEqual(record.status, 'success')
        self.assertEqual(record.last_error, '')
        self.assertEqual(record.attempt_count, 1)
        self.assertEqual(record.response_payload['errors'], 'timeout')
        event = GIOSepidarManualDocumentEntry.objects.get(group=record)
        self.assertEqual(event.previous_status, 'unknown')

    def test_admin_can_correct_existing_success_with_extra_confirmation_and_audit(self):
        with patch('order.gio_sepidar._record_order_documents') as ledger:
            record = self.save()
            with self.assertRaises(GIOSepidarError):
                self.save(documents=self.docs(1100))
            changed = self.save(documents=self.docs(1100), overwrite_confirmed=True)
        changed.refresh_from_db()
        self.assertEqual(changed.pk, record.pk)
        self.assertEqual(changed.invoice_id, 1101)
        self.assertEqual(changed.receipt_id, 1102)
        self.assertEqual(changed.voucher_id, 1103)
        self.assertEqual(ledger.call_count, 2)
        self.assertEqual(ledger.call_args.kwargs['previous_invoice_id'], 1001)
        events = list(GIOSepidarManualDocumentEntry.objects.filter(group=record))
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].previous_status, 'success')
        self.assertEqual(events[0].previous_documents['invoice']['id'], 1001)
        self.assertEqual(events[0].new_documents['invoice']['id'], 1101)

    def test_replacing_previous_invoice_updates_existing_order_ledger_in_place(self):
        from unittest.mock import Mock
        from order.gio_sepidar import _record_order_documents

        order_entry = SimpleNamespace(
            data={'gio': {'sepidar': [{
                'purchase_invoice': {'id': 1001, 'number': 'INV-1011'},
                'before_central_wh_receipt': {'id': 1002, 'number': 'REC-1012'},
                'voucher': {'id': 1003, 'number': 'ACC-1013'},
            }]}},
            save=Mock(),
        )
        corrected = SimpleNamespace(
            invoice_id=1101, invoice_number='INV-1111',
            receipt_id=1102, receipt_number='REC-1112',
            voucher_id=1103, voucher_number='ACC-1113',
        )
        with patch('order.gio_sepidar.SepidarOrderDocument.objects.select_for_update') as locked:
            locked.return_value.get_or_create.return_value = (order_entry, False)
            _record_order_documents(
                corrected, [self.rows[self.key1][0]], previous_invoice_id=1001,
            )
        recorded = order_entry.data['gio']['sepidar']
        self.assertEqual(len(recorded), 1)
        self.assertEqual(recorded[0]['purchase_invoice']['id'], 1101)
        self.assertEqual(recorded[0]['voucher']['id'], 1103)
        order_entry.save.assert_called_once_with(update_fields=['data'])

    def test_correction_updates_completed_summary(self):
        with patch('order.gio_sepidar._record_order_documents'):
            self.save()
            self.save(self.key2, documents=self.docs(2000))
            self.save(documents=self.docs(5000), overwrite_confirmed=True)
        self.gio.refresh_from_db()
        self.assertEqual(
            self.gio.sepidar_buy_factor_response_json['purchase_invoice'],
            [5001, 2001],
        )
        self.assertEqual(
            self.gio.sepidar_buy_factor_response_json['voucher'],
            [5003, 2003],
        )

    def test_user_without_superuser_permission_is_rejected_server_side(self):
        with self.assertRaises(PermissionError):
            manual_save_gio_sepidar_documents(
                self.gio, self.other_user,
                group_key=self.key1, confirmed_group=self.key1,
                reason='هر سه سند در سپیدار واقعاً بررسی شده و تطبیق داده شدند.',
                documents=self.docs(), verified=True,
            )
        self.assertFalse(GIOSepidarGroup.objects.exists())

    def test_missing_or_malformed_document_identifier_is_rejected(self):
        bad_cases = [
            {'invoice': {'id': '', 'number': 'INV'}, 'receipt': self.docs()['receipt'],
             'voucher': self.docs()['voucher']},
            {**self.docs(), 'voucher': {'id': '1.5', 'number': 'V'}},
            {**self.docs(), 'voucher': {'id': '-5', 'number': 'V'}},
            {**self.docs(), 'voucher': {'id': True, 'number': 'V'}},
            {**self.docs(), 'voucher': {'id': '9999999999999999999', 'number': 'V'}},
            {**self.docs(), 'voucher': {'id': '42', 'number': ''}},
            {**self.docs(), 'voucher': {'id': '42', 'number': 'A\nB'}},
            {**self.docs(), 'voucher': {'id': '42', 'number': 'A' * 65}},
            {'invoice': self.docs()['invoice'], 'receipt': self.docs()['receipt']},
        ]
        for documents in bad_cases:
            with self.subTest(documents=documents), self.assertRaises(GIOSepidarError):
                self.save(documents=documents)
        self.assertFalse(GIOSepidarGroup.objects.exists())

    def test_explicit_confirmation_reason_and_exact_group_key_required(self):
        bad = [
            {'verified': False}, {'verified': 'true'},
            {'reason': 'ثبت شد'}, {'reason': 'a' * 2001},
            {'confirmed_group': '202___2'},
            {'group_key': 'NOT-A-GROUP', 'confirmed_group': 'NOT-A-GROUP'},
        ]
        for values in bad:
            with self.subTest(values=values), self.assertRaises(GIOSepidarError):
                self.save(**values)
        self.assertFalse(GIOSepidarManualDocumentEntry.objects.exists())

    def test_edit_during_in_flight_remote_send_is_blocked(self):
        GIOSepidarGroup.objects.create(
            gio=self.gio, group_key=self.key1, status='sending',
            items_snapshot=snapshot_for_group(self.rows[self.key1]),
        )
        with self.assertRaises(GIOSepidarError):
            self.save()
        self.assertFalse(GIOSepidarManualDocumentEntry.objects.exists())

    def test_changed_rows_cannot_be_attributed_to_previous_undetermined_send(self):
        GIOSepidarGroup.objects.create(
            gio=self.gio, group_key=self.key1, status='unknown',
            items_snapshot=snapshot_for_group(self.rows[self.key1]),
        )
        self.rows[self.key1][0].quantity = 99
        with self.assertRaises(GIOSepidarError):
            self.save()
        self.assertFalse(GIOSepidarManualDocumentEntry.objects.exists())

    def test_duplicate_remote_identifier_in_different_gio_is_blocked(self):
        other_gio = GIO.objects.create(gio_date=date(2026, 11, 11))
        GIOSepidarGroup.objects.create(
            gio=other_gio, group_key='999___1', status='success',
            invoice_id=1001, invoice_number='INV-1',
        )
        with self.assertRaises(GIOSepidarError):
            self.save()
        self.assertFalse(GIOSepidarManualDocumentEntry.objects.exists())

    def test_db_rollback_including_audit_when_ledger_update_fails(self):
        with patch('order.gio_sepidar._record_order_documents',
                   side_effect=RuntimeError('local database error')):
            with self.assertRaises(RuntimeError):
                self.save()
        self.assertFalse(GIOSepidarGroup.objects.filter(gio=self.gio).exists())
        self.assertFalse(GIOSepidarManualDocumentEntry.objects.exists())

    def test_legacy_ungrouped_response_is_not_overwritten(self):
        GIO.objects.filter(pk=self.gio.pk).update(
            sepidar_buy_factor_response_json={'purchase_invoice': [11]},
        )
        with self.assertRaises(GIOSepidarError):
            self.save()
        self.assertFalse(GIOSepidarGroup.objects.exists())

    def test_endpoint_superuser_only_and_does_not_send_to_remote_api(self):
        url = '/order/ajax/order_and_sepidar/?view_name=trade_buy_factor_manual_save'
        body = {
            'gio_id': self.gio.pk, 'group_key': self.key1,
            'confirmed_group': self.key1,
            'reason': 'سه سند در سپیدار با تأمین‌کننده و ارز دقیقاً تطبیق داده شدند.',
            'verified': True, 'documents': self.docs(),
        }
        request = RequestFactory().post(
            url, data=json.dumps(body), content_type='application/json',
        )
        request.user = self.other_user
        denied = OrderAndSepidar.as_view()(request)
        self.assertEqual(denied.status_code, 403)
        request.user = self.admin
        with patch('order.gio_sepidar._record_order_documents'), patch(
            'order.gio_sepidar.SepidarApiCall.gio_to_sepidar',
        ) as remote:
            ok = OrderAndSepidar.as_view()(request)
        remote.assert_not_called()
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(json.loads(ok.content)['status'], 'success')
        self.assertEqual(json.loads(ok.content)['group_key'], self.key1)

    def test_get_method_not_allowed_for_manual_save(self):
        request = RequestFactory().get(
            '/order/ajax/order_and_sepidar/?view_name=trade_buy_factor_manual_save',
        )
        request.user = self.admin
        self.assertEqual(OrderAndSepidar.as_view()(request).status_code, 405)

    def test_group_html_shows_button_only_to_superuser_and_never_during_send(self):
        gio = SimpleNamespace(
            sepidar_buy_factor_response_json=None,
            sepidar_inventory_receipt_response_json=None,
            sepidar_groups=SimpleNamespace(all=lambda: []),
        )
        with patch('order.gio_sepidar.plan_gio_groups', return_value=self.rows):
            group = gio_preview_groups(gio)[0]
        shared = {'groups': [group], 'gio_sepidar_can_send': False}
        shown = render_to_string(
            'order/partial/sepidar/trade_buy_factor_preview.html',
            {**shared, 'gio_can_manual_save_sepidar': True},
        )
        hidden = render_to_string(
            'order/partial/sepidar/trade_buy_factor_preview.html',
            {**shared, 'gio_can_manual_save_sepidar': False},
        )
        self.assertIn('gio-manual-sepidar-open', shown)
        self.assertNotIn('gio-manual-sepidar-open', hidden)
        group['status'] = 'sending'
        sending = render_to_string(
            'order/partial/sepidar/trade_buy_factor_preview.html',
            {**shared, 'gio_can_manual_save_sepidar': True},
        )
        self.assertNotIn('gio-manual-sepidar-open', sending)

    def test_modal_requires_three_ids_verified_reason_and_double_confirmation(self):
        from django.template.loader import get_template
        source = get_template('order/gio/quick_gio_update.html').template.source
        for name in ('gio-manual-invoice-id', 'gio-manual-invoice-number',
                     'gio-manual-receipt-id', 'gio-manual-receipt-number',
                     'gio-manual-voucher-id', 'gio-manual-voucher-number',
                     'gio-manual-verified', 'gio-manual-overwrite',
                     'gio-manual-confirm-key', 'gio-manual-reason',
                     'trade_buy_factor_manual_save', 'gio_manual_saved'):
            self.assertIn(name, source)
        self.assertIn('{% if gio_can_manual_save_sepidar %}', source)
        self.assertIn('manualSave.disabled', source)
        self.assertIn('manualIsCorrection', source)
