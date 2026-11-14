"""Legal profile selections on single and bulk quotation printouts."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.template.loader import get_template
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from micmod_base.views import print_view, quotation_bulk_print


class QuotationLegalProfilePrintTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.first = SimpleNamespace(
            pk=11, title='مشتری اول', national_code='0000000011',
            address='آدرس مشتری اول', phone='021123',
            legal_profiles=[
                {'name': 'شرکت اول', 'national_id': '00123456789', 'type': 'سهامی خاص',
                 'postal_code': '0123456789', 'address': 'آدرس شرکت اول'},
                {'name': 'شرکت دوم', 'national_id': '00123456780', 'type': 'مسئولیت محدود',
                 'postal_code': '9988776655', 'address': 'آدرس شرکت دوم'},
            ],
        )
        self.second = SimpleNamespace(
            pk=22, title='مشتری دیگر', national_code='0000000022',
            address='آدرس مشتری دیگر', phone='021456',
            legal_profiles=[
                {'name': 'شرکت سوم', 'national_id': '00333333333',
                 'type': 'سهامی خاص', 'postal_code': '1111111111',
                 'address': 'آدرس شرکت سوم'},
            ],
        )

    def _user(self):
        return SimpleNamespace(is_authenticated=True, base_group='sales')

    def _single(self, path, params):
        request = self.factory.get(path, params)
        request.user = self._user()
        quotation = SimpleNamespace(
            customer_party_id=self.first,
            created_date=datetime(2026, 11, 14, 10),
            last_update_date=datetime(2026, 11, 14, 10),
        )
        with (
            patch('micmod_base.views.Quotation.objects.filter') as queryset,
            patch('micmod_base.views.QuotationForm'),
            patch('micmod_base.views.inlineformset_factory'),
            patch('micmod_base.views.datetime2jalali', side_effect=lambda value: value),
        ):
            queryset.return_value.first.return_value = quotation
            return print_view(request, id=101, context_only=True)

    def test_customer_print_uses_selected_profile(self):
        result = self._single(reverse('micmod_base:print_customer', args=[101]),
                              {'legal_profile': '1'})
        self.assertEqual(result['buyer_info']['name'], 'شرکت دوم')
        self.assertEqual(result['buyer_info']['national_number'], '00123456780')
        self.assertEqual(result['buyer_info']['postal_code'], '9988776655')
        self.assertEqual(result['buyer_info']['address'], 'آدرس شرکت دوم')
        self.assertEqual(result['selected_legal_profile'], '1')

    def test_expert_print_has_same_selection(self):
        result = self._single(reverse('micmod_base:quotations.print-view', args=[101]),
                              {'legal_profile': '0'})
        self.assertEqual(result['buyer_info']['name'], 'شرکت اول')
        self.assertEqual(result['buyer_info']['type'], 'سهامی خاص')

    def test_default_uses_customer_base_data(self):
        result = self._single(reverse('micmod_base:print_customer', args=[101]), {})
        self.assertEqual(result['buyer_info']['name'], 'مشتری اول')
        self.assertEqual(result['buyer_info']['national_number'], '0000000011')

    def test_invalid_selection_is_rejected(self):
        result = self._single(reverse('micmod_base:print_customer', args=[101]),
                              {'legal_profile': '99'})
        self.assertEqual(result.status_code, 400)

    def test_single_quotation_print_requires_login(self):
        request = self.factory.get(reverse('micmod_base:print_customer', args=[101]))
        request.user = AnonymousUser()
        response = print_view(request, id=101)
        self.assertEqual(response.status_code, 302)

    def test_customer_and_expert_templates_both_use_selected_buyer(self):
        customer = get_template('micmod-base/quotation/view-print-raw.html').template.source
        expert = get_template('micmod-base/quotation/view-print.html').template.source
        picker = get_template('micmod-base/quotation/partial/legal_profile_picker.html').template.source
        for token in ('{{ buyer_info.name }}', '{{ buyer_info.address }}',
                      '{{ buyer_info.national_number }}', '{{ buyer_info.postal_code }}'):
            self.assertIn(token, customer)
        self.assertIn('{{ buyer_info.national_number }}', expert)
        self.assertIn('{{ buyer_info.postal_code }}', expert)
        self.assertIn('{% if buyer_info.is_legal_profile %}', expert)
        self.assertIn('name="legal_profile"', picker)
        self.assertIn('request.GET.customer_goods_code_url_param', picker)
        self.assertIn('request.GET.comments_url_params', picker)


class QuotationBulkLegalProfilePrintTests(SimpleTestCase):
    setUp = QuotationLegalProfilePrintTests.setUp
    _user = QuotationLegalProfilePrintTests._user

    """Test multiple customers, same-customer sharing and access checks."""

    def _bulk(self, ids, choices=None, allowed=None):
        params = {'ids': [str(id_value) for id_value in ids], 'q': 'sales_user'}
        params.update(choices or {})
        request = self.factory.post(reverse('micmod_base:quotation.bulk_print'), params)
        request.user = self._user()
        client_by_id = {101: self.first, 102: self.second, 103: self.first}
        allowed = list(ids) if allowed is None else allowed

        def document(request, id, context_only=False):
            self.assertTrue(context_only)
            return {'print_customer': client_by_id[id], 'data': SimpleNamespace(id=id),
                    'buyer_info': {'name': client_by_id[id].title}}

        with (
            patch('micmod_base.views.QuotationListDatatable') as datatable,
            patch('micmod_base.views.Quotation.get_qs') as get_qs,
            patch('micmod_base.views.print_view', side_effect=document),
            patch('micmod_base.views.render') as rendered,
        ):
            datatable.return_value.get_initial_queryset.return_value.filter.return_value.values_list.return_value.distinct.return_value = allowed
            get_qs.return_value.filter.return_value.values_list.return_value.distinct.return_value = allowed
            response = quotation_bulk_print(request)
            if rendered.called:
                return rendered.call_args.args[2]
            return response

    def test_distinct_customers_select_independently(self):
        ctx = self._bulk([101, 102], {'legal_profile_11': '1', 'legal_profile_22': '0'})
        self.assertEqual(len(ctx['customers']), 2)
        self.assertEqual(ctx['documents'][0]['buyer_info']['name'], 'شرکت دوم')
        self.assertEqual(ctx['documents'][1]['buyer_info']['name'], 'شرکت سوم')

    def test_same_customer_uses_one_selection_in_all_quotations(self):
        ctx = self._bulk([101, 103], {'legal_profile_11': '0'})
        self.assertEqual(len(ctx['customers']), 1)
        self.assertEqual(ctx['documents'][0]['buyer_info']['name'], 'شرکت اول')
        self.assertEqual(ctx['documents'][1]['buyer_info']['name'], 'شرکت اول')
        self.assertEqual(ctx['ids'], [101, 103])

    def test_print_style_preserved_when_applying_profiles(self):
        ctx = self._bulk([101], {'print_style': 'expert', 'legal_profile_11': '1'})
        self.assertEqual(ctx['print_style'], 'expert')
        self.assertEqual(ctx['documents'][0]['buyer_info']['name'], 'شرکت دوم')

    def test_invalid_other_customer_profile_returns_400(self):
        response = self._bulk([102], {'legal_profile_22': '1'})
        self.assertEqual(response.status_code, 400)

    def test_missing_permission_rejects_entire_batch(self):
        with self.assertRaises(PermissionDenied):
            self._bulk([101, 102], allowed=[101])

    def test_duplicate_and_over_limit_rejected_before_query(self):
        for ids in ([101, 101], list(range(1, 33))):
            with self.subTest(ids=ids):
                req = self.factory.post(reverse('micmod_base:quotation.bulk_print'),
                                        {'ids': [str(n) for n in ids]})
                req.user = self._user()
                response = quotation_bulk_print(req)
                self.assertEqual(response.status_code, 400)

    def test_bulk_template_has_independent_customer_selectors(self):
        html = get_template('micmod-base/quotation/bulk_print.html').template.source
        self.assertIn('name="{{ customer.field_name }}"', html)
        self.assertIn('name="ids"', html)
        self.assertIn('{% csrf_token %}', html)
        self.assertIn('print_style', html)
        self.assertIn('view-print-raw.html', html)
        self.assertIn('view-print.html', html)

    def test_list_template_can_submit_selected_quotations(self):
        html = get_template('micmod-base/quotation/list_datatable.html').template.source
        self.assertIn('id="quotation-bulk-form"', html)
        self.assertIn('quotation.bulk_print', html)
        self.assertIn('js-quotation-bulk', html)



class QuotationCustomerPrintToolbarLayoutTests(SimpleTestCase):
    """The customer print tools share a responsive, print-hidden in-flow toolbar."""

    def test_customer_print_tools_are_not_absolute_or_separate(self):
        source = get_template('micmod-base/quotation/view-print-raw.html').template.source
        start = source.index('class="quotation-customer-print-toolbar noprint"')
        end = source.index('\n</div>\n{% endif %}', start)
        toolbar = source[start:end]
        self.assertNotIn('position-absolute', toolbar)
        self.assertIn('id="id_print_btn"', toolbar)
        self.assertIn("micmod_base:quotations.print-view", toolbar)
        self.assertIn("micmod_base:print_customer", toolbar)
        self.assertIn("{% include 'micmod-base/quotation/partial/legal_profile_picker.html' %}", toolbar)
        self.assertLess(toolbar.index('quotation-customer-print-actions'),
                        toolbar.index('legal_profile_picker.html'))
        self.assertEqual(source.count('legal_profile_picker.html'), 1)
        self.assertIn('class="quotation-customer-print-toolbar noprint"', source)

    def test_expert_and_goods_links_preserve_profile_and_have_complete_href(self):
        source = get_template('micmod-base/quotation/view-print-raw.html').template.source
        self.assertIn(
            '''?legal_profile={{ selected_legal_profile|default:''|urlencode }}"''',
            source,
        )
        self.assertIn(
            '''&amp;legal_profile={{ selected_legal_profile|default:''|urlencode }}"''',
            source,
        )
        self.assertNotIn(
            '''?legal_profile={{ selected_legal_profile|default:'' }} class=''', source,
        )

    def test_toolbar_is_responsive_and_hidden_in_print(self):
        source = get_template('micmod-base/quotation/view-print-raw.html').template.source
        self.assertIn('.quotation-customer-print-toolbar {', source)
        self.assertIn('display: flex;', source)
        self.assertIn('flex-wrap: wrap;', source)
        self.assertIn('@media (max-width: 767px)', source)
        self.assertIn('class="quotation-customer-print-toolbar noprint"', source)
        self.assertIn('.noprint {\\n              display: none !important;', source)
