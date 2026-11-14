"""Customer legal-profile selection in the printed sales factor."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.template.loader import get_template
from django.test import RequestFactory, SimpleTestCase

from factor.print_customer import customer_print_context, apply_bulk_customer_profiles
from factor.views import print_view, factor_bulk_print


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
        self.assertIn('{% if not bulk_mode %}', html)
        self.assertIn('{% if legal_profile_options %}', html)
        self.assertIn('class="ptb-toolbar noprint"', html)
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



class BulkLegalProfileGroupingTests(SimpleTestCase):
    """Each customer has one choice shared across their documents."""

    def setUp(self):
        self.first = SimpleNamespace(
            pk=11, title='مشتری اول', national_code='100',
            address='آدرس اول', phone='0211',
            legal_profiles=[
                {'name': 'شرکت الف', 'national_id': '11111111111',
                 'postal_code': '1111111111', 'type': 'سهامی خاص', 'address': 'نشانی الف'},
                {'name': 'شرکت ب', 'national_id': '22222222222',
                 'postal_code': '2222222222', 'type': 'مسئولیت محدود', 'address': 'نشانی ب'},
            ],
        )
        self.second = SimpleNamespace(
            pk=22, title='مشتری دوم', national_code='200',
            address='آدرس دوم', phone='0212',
            legal_profiles=[{'name': 'شرکت ج', 'national_id': '33333333333',
                             'postal_code': '3333333333', 'type': 'سهامی خاص',
                             'address': 'نشانی ج'}],
        )

    def test_same_customer_one_selection_for_multiple_invoices(self):
        docs = [{'print_customer': self.first}, {'print_customer': self.first}]
        groups = apply_bulk_customer_profiles(docs, {'legal_profile_11': '1'})
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['field_name'], 'legal_profile_11')
        self.assertEqual(docs[0]['buyer_info']['name'], 'شرکت ب')
        self.assertEqual(docs[1]['buyer_info']['name'], 'شرکت ب')

    def test_different_customers_independent_choices(self):
        docs = [{'print_customer': self.first}, {'print_customer': self.second}]
        groups = apply_bulk_customer_profiles(docs, {'legal_profile_11': '1', 'legal_profile_22': '0'})
        self.assertEqual(len(groups), 2)
        self.assertEqual(docs[0]['buyer_info']['name'], 'شرکت ب')
        self.assertEqual(docs[1]['buyer_info']['name'], 'شرکت ج')
        self.assertEqual([option['selected'] for option in groups[0]['options']], [False, True])
        self.assertEqual([option['selected'] for option in groups[1]['options']], [True])

    def test_other_customer_index_is_invalid(self):
        with self.assertRaises(ValueError):
            apply_bulk_customer_profiles([{'print_customer': self.second}], {'legal_profile_22': '1'})

    def test_base_fallback_and_no_profiles(self):
        without = SimpleNamespace(pk=33, title='بدون پروفایل', legal_profiles=[],
                                  national_code='300', address='', phone='')
        docs = [{'print_customer': self.first}, {'print_customer': without}]
        groups = apply_bulk_customer_profiles(docs, {})
        self.assertEqual(len(groups), 1)
        self.assertEqual(docs[0]['buyer_info']['name'], 'مشتری اول')
        self.assertEqual(docs[1]['buyer_info']['name'], 'بدون پروفایل')

    def test_bulk_form_preserves_invoice_ids_and_csrf(self):
        body = get_template('factor/bulk_print.html').template.source
        self.assertIn('{% csrf_token %}', body)
        self.assertIn('name="ids"', body)
        self.assertIn('name="{{ customer.field_name }}"', body)
        self.assertIn('{% if not customer.selected %}selected{% endif %}', body)
        self.assertIn('{% for profile in customer.options %}', body)
        self.assertIn('{% if profile.selected %}selected{% endif %}', body)



class FactorBulkLegalProfileViewTests(SimpleTestCase):
    """The bulk endpoint must apply independent selections after permission checks."""

    def setUp(self):
        self.factory = RequestFactory()
        self.first = SimpleNamespace(
            pk=11, title='مشتری اول', legal_profiles=[
                {'name': 'شرکت اول', 'national_id': '00123456789',
                 'postal_code': '1111111111', 'type': 'سهامی خاص', 'address': 'آدرس اول'},
            ], address='آدرس پایه اول', national_code='100', phone='0211',
        )
        self.second = SimpleNamespace(
            pk=22, title='مشتری دوم', legal_profiles=[
                {'name': 'شرکت دوم', 'national_id': '00123456780',
                 'postal_code': '2222222222', 'type': 'مسئولیت محدود', 'address': 'آدرس دوم'},
            ], address='آدرس پایه دوم', national_code='200', phone='0212',
        )

    def _call(self, params):
        request = self.factory.post('/factor/factor/bulk-print/', params)
        request.user = SimpleNamespace(is_authenticated=True)
        by_id = {101: self.first, 102: self.second}

        def document(request, id, context_only=False):
            self.assertTrue(context_only)
            return {'print_customer': by_id[id], 'data': SimpleNamespace(id=id)}

        with (
            patch('factor.views.FactorListDatatable') as table,
            patch('factor.views.Factor.get_qs') as get_qs,
            patch('factor.views.print_view', side_effect=document),
            patch('factor.views.render') as render,
        ):
            table.return_value.get_initial_queryset.return_value.filter.return_value.values_list.return_value.distinct.return_value = [101, 102]
            get_qs.return_value.filter.return_value.values_list.return_value.distinct.return_value = [101, 102]
            response = factor_bulk_print(request)
            if render.called:
                return render.call_args.args[2]
            return response

    def test_independent_customer_selection_on_bulk_factor_print(self):
        context = self._call({
            'ids': ['101', '102'], 'legal_profile_11': '0', 'legal_profile_22': '',
        })
        self.assertEqual(len(context['customers']), 2)
        self.assertEqual(context['documents'][0]['buyer_info']['name'], 'شرکت اول')
        self.assertEqual(context['documents'][1]['buyer_info']['name'], 'مشتری دوم')

    def test_invalid_customer_profile_on_bulk_factor_print_returns_400(self):
        result = self._call({
            'ids': ['101', '102'], 'legal_profile_11': '2',
        })
        self.assertEqual(result.status_code, 400)

    def test_bulk_factor_print_keeps_id_order(self):
        context = self._call({
            'ids': ['102', '101'], 'legal_profile_22': '0',
        })
        self.assertEqual(context['ids'], [102, 101])
        self.assertEqual(context['documents'][0]['buyer_info']['name'], 'شرکت دوم')



class FactorPrintToolbarStyleTests(SimpleTestCase):
    """Invoice print controls are in the same compact shared toolbar as quotations."""

    def test_invoice_toolbar_includes_print_profile_and_warehouse_action(self):
        html = get_template('factor/factor_print.html').template.source
        self.assertIn('{% if not bulk_mode %}\n<section class="ptb-toolbar noprint"', html)
        self.assertIn('id="id_print_btn"', html)
        self.assertIn('id="factor-legal-profile-form"', html)
        self.assertIn('id="factor-legal-profile-select"', html)
        self.assertIn('id="calculate-button"', html)
        self.assertIn('class="ptb-actions"', html)
        self.assertIn('class="ptb-profile-zone"', html)
        self.assertIn('factor/css/print_toolbar.css', html)
        self.assertNotIn('class="noprint border rounded p-3', html)

    def test_invoice_warehouse_handler_only_attaches_if_button_exists(self):
        html = get_template('factor/factor_print.html').template.source
        self.assertIn("document.getElementById('calculate-button')?.addEventListener", html)
        self.assertNotIn('    debugger\n', html)

    def test_invoice_bulk_toolbar_uses_same_styles_and_preserves_customer_ids(self):
        html = get_template('factor/bulk_print.html').template.source
        self.assertIn('class="bulk-toolbar ptb-toolbar noprint"', html)
        self.assertIn('name="{{ customer.field_name }}"', html)
        self.assertIn('name="ids"', html)
        self.assertIn('name="q"', html)
        self.assertIn('{% csrf_token %}', html)
        self.assertIn("factor/css/print_toolbar.css", html)
        self.assertIn('class="ptb-profile-actions"', html)
        self.assertNotIn('onchange="this.form.submit()"', html)
