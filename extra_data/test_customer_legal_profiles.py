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
