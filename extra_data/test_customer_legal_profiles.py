"""Customer legal-profile JSON validation and persistence regression tests."""

import json

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from extra_data.customer_legal_profiles import normalize_customer_legal_profiles
from extra_data.forms import CustomerForm
from extra_data.models import Customer, CustomerType


PROFILE = {
    'name': 'شرکت نمونه',
    'national_id': '00123456789',
    'type': 'سهامی خاص',
    'postal_code': '0123456789',
    'address': 'تهران، خیابان نمونه',
}


class CustomerLegalProfileValidationTests(SimpleTestCase):
    def test_multiple_profiles_and_blank_row(self):
        second = dict(PROFILE, name='مجموعه دوم', national_id='00123456780')
        result = normalize_customer_legal_profiles([PROFILE, {}, second])
        self.assertEqual(result, [PROFILE, second])

    def test_accepts_persian_and_arabic_digits_while_preserving_leading_zero(self):
        data = dict(PROFILE, national_id='۰۰۱۲۳۴۵۶۷۸۹', postal_code='٠١٢٣٤٥٦٧٨٩')
        self.assertEqual(normalize_customer_legal_profiles([data])[0]['national_id'], '00123456789')
        self.assertEqual(normalize_customer_legal_profiles([data])[0]['postal_code'], '0123456789')

    def test_rejects_partial_or_wrongly_typed_rows(self):
        for value in ([{'name': 'تنها نام'}], [42], {'name': 'مشتری'}, [dict(PROFILE, postal_code='123')]):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                normalize_customer_legal_profiles(value)

    def test_rejects_too_many_rows(self):
        with self.assertRaises(ValidationError):
            normalize_customer_legal_profiles([PROFILE] * 101)

    def test_model_field_uses_independent_list_default(self):
        field = Customer._meta.get_field('legal_profiles')
        a, b = field.get_default(), field.get_default()
        self.assertEqual(a, [])
        self.assertIsNot(a, b)


class CustomerLegalProfileFormTests(TestCase):
    def customer_form(self, value, instance=None):
        return CustomerForm(
            data={
                'title': 'مشتری تست پروفایل حقوقی',
                'type': CustomerType.Company,
                'legal_profiles': json.dumps(value, ensure_ascii=False),
            },
            instance=instance,
        )

    def test_create_edit_and_delete_profiles(self):
        form = self.customer_form([PROFILE, dict(PROFILE, name='مشتری دوم')])
        self.assertTrue(form.is_valid(), form.errors.as_json())
        customer = form.save()
        customer.refresh_from_db()
        self.assertEqual(len(customer.legal_profiles), 2)

        edited = self.customer_form([dict(PROFILE, name='ویرایش شده')], instance=customer)
        self.assertTrue(edited.is_valid(), edited.errors.as_json())
        edited.save()
        customer.refresh_from_db()
        self.assertEqual(customer.legal_profiles[0]['name'], 'ویرایش شده')
        self.assertEqual(len(customer.legal_profiles), 1)

        emptied = self.customer_form([], instance=customer)
        self.assertTrue(emptied.is_valid(), emptied.errors.as_json())
        emptied.save()
        customer.refresh_from_db()
        self.assertEqual(customer.legal_profiles, [])

    def test_invalid_input_does_not_overwrite_existing_data(self):
        customer = Customer.objects.create(
            title='مشتری تست پروفایل حقوقی', legal_profiles=[PROFILE],
        )
        bad = self.customer_form([{'name': 'ناتمام'}], instance=customer)
        self.assertFalse(bad.is_valid())
        self.assertIn('legal_profiles', bad.errors)
        customer.refresh_from_db()
        self.assertEqual(customer.legal_profiles, [PROFILE])

    def test_missing_legacy_field_does_not_clear_existing_profiles(self):
        customer = Customer.objects.create(
            title='مشتری تست پروفایل حقوقی', legal_profiles=[PROFILE],
        )
        form = CustomerForm(
            data={'title': customer.title, 'type': CustomerType.Company},
            instance=customer,
        )
        self.assertTrue(form.is_valid(), form.errors.as_json())
        form.save()
        customer.refresh_from_db()
        self.assertEqual(customer.legal_profiles, [PROFILE])




