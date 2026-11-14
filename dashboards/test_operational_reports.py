"""Tests for the role-scoped operational dashboard.

Run with: python manage.py test dashboards.test_operational_reports
"""
from datetime import date, timedelta
from decimal import Decimal
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
from workflow.models import FlowAdminGroup, WorkFlow
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
            currency_ref=currency, rate=30000, final_price=100.5,
            customer_party_id=customer,
        )
        Factor.objects.create(
            creator_user=sales, sale_type=sale_type, currency_ref=currency,
            final_price=300.25, currency_amount=Decimal('50000'),
            customer_party_id=customer,
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
        self.assertEqual(sales_row['invoice_total_rial'], Decimal('15012500'))
        self.assertEqual(sales_row['quotation_total_rial'], Decimal('3015000'))
        self.assertEqual(sales_row['invoice_unconverted'], 0)
        self.assertEqual(sales_row['quotation_unconverted'], 0)


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
            'invoice_total_rial': Decimal('12500'),
            'quotation_total_rial': Decimal('4500'),
            'invoice_unconverted': 0, 'quotation_unconverted': 0,
            'active_factors': [
                {'id': 84, 'url': '/factor/view/84/',
                 'state': 'جمع‌آوری', 'customer': 'مشتری'}
            ],
            'active_quotations': [], 'active_factor_count': 1,
            'active_quotation_count': 0,
            'active_factor_more_url': '/work-items/1/?type=factor',
            'active_quotation_more_url': '',
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
        self.assertContains(response, '12,500')
        self.assertContains(response, '4,500')
        self.assertContains(response, 'فاکتور #84')
        self.assertContains(response, 'در حال انجام این کاربر')
        self.assertContains(response, 'ریال')
        self.assertNotContains(response, 'Dollar')
        self.assertNotContains(response, 'RMB')
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


class OperationalSalesTotalsAndLinksTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.sales = User.objects.create_user(
            username='op_sales_total', password='pass'
        )
        self.other = User.objects.create_user(
            username='op_other_total', password='pass'
        )
        self.manager = User.objects.create_user(
            username='op_manager_total', password='pass'
        )
        self.sales.head = self.manager
        self.sales.save(update_fields=['head'])
        self.group, _ = Group.objects.get_or_create(name='sales_user')
        self.sales.groups.add(self.group)
        self.rial = Currency.objects.create(title='ریال', title_en='Rial')
        self.usd = Currency.objects.create(title='دلار', title_en='Dollar')
        self.month = Month.objects.create(title='ماه تست', month=11)
        self.sale_type = SaleType.objects.create(
            title='تست', number=2, month=self.month, currency=self.rial
        )
        self.customer = Customer.objects.create(
            title='مشتری داشبورد', sepidar_party_id=880001
        )

    def factor(self, creator=None, **kwargs):
        return Factor.objects.create(
            creator_user=creator or self.sales,
            sale_type=self.sale_type,
            customer_party_id=self.customer, **kwargs
        )

    def quotation(self, creator=None, **kwargs):
        return Quotation.objects.create(
            creator_user=creator or self.sales,
            sale_type=self.sale_type,
            customer_party_id=self.customer,
            request_date=date.today(), **kwargs
        )

    def assign(self, document, user, state):
        flow = WorkFlow.objects.create(
            from_user=self.sales, to_user=user,
            action='next', wf_status=3, current_state_name=state,
            content_type=ContentType.objects.get_for_model(type(document)),
            object_id=document.pk,
        )
        type(document).objects.filter(pk=document.pk).update(last_work_flow=flow)

    def test_mixed_currency_sales_totals_are_in_rial(self):
        self.factor(currency_ref=self.rial, final_price=125000)
        self.factor(currency_ref=self.usd, final_price=10,
                    currency_amount=Decimal('60000'))
        self.quotation(currency_ref=self.rial, final_price=50000)
        self.quotation(currency_ref=self.usd, final_price=2, rate=70000)
        row = build_report(self.sales)['sections'][0]['rows'][0]
        self.assertEqual(row['invoice_count'], 2)
        self.assertEqual(row['quotation_count'], 2)
        self.assertEqual(row['invoice_total_rial'], Decimal('725000'))
        self.assertEqual(row['quotation_total_rial'], Decimal('190000'))
        self.assertEqual(row['invoice_unconverted'], 0)
        self.assertEqual(row['quotation_unconverted'], 0)

    def test_missing_historical_rate_does_not_get_made_up(self):
        self.factor(currency_ref=self.usd, final_price=300)
        self.quotation(currency_ref=self.usd, final_price=400)
        row = build_report(self.sales)['sections'][0]['rows'][0]
        self.assertEqual(row['invoice_count'], 1)
        self.assertEqual(row['quotation_count'], 1)
        self.assertEqual(row['invoice_unconverted'], 1)
        self.assertEqual(row['quotation_unconverted'], 1)
        self.assertEqual(row['invoice_total_rial'], Decimal('0'))
        self.assertEqual(row['quotation_total_rial'], Decimal('0'))

    def test_current_assignment_links_are_separate_from_created_totals(self):
        open_factor = self.factor(
            creator=self.other, currency_ref=self.rial, final_price=800
        )
        open_quote = self.quotation(
            creator=self.other, currency_ref=self.rial, final_price=900
        )
        finished_factor = self.factor(
            currency_ref=self.rial, final_price=100
        )
        other_factor = self.factor(
            currency_ref=self.rial, final_price=200
        )
        self.assign(open_factor, self.sales, 'جمع‌‌آوری')
        self.assign(open_quote, self.sales, 'استعلام قیمت')
        self.assign(finished_factor, self.sales, 'مرحله نهایی')
        self.assign(other_factor, self.other, 'تایید مدیر فروش')

        row = build_report(self.sales)['sections'][0]['rows'][0]
        self.assertEqual(row['invoice_count'], 2)
        self.assertEqual(row['quotation_count'], 0)
        self.assertEqual(row['active_factor_count'], 1)
        self.assertEqual(row['active_quotation_count'], 1)
        self.assertEqual([doc['id'] for doc in row['active_factors']],
                         [open_factor.pk])
        self.assertEqual([doc['id'] for doc in row['active_quotations']],
                         [open_quote.pk])
        self.assertEqual(row['active_factors'][0]['url'],
                         reverse('factor:factor.view', kwargs={'pk': open_factor.pk}))
        self.assertEqual(row['active_quotations'][0]['url'],
                         reverse('micmod_base:quotations.view',
                                 kwargs={'pk': open_quote.pk}))

    def test_all_open_documents_page_is_scope_checked(self):
        open_factor = self.factor(currency_ref=self.rial, final_price=50)
        self.assign(open_factor, self.sales, 'جمع‌‌آوری')
        url = reverse('dashboards:sales_work_items',
                      kwargs={'user_id': self.sales.pk})

        self.client.force_login(self.sales)
        response = self.client.get(url + '?type=factor')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'فاکتور شماره {open_factor.pk}')
        self.assertContains(response, reverse('factor:factor.view',
                                               kwargs={'pk': open_factor.pk}))

        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)

        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_closed_documents_and_cancelled_documents_are_excluded(self):
        ended = self.quotation(currency_ref=self.rial, final_price=30)
        cancelled = self.factor(
            currency_ref=self.rial, final_price=20, cancel=True
        )
        self.assign(ended, self.sales, 'مرحله نهایی')
        self.assign(cancelled, self.sales, 'جمع‌‌آوری')
        row = build_report(self.sales)['sections'][0]['rows'][0]
        self.assertEqual(row['active_factor_count'], 0)
        self.assertEqual(row['active_quotation_count'], 0)

    def test_historical_amount_and_count_use_the_same_time_window(self):
        recent = self.factor(currency_ref=self.rial, final_price=300)
        older = self.factor(currency_ref=self.rial, final_price=700)
        older_quote = self.quotation(currency_ref=self.rial, final_price=2000)
        Factor.objects.filter(pk=older.pk).update(
            created_date=timezone.now() - timedelta(days=45)
        )
        Quotation.objects.filter(pk=older_quote.pk).update(
            created_date=timezone.now() - timedelta(days=45)
        )
        row = build_report(self.sales, days=30)['sections'][0]['rows'][0]
        self.assertEqual(row['invoice_count'], 1)
        self.assertEqual(row['invoice_total_rial'], Decimal('300'))
        self.assertEqual(row['quotation_count'], 0)
        self.assertEqual(row['quotation_total_rial'], Decimal('0'))

    def test_open_document_preview_is_limited_but_full_list_is_complete(self):
        for _ in range(7):
            doc = self.factor(currency_ref=self.rial, final_price=100)
            self.assign(doc, self.sales, 'جمع‌‌آوری')
        row = build_report(self.sales)['sections'][0]['rows'][0]
        self.assertEqual(row['active_factor_count'], 7)
        self.assertEqual(len(row['active_factors']), 5)
        self.assertIn(
            reverse('dashboards:sales_work_items',
                    kwargs={'user_id': self.sales.pk}),
            row['active_factor_more_url']
        )
        self.client.force_login(self.sales)
        response = self.client.get(
            reverse('dashboards:sales_work_items',
                    kwargs={'user_id': self.sales.pk}) + '?type=factor'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['documents']), 7)
