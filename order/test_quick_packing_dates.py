"""Regression coverage: Quick Packing dates are Gregorian in the DB.

The shared CustomBaseModelForm intentionally creates JalaliDateField instances;
the override must stay isolated to PackingSafeForm.
"""
from datetime import date

from django import forms
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from jalali_date.fields import JalaliDateField

from order.forms import PackingSafeForm


class QuickPackingGregorianDateTests(SimpleTestCase):
    DATE_FIELDS = (
        'bl_date',
        'departure_date',
        'arrival_date',
        'sales_manager_check_date',
        'delivery_to_salehi_date',
        'cl_90_date',
        'cl_10_date',
        'cl_100_date',
        'arrive_to_wh_date',
        'estimated_shipping_start_date',
        'estimated_arrive_to_wh_date',
        'reserve_bar_date',
    )

    def get_form(self):
        return PackingSafeForm(
            allowed_fields=list(self.DATE_FIELDS),
            allowed_hidden=[],
            only_show=[],
        )

    def test_all_quick_packing_date_fields_use_gregorian_datefield(self):
        form = self.get_form()
        for name in self.DATE_FIELDS:
            with self.subTest(field=name):
                field = form.fields[name]
                self.assertIs(type(field), forms.DateField)
                self.assertNotIsInstance(field, JalaliDateField)
                self.assertEqual(field.input_formats, ['%Y-%m-%d'])
                # Django Input.__init__ moves attrs['type'] to input_type.
                self.assertEqual(field.widget.input_type, 'date')

    def test_gregorian_date_is_not_interpreted_as_jalali_year(self):
        field = self.get_form().fields['bl_date']
        self.assertEqual(field.clean('2026-10-25'), date(2026, 10, 25))

    def test_iso_widget_displays_correct_existing_gregorian_date(self):
        field = self.get_form().fields['estimated_shipping_start_date']
        html = field.widget.render('estimated_shipping_start_date', date(2026, 10, 25))
        self.assertIn('type="date"', html)
        self.assertIn('value="2026-10-25"', html)
        self.assertIn('data-packing-gregorian-date="1"', html)

    def test_invalid_month_day_is_rejected(self):
        field = self.get_form().fields['bl_date']
        with self.assertRaises(ValidationError):
            field.clean('2026-25-10')

    def test_jalali_text_is_not_accepted_as_gregorian_iso(self):
        field = self.get_form().fields['bl_date']
        with self.assertRaises(ValidationError):
            field.clean('1405/08/03')

    def test_implausible_year_from_legacy_wrong_conversion_is_rejected(self):
        field = self.get_form().fields['bl_date']
        with self.assertRaises(ValidationError):
            field.clean('2648-01-15')

    def test_date_field_can_be_cleared(self):
        field = self.get_form().fields['bl_date']
        self.assertIsNone(field.clean(''))
