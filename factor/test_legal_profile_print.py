"""Customer legal-profile selection in the printed sales factor."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.template.loader import get_template
from django.test import RequestFactory, SimpleTestCase

from factor.print_customer import customer_print_context
from factor.views import print_view


class LegalProfileFactorPrintTests(SimpleTestCase):
    def setUp(self):
        self.customer = SimpleNamespace(
            title='مشتری پایه',
            national_code='0011223344',
            address='آدرس پایه',
            phone='021222222',
            legal_profiles=[
                {'name': 'شرکت الف', 'national_id': '00123456789',
                 'type': 'سهامی خاص', 'postal_code': '0123456789',
                 'address': 'آدرس الف'},
                {'name': 'شرکت ب', 'national_id': '00123456780',
                 'type': 'مسئولیت محدود', 'postal_code': '9988776655',
                 'address': 'آدرس ب'},
            ],
        )

    def test_default_print_uses_base_customer_data(self):
        ctx = customer_print_context(self.customer)
        self.assertEqual(ctx['buyer_info']['name'], 'مشتری پایه')
        self.assertEqual(ctx['buyer_info']['national_number'], '0011223344')
        self.assertFalse(ctx['buyer_info']['is_legal_profile'])
        self.assertEqual(len(ctx['legal_profile_options']), 2)

    def test_selected_print_changes_all_legal_fields_but_not_original_customer(self):
        ctx = customer_print_context(self.customer, '1')
        info = ctx['buyer_info']
        self.assertEqual(info['name'], 'شرکت ب')
        self.assertEqual(info['national_number'], '00123456780')
        self.assertEqual(info['postal_code'], '9988776655')
        self.assertEqual(info['type'], 'مسئولیت محدود')
        self.assertEqual(info['address'], 'آدرس ب')
        self.assertEqual(info['phone'], '021222222')
        self.assertEqual(info['economical_number'], '-')
        self.assertTrue(ctx['legal_profile_options'][1]['selected'])
        self.assertEqual(self.customer.title, 'مشتری پایه')

    def test_invalid_foreign_or_injected_selection_rejected(self):
        for invalid in ('2', '-1', '1;DROP', '۰۰', '00', 'abc', '99999999999999'):
            with self.subTest(selection=invalid), self.assertRaises(ValueError):
                customer_print_context(self.customer, invalid)

    def test_no_profiles_and_malformed_entries(self):
        old = self.customer.legal_profiles[1]
        self.customer.legal_profiles = [None, {}, old]
        ctx = customer_print_context(self.customer, '2')
        self.assertEqual(ctx['buyer_info']['name'], 'شرکت ب')
        self.assertEqual(ctx['legal_profile_options'][0]['value'], '2')
        self.customer.legal_profiles = []
        self.assertEqual(customer_print_context(self.customer)['legal_profile_options'], [])
        with self.assertRaises(ValueError):
            customer_print_context(self.customer, '0')

    def test_print_template_is_bound_to_selected_profile_not_legacy_quotation(self):
        html = get_template('factor/factor_print.html').template.source
        for key in ('name', 'address', 'national_number', 'postal_code', 'type'):
            self.assertIn('{{ buyer_info.' + key + ' }}', html)
        self.assertNotIn('data.q.customer_party_id', html)
        self.assertIn('id="factor-legal-profile-select"', html)
        self.assertIn('{% if not bulk_mode and legal_profile_options %}', html)
        bulk = get_template('factor/bulk_print.html').template.source
        self.assertIn('buyer_info=doc.buyer_info', bulk)

    def _context_from_view(self, params):
        request = RequestFactory().get('/factor/factor/print/73/', params)
        request.user = SimpleNamespace(is_authenticated=True)
        factor = SimpleNamespace(
            get_customer_party_id=self.customer,
            created_date=datetime(2026, 11, 14, 12),
            last_update_date=datetime(2026, 11, 14, 12),
        )
        with (
            patch('factor.views.Factor.objects.filter') as factor_qs,
            patch('factor.views.FactorModelForm'),
            patch('factor.views.inlineformset_factory'),
            patch('factor.views.datetime2jalali', side_effect=lambda value: value),
        ):
            factor_qs.return_value.first.return_value = factor
            return print_view(request, id=73, context_only=True)

    def test_print_view_retrieves_selected_profile_of_factor_customer(self):
        context = self._context_from_view({'action': 'factor_print', 'legal_profile': '0'})
        self.assertEqual(context['buyer_info']['name'], 'شرکت الف')
        self.assertEqual(context['buyer_info']['national_number'], '00123456789')

    def test_print_view_without_selection_keeps_base_fields(self):
        context = self._context_from_view({'action': 'factor_print'})
        self.assertEqual(context['buyer_info']['name'], 'مشتری پایه')

    def test_invalid_selected_index_returns_400(self):
        result = self._context_from_view({'action': 'factor_print', 'legal_profile': '4'})
        self.assertEqual(result.status_code, 400)

    def test_warehouse_permit_ignores_legal_profile_selection(self):
        context = self._context_from_view({'action': 'wh_exit_permit', 'legal_profile': '4'})
        self.assertNotIn('buyer_info', context)

    def test_anonymous_print_request_requires_login(self):
        request = RequestFactory().get('/factor/factor/print/73/', {'legal_profile': '0'})
        request.user = AnonymousUser()
        result = print_view(request, id=73, context_only=True)
        self.assertEqual(result.status_code, 302)