class CustomerLegalProfileSalesStyleTests(SimpleTestCase):
    """Match the shared multi-condition invoice/quotation design language."""

    def test_native_details_and_metronic_card_match_sales_editor(self):
        from django.template.loader import get_template

        customer = get_template('extra_data/customer.html').template.source
        sales = get_template('factor/partial/sale_conditions_editor.html').template.source
        for marker in ('class="card shadow-sm', '<details class=', '<summary class='):
            self.assertIn(marker, sales)
        self.assertIn('class="card shadow-sm clp-card"', customer)
        self.assertIn('<details class="clp-accordion"', customer)
        self.assertIn('class="card-header border-0 clp-header"', customer)
        self.assertIn('symbol symbol-30px bg-light-primary', customer)
        self.assertIn('class="card-body clp-body"', customer)
        self.assertIn('class="btn btn-sm btn-primary clp-add-profile"', customer)
        self.assertIn('{% if form.legal_profiles.errors %}open{% endif %}', customer)
        self.assertIn('{{ form.legal_profiles }}', customer)

    def test_separate_summary_cards_and_fields_remain_available(self):
        from django.template.loader import get_template

        customer = get_template('extra_data/customer.html').template.source
        self.assertIn('id="customer-legal-profiles-cards"', customer)
        self.assertIn('data-legal-summary-card', customer)
        self.assertIn('id="customer-legal-profile-add"', customer)
        self.assertIn('data-legal-remove', customer)
        for field in ('name', 'national_id', 'type', 'postal_code', 'address'):
            self.assertIn('data-legal-field="' + field + '"', customer)

    def test_styles_match_sales_accent_and_responsive_columns(self):
        from django.conf import settings
        from pathlib import Path

        css = (Path(settings.BASE_DIR) / 'extra_data/static/extra_data/css/customer_legal_profiles.css').read_text(encoding='utf-8')
        for value in ('#e1e9ef', '#087f78', '#fbfdfd', '#81a8d6'):
            self.assertIn(value, css)
        for grid in ('repeat(4, minmax(0, 1fr))',
                     'repeat(3, minmax(0, 1fr))',
                     'repeat(2, minmax(0, 1fr))'):
            self.assertIn(grid, css)
        self.assertIn('.clp-accordion:not([open])', css)

    def test_javascript_preserves_json_and_safe_card_rendering(self):
        from django.conf import settings
        from pathlib import Path

        script = (Path(settings.BASE_DIR) / 'extra_data/static/extra_data/js/customer_legal_profiles.js').read_text(encoding='utf-8')
        self.assertIn("details.open = true", script)
        self.assertIn('hidden.value = JSON.stringify(activeProfiles())', script)
        self.assertIn('cards.replaceChildren(fragment)', script)
        self.assertIn('textContent = profile.national_id', script)
        self.assertNotIn('cards.innerHTML', script)


    def test_profile_row_matches_sale_conditions_remove_button(self):
        """Remove button has the same glyph, styling and placement as payment rows."""
        from django.conf import settings
        from django.template.loader import get_template
        from pathlib import Path

        customer = get_template('extra_data/customer.html').template.source
        self.assertNotIn('clp-row-subtitle', customer)
        self.assertNotIn('data-legal-row-summary', customer)
        self.assertNotIn('clp-row-identity', customer)
        self.assertIn('class="clp-row-header"', customer)
        self.assertIn('class="btn btn-sm btn-light-danger" data-legal-remove', customer)
        self.assertIn('title="حذف پروفایل" aria-label="حذف پروفایل">×</button>', customer)

        sales = (Path(settings.BASE_DIR) / 'factor/static/factor/js/sale_conditions.js').read_text(encoding='utf-8')
        self.assertIn('class="btn btn-sm btn-light-danger" data-action="remove"', sales)
        self.assertIn('aria-label="حذف شرط">×</button>', sales)

    def test_profile_remove_button_css_and_js_regression(self):
        """Removing the subtitle leaves a functioning remove control and JSON sync."""
        from django.conf import settings
        from pathlib import Path

        root = Path(settings.BASE_DIR) / 'extra_data/static/extra_data'
        css = (root / 'css/customer_legal_profiles.css').read_text(encoding='utf-8')
        js = (root / 'js/customer_legal_profiles.js').read_text(encoding='utf-8')

        self.assertNotIn('.clp-row-subtitle', css)
        self.assertNotIn('.clp-remove', css)
        self.assertIn('#customer-legal-profiles button[data-legal-remove]', css)
        for expected in ('font-size: 17px', 'line-height: 1', 'padding: 1px 6px',
                         'width: 27px', 'height: 25px'):
            self.assertIn(expected, css)
        self.assertNotIn('[data-legal-row-summary]', js)
        self.assertIn("event.target.closest('[data-legal-remove]')", js)
        self.assertIn("button.closest('[data-legal-profile-row]').remove()", js)
        self.assertIn('hidden.value = JSON.stringify(activeProfiles())', js)
