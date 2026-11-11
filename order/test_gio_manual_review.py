"""Safety regressions for superuser-only manual GIO Sepidar retry approval."""
import json
from collections import OrderedDict
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.template.loader import get_template, render_to_string
from django.test import RequestFactory, TestCase

from order.gio_sepidar import (
    GIOSepidarError, approve_unknown_gio_retry, gio_is_locked,
    gio_preview_groups, send_gio_groups, snapshot_for_group,
)
from order.models import GIO, GIOSepidarGroup, GIOSepidarManualReview
from order.views import OrderAndSepidar


class GIOManualReviewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_user(
            username='gio_review_admin', password='not-used', is_superuser=True,
            is_staff=True,
        )
        self.operator = user_model.objects.create_user(
            username='gio_review_operator', password='not-used',
        )
        self.gio = GIO.objects.create(gio_date=date(2026, 11, 11))
        self.key = '501___1'
        self.row = SimpleNamespace(
            pk=41, order_id=301, quantity=3000,
            description='test line',
            order=SimpleNamespace(
                pk=301, order_number='ORD-301',
                item=SimpleNamespace(sepidar_id_0=9021),
                final_item=SimpleNamespace(part_number='TRADE-PN', sku='SKU41'),
                final_supplier=SimpleNamespace(dlref=501),
                currency=SimpleNamespace(title_en='Dollar', title='ارز', sepidar_id=1),
                final_price=12, final_discount=0, final_addition=0,
            ),
        )
        self.record = GIOSepidarGroup.objects.create(
            gio=self.gio, group_key=self.key, status='unknown',
            items_snapshot=snapshot_for_group([self.row]),
            request_payload={'request': 'prior-attempt'},
            response_payload={'errors': 'Gateway timeout', 'uncertain': True},
            last_error='Gateway timeout', attempt_count=1,
        )
        self.plan = patch(
            'order.gio_sepidar.plan_gio_groups',
            return_value=OrderedDict([(self.key, [self.row])]),
        )
        self.plan.start()
        self.addCleanup(self.plan.stop)

    def approve(self, user=None, **overrides):
        fields = {
            'group_key': self.key,
            'confirmed_group': self.key,
            'reason': 'هر سه سند را با تاریخ و تأمین‌کننده در سپیدار بررسی کردم؛ موردی ثبت نشده است.',
            'invoice_checked': True,
            'receipt_checked': True,
            'voucher_checked': True,
        }
        fields.update(overrides)
        return approve_unknown_gio_retry(self.gio, user or self.admin, **fields)

    def test_superuser_review_preserves_uncertain_evidence_and_keeps_gio_locked(self):
        reviewed = self.approve()
        reviewed.refresh_from_db()
        self.assertEqual(reviewed.status, 'reviewed')
        self.assertTrue(gio_is_locked(self.gio))
        log = GIOSepidarManualReview.objects.get(group=reviewed)
        self.assertEqual(log.reviewer_id, self.admin.pk)
        self.assertIn('سپیدار', log.reason)
        self.assertEqual(log.previous_error, 'Gateway timeout')
        self.assertEqual(log.previous_attempt_count, 1)
        self.assertEqual(log.previous_request_payload, {'request': 'prior-attempt'})
        self.assertEqual(log.previous_response_payload['errors'], 'Gateway timeout')
        self.assertTrue(all(log.confirmations.values()))
        self.assertEqual(reviewed.attempt_count, 1)
        self.assertEqual(reviewed.response_payload['errors'], 'Gateway timeout')

    def test_non_superuser_cannot_approve_even_with_correct_confirmations(self):
        with self.assertRaises(PermissionError):
            self.approve(self.operator)
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, 'unknown')
        self.assertFalse(GIOSepidarManualReview.objects.exists())

    def test_all_three_confirmations_exact_key_and_explanation_are_required(self):
        invalid_cases = [
            {'confirmed_group': '501___2'},
            {'invoice_checked': False},
            {'receipt_checked': False},
            {'voucher_checked': False},
            {'voucher_checked': 'true'},
            {'reason': 'بررسی شد'},
            {'reason': 'a' * 2001},
        ]
        for invalid in invalid_cases:
            with self.subTest(invalid=invalid):
                with self.assertRaises(GIOSepidarError):
                    self.approve(**invalid)
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, 'unknown')
        self.assertFalse(GIOSepidarManualReview.objects.exists())

    def test_approval_is_single_use_and_repeated_approval_is_rejected(self):
        self.approve()
        with self.assertRaises(GIOSepidarError):
            self.approve()
        self.assertEqual(GIOSepidarManualReview.objects.filter(group=self.record).count(), 1)

    def test_cannot_approve_if_any_sepidar_id_was_already_recorded(self):
        for field in ('invoice_id', 'receipt_id', 'voucher_id'):
            setattr(self.record, field, 123)
            self.record.save(update_fields=[field])
            with self.subTest(field=field), self.assertRaises(GIOSepidarError):
                self.approve()
            setattr(self.record, field, None)
            self.record.save(update_fields=[field])
        self.assertFalse(GIOSepidarManualReview.objects.exists())

    def test_snapshot_mismatch_and_completed_gio_stay_blocked(self):
        self.row.quantity = 4000
        with self.assertRaises(GIOSepidarError):
            self.approve()
        self.row.quantity = 3000
        GIO.objects.filter(pk=self.gio.pk).update(
            sepidar_buy_factor_response_json={'purchase_invoice': [101]},
        )
        with self.assertRaises(GIOSepidarError):
            self.approve()

    def test_reviewed_retry_requires_explicit_group_and_does_not_resend_automatically(self):
        self.approve()
        payload = {'inventorypurchaseinvoice_item': [{'itemref': 9021}]}
        response = {self.key: {'gio': {'sepidar': [{
            'purchase_invoice': {'id': 11, 'number': 101},
            'before_central_wh_receipt': {'id': 12, 'number': 102},
            'voucher': {'id': 13, 'number': 103},
        }]}}}
        with patch(
            'order.gio_sepidar.SepidarDataFactory.get_trade_inventory_purchase_invoice_data',
            return_value=payload,
        ), patch(
            'order.gio_sepidar.SepidarApiCall.gio_to_sepidar', return_value=response,
        ) as remote, patch('order.gio_sepidar._record_order_documents'):
            with self.assertRaises(GIOSepidarError):
                send_gio_groups(self.gio, SimpleNamespace(user=self.operator))
            remote.assert_not_called()
            states = send_gio_groups(
                self.gio, SimpleNamespace(user=self.operator), group_key=self.key,
            )
            self.assertEqual(remote.call_count, 1)
        self.assertEqual(states[0]['status'], 'success')
        self.record.refresh_from_db()
        self.assertEqual(self.record.attempt_count, 2)
        self.assertEqual(self.record.status, 'success')
        self.assertEqual(GIOSepidarManualReview.objects.filter(group=self.record).count(), 1)

    def test_preview_shows_manual_reviewer_and_allows_authorized_group_retry(self):
        self.approve()
        preview = gio_preview_groups(self.gio)
        self.assertEqual(preview[0]['status'], 'reviewed')
        self.assertTrue(preview[0]['can_send'])
        self.assertIn('gio_review_admin', preview[0]['manual_review']['reviewer'])
        html = render_to_string(
            'order/partial/sepidar/trade_buy_factor_preview.html',
            {'groups': preview, 'gio_sepidar_can_send': True,
             'gio_reconcile_can_review': False},
        )
        self.assertIn('ارسال مجدد پس از بررسی دستی', html)
        self.assertIn('data-manual-reviewed="true"', html)
        self.assertIn('gio_review_admin', html)
        self.assertNotIn('gio-review-unknown-group', html)

    def test_superuser_only_review_button_for_unknown_group(self):
        preview = gio_preview_groups(self.gio)
        base = {'groups': preview, 'gio_sepidar_can_send': False}
        shown = render_to_string(
            'order/partial/sepidar/trade_buy_factor_preview.html',
            {**base, 'gio_reconcile_can_review': True},
        )
        hidden = render_to_string(
            'order/partial/sepidar/trade_buy_factor_preview.html',
            {**base, 'gio_reconcile_can_review': False},
        )
        self.assertIn('gio-review-unknown-group', shown)
        self.assertNotIn('gio-review-unknown-group', hidden)
        self.assertIn('فاکتور خرید', shown)
        self.assertIn('سند حسابداری', shown)

    def test_reconcile_endpoint_rejects_non_superusers_and_allows_superuser(self):
        url = '/order/ajax/order_and_sepidar/?view_name=trade_buy_factor_reconcile'
        data = {
            'gio_id': self.gio.pk, 'group_key': self.key,
            'confirmed_group': self.key,
            'reason': 'بررسی کامل سه سند در سپیدار انجام شد و هیچ سندی ایجاد نشده است.',
            'invoice_checked': True, 'receipt_checked': True, 'voucher_checked': True,
        }
        request = RequestFactory().post(
            url, data=json.dumps(data), content_type='application/json',
        )
        request.user = self.operator
        denied = OrderAndSepidar.as_view()(request)
        self.assertEqual(denied.status_code, 403)
        request.user = self.admin
        allowed = OrderAndSepidar.as_view()(request)
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(json.loads(allowed.content)['group_key'], self.key)
        repeated = OrderAndSepidar.as_view()(request)
        self.assertEqual(repeated.status_code, 409)

    def test_view_accepts_only_post_for_reconciliation(self):
        request = RequestFactory().get(
            '/order/ajax/order_and_sepidar/?view_name=trade_buy_factor_reconcile',
        )
        request.user = self.admin
        self.assertEqual(OrderAndSepidar.as_view()(request).status_code, 405)

    def test_confirmation_modal_and_scripts_are_present(self):
        source = get_template('order/gio/quick_gio_update.html').template.source
        self.assertIn('gio-manual-review-modal', source)
        self.assertIn('gio-review-invoice', source)
        self.assertIn('gio-review-receipt', source)
        self.assertIn('gio-review-voucher', source)
        self.assertIn('gio-review-confirm-key', source)
        self.assertIn('gio-review-reason', source)
        self.assertIn('trade_buy_factor_reconcile', source)
        self.assertIn("button.dataset.manualReviewed === 'true'", source)
        self.assertIn('gio_reviewed', source)
        self.assertIn('بدون بررسی کامل و مستقل هر سه سند', source)
