"""Tests for the role-scoped operational dashboard.

Run with: python manage.py test dashboards.test_operational_reports
"""
from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.http import Http404
from django.test import TestCase
from django.urls import reverse

from changelog.models import ChangeLog
from dashboards.operational_reports import (
    _transition_metrics, build_report, clamp_days, visible_users,
)
from factor.models import Factor
from micmod_base.base import Currency
from micmod_base.models import Month, Quotation, SaleType
from extra_data.models import Customer
from order.models import Order, OrderBazar
from payment.models import PaymentOrder
from workflow.models import FlowAdminGroup
from django.utils import timezone
from unittest.mock import patch


class OperationalScopeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.member = User.objects.create_user(username='op_member', password='pass')
        self.outsider = User.objects.create_user(username='op_outsider', password='pass')
        self.manager = User.objects.create_user(username='op_manager', password='pass')
        self.member.head = self.manager
        self.member.save(update_fields=['head'])

    def test_personal_access_excludes_other_users(self):
        qs, role = visible_users(self.member)
        self.assertEqual(role, 'user')
        self.assertEqual(list(qs.values_list('pk', flat=True)), [self.member.pk])
        with self.assertRaises(Http404):
            build_report(self.member, selected_user_id=self.outsider.pk)

    def test_direct_manager_can_see_own_team_but_not_unrelated(self):
        qs, role = visible_users(self.manager)
        self.assertEqual(role, 'manager')
        self.assertEqual(set(qs.values_list('pk', flat=True)),
                         {self.member.pk, self.manager.pk})
        with self.assertRaises(Http404):
            build_report(self.manager, selected_user_id=self.outsider.pk)

    def test_flow_admin_subgroups_are_scoped(self):
        parent = Group.objects.create(name='trade_admin')
        child = Group.objects.create(name='trade_user')
        self.manager.groups.add(parent)
        self.outsider.groups.add(child)
        hierarchy = FlowAdminGroup.objects.create(group_rel=parent, group_name='بازرگانی')
        hierarchy.group_child.add(child)
        users, role = visible_users(self.manager)
        self.assertEqual(role, 'manager')
        self.assertIn(self.outsider.pk, list(users.values_list('pk', flat=True)))

    def test_senior_group_sees_all_active_users(self):
        executive = Group.objects.create(name='total_admin')
        self.manager.groups.add(executive)
        qs, role = visible_users(self.manager)
        self.assertEqual(role, 'executive')
        self.assertEqual(set(qs.values_list('pk', flat=True)),
                         {self.manager.pk, self.member.pk, self.outsider.pk})

    def test_invalid_window_is_clamped(self):
        self.assertEqual(clamp_days('0'), 1)
        self.assertEqual(clamp_days('500'), 365)
        self.assertEqual(clamp_days('abc'), 30)

    def test_unauthenticated_home_redirects(self):
        response = self.client.get(reverse('dashboards:index'))
        self.assertEqual(response.status_code, 302)

    @patch('dashboards.operational_reports.build_report')
    def test_home_passes_window_and_selected_user(self, mock_report):
        self.client.force_login(self.manager)
        mock_report.return_value = {
            'days': 7, 'scope': 'manager', 'selected_user_id': self.member.pk,
            'user_options': [self.member], 'sections': [],
            'total_documents': 0, 'total_inquiries': 0,
            'total_operations': 0, 'total_contracts': 0,
        }
        response = self.client.get(reverse('dashboards:index'),
                                   {'days': '7', 'user_id': str(self.member.pk)})
        self.assertEqual(response.status_code, 200)
        mock_report.assert_called_once_with(
            self.manager, days='7', selected_user_id=str(self.member.pk)
        )


class OperationalSalesMetricsTests(TestCase):
    def test_sales_documents_values_and_unique_customers(self):
        User = get_user_model()
        sales = User.objects.create_user(username='sales_metric', password='pass')
        Group.objects.get_or_create(name='sales_user')[0].user_set.add(sales)
        other = User.objects.create_user(username='other_metric', password='pass')
        currency = Currency.objects.create(title='دلار', title_en='Dollar')
        month = Month.objects.create(title='ماه', month=1)
        sale_type = SaleType.objects.create(number=1, title='نقدی', month=month,
                                            currency=currency)
        customer = Customer.objects.create(title='خریدار آزمایشی', sepidar_party_id=900001)

        Quotation.objects.create(
            creator_user=sales, sale_type=sale_type, request_date=date.today(),
            currency_ref=currency, final_price=100.5, customer_party_id=customer,
        )
        Factor.objects.create(
            creator_user=sales, sale_type=sale_type, currency_ref=currency,
            final_price=300.25, customer_party_id=customer,
        )
        Factor.objects.create(
            creator_user=other, sale_type=sale_type, currency_ref=currency,
            final_price=999, customer_party_id=customer,
        )
        result = build_report(sales, days=30)
        sales_row = result['sections'][0]['rows'][0]
        self.assertEqual(result['total_documents'], 2)
        self.assertEqual(sales_row['invoice_count'], 1)
        self.assertEqual(sales_row['quotation_count'], 1)
        self.assertEqual(sales_row['customers'], 1)
        self.assertEqual(sales_row['invoice_amounts'][0]['currency'], 'Dollar')
        self.assertAlmostEqual(sales_row['invoice_amounts'][0]['amount'], 300.25)
        self.assertAlmostEqual(sales_row['quotation_amounts'][0]['amount'], 100.5)


class OperationalTransitionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='action_actor', password='pass'
        )
        self.rows = {self.user.pk: {
            'purchase_count': 0, 'receipt_count': 0,
            'dispatch_count': 0, 'finance_approval_count': 0,
            'paid_count': 0,
        }}

    def record(self, model, object_id, fields, actor=None):
        ChangeLog.objects.create(
            content_type=ContentType.objects.get_for_model(model),
            object_id=object_id, action=2, diff_json={'fields': fields},
            creator_user=actor if actor is not None else self.user,
        )

    def run_report(self):
        _transition_metrics(
            self.rows, timezone.now() - timedelta(days=30),
            timezone.now() + timedelta(minutes=1)
        )
        return self.rows[self.user.pk]

    def test_counts_all_five_action_categories(self):
        self.record(Factor, 11, {'accounting_confirm': [False, True]})
        self.record(Factor, 12, {'deliver_to_customer': [False, True]})
        self.record(Order, 13, {'receipt_in_wh': [False, True]})
        self.record(OrderBazar, 14, {'buy_factors': [[], [{'id': 10}]]})
        self.record(PaymentOrder, 15, {'is_paid': [False, True]})
        row = self.run_report()
        self.assertEqual(row['finance_approval_count'], 1)
        self.assertEqual(row['dispatch_count'], 1)
        self.assertEqual(row['receipt_count'], 1)
        self.assertEqual(row['purchase_count'], 1)
        self.assertEqual(row['paid_count'], 1)

    def test_repeated_update_does_not_double_count(self):
        self.record(Factor, 10, {'accounting_confirm': [False, True]})
        self.record(Factor, 10, {'accounting_confirm': [False, True]})
        self.record(Order, 22, {'buy_factors': [[], [1]]})
        self.record(Order, 22, {'buy_factors': [[1], [1, 2]]})
        row = self.run_report()
        self.assertEqual(row['finance_approval_count'], 1)
        self.assertEqual(row['purchase_count'], 1)

    def test_non_transitions_do_not_count(self):
        self.record(PaymentOrder, 1, {'is_paid': [True, True]})
        self.record(Order, 2, {'receipt_in_wh': [True, False]})
        self.record(OrderBazar, 3, {'buy_factors': [[], []]})
        row = self.run_report()
        self.assertEqual(row['paid_count'], 0)
        self.assertEqual(row['receipt_count'], 0)
        self.assertEqual(row['purchase_count'], 0)


class OperationalPresentationTests(TestCase):
    """The first screen must explain the metrics without overwhelming users."""

    def setUp(self):
        self.viewer = get_user_model().objects.create_user(
            username='dashboard_viewer', password='pass'
        )
        self.client.force_login(self.viewer)

    def sample_report(self, section_key='sales'):
        row = {
            'id': self.viewer.pk, 'name': 'کارشناس نمونه',
            'invoice_count': 3, 'quotation_count': 5, 'customers': 2,
            'invoice_amounts': [{'amount': 12500, 'currency': 'Dollar'}],
            'quotation_amounts': [{'amount': 4500, 'currency': 'RMB'}],
            'inquiry_count': 0, 'purchase_count': 0, 'dispatch_count': 0,
            'receipt_count': 0, 'finance_approval_count': 0,
            'paid_count': 0, 'contract_count': 0, 'contract_amount': 0,
        }
        section = {
            'key': section_key, 'title': 'فروش',
            'description': 'فاکتورها و مشتریان ثبت‌شده توسط کارشناس.',
            'rows': [row], 'nav_total': 8, 'primary_unit': 'سند فروش',
            'metrics': [
                {'label': 'فاکتور ثبت‌شده', 'value': 3, 'hint': 'تاریخ ایجاد'},
                {'label': 'پیش‌فاکتور ثبت‌شده', 'value': 5, 'hint': 'تاریخ ایجاد'},
            ],
        }
        return {
            'days': 30, 'scope': 'user', 'selected_user_id': None,
            'user_options': [self.viewer], 'users_count': 1,
            'visible_sections': [section],
        }

    @patch('dashboards.operational_reports.build_report')
    def test_first_screen_has_department_navigation_and_person_cards(self, mock):
        mock.return_value = self.sample_report()
        response = self.client.get(reverse('dashboards:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'در 30 روز گذشته چه کرده‌ایم؟')
        self.assertContains(response, 'عملکرد هر نفر')
        self.assertContains(response, 'کارشناس نمونه')
        self.assertContains(response, 'مشتری متفاوت')
        self.assertContains(response, 'Dollar')
        self.assertContains(response, 'RMB')
        self.assertContains(response, 'role="tablist"')
        self.assertContains(response, 'data-op-person')
        self.assertContains(response, '/assets/css/operational-dashboard.css')
        self.assertContains(response, '/assets/js/operational-dashboard.js')
        self.assertNotContains(response, 'عملکرد مالی')
        self.assertNotContains(response, 'op-table')

    @patch('dashboards.operational_reports.build_report')
    def test_filter_and_manager_scope_are_visible(self, mock):
        report = self.sample_report()
        report['days'] = 7
        report['scope'] = 'manager'
        report['selected_user_id'] = self.viewer.pk
        mock.return_value = report
        response = self.client.get(reverse('dashboards:index'))
        self.assertContains(response, 'اعضای تیم شما')
        self.assertContains(response, 'نمایش عملکرد')
        self.assertContains(response, 'تمام افراد مجاز')
        self.assertContains(response, 'name="user_id"')
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, 'min="1" max="365"')

    @patch('dashboards.operational_reports.build_report')
    def test_empty_state_guides_user_instead_of_opening_empty_teams(self, mock):
        report = self.sample_report()
        report['visible_sections'] = []
        mock.return_value = report
        response = self.client.get(reverse('dashboards:index'))
        self.assertContains(response, 'هنوز اطلاعاتی برای نمایش نیست')
        self.assertContains(response, 'نمایش ۹۰ روز گذشته')
        self.assertNotContains(response, 'data-op-tab')
        self.assertNotContains(response, 'کارشناس نمونه')

    def test_visible_sections_are_restricted_to_relevant_departments(self):
        group, _ = Group.objects.get_or_create(name='sales_user')
        self.viewer.groups.add(group)
        result = build_report(self.viewer)
        self.assertEqual([s['key'] for s in result['visible_sections']], ['sales'])
        self.assertEqual(result['visible_sections'][0]['nav_total'], 0)
        self.assertEqual(result['visible_sections'][0]['metrics'][0]['value'], 0)
