from django.utils import timezone
from jalali_date.fields import JalaliDateTimeField, JalaliDateField
from jalali_date.widgets import AdminJalaliDateWidget

from core.forms import CustomBaseModelForm
from files.models import Image, File
from payment.models import PaymentOrder, PaymentDocument, CreditCard, GenericPaymentItem, Payment

from translator import get_text as _
from django_select2 import forms as s2forms
from django import forms



class PaymentItemFormPaymentWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "id__iexact",
    ]


class PaymentOrderModelForm(CustomBaseModelForm):
    image_groups = 1
    file_groups = 1

    class Meta:
        model = PaymentOrder
        exclude = ['group']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['request_date'] = JalaliDateField(widget=AdminJalaliDateWidget(
            attrs={'class': 'jalali_date-date underline_dash_border', 'size': '10'}), required=True)
        self.fields['payment_date'] = JalaliDateField(widget=AdminJalaliDateWidget(
            attrs={'class': 'jalali_date-date underline_dash_border', 'size': '10'}), required=False)
        self.fields['description'].widget.attrs['rows'] = 2
        self.fields['currency_type'].widget.attrs['class'] = "underline_dash_border text-center mini-select p-0"
        self.fields['currency_type'].widget.attrs['onchange'] = "change_currency_type(event)"

        self.fields['request_date'].initial = timezone.now()
        request = access = form_constraint = formset_constraint = form_constraint_read = form_constraint_hide = formset_constraint_read = formset_constraint_hide = None
        if self.form_state is None:
            if kwargs.get('initial') and (c := kwargs.get('initial').get('constraint')):
                self.form_state = c.get('form_state')
            elif kwargs.get('constraint'):
                self.form_state = kwargs.get('constraint').get('form_state')

        if self.form_state is not None:
            if self.form_state >= 1:
                self.fields['accounting'].widget.attrs['required'] = 'required'
                # self.fields['from_source'].widget.attrs['required'] = 'required'
            if self.form_state != 1:
                self.fields['from_source'].widget.attrs['readonly'] = 'readonly'
            if kwargs.get('initial') and (c := kwargs.get('initial').get('constraint')):
                form_constraint = c.pop('form_constraint')  # remove unnecessary kwargs
                formset_constraint = c.pop('formset_constraint')  # remove unnecessary kwargs
                request = c.pop('request')  # remove unnecessary kwargs
                access = c.get('wf_access')
            elif kwargs.get('constraint'):
                form_constraint = kwargs.get('constraint').get('form_constraint')
                formset_constraint = kwargs.get('constraint').get('formset_constraint')
                request = kwargs.get('constraint').get('request')
                access = kwargs.get('constraint').get('wf_access')
                kwargs.pop('constraint')  # remove unnecessary kwargs
            if form_constraint:
                form_constraint_read = form_constraint[self.form_state].get('read')
                form_constraint_hide = form_constraint[self.form_state].get('hide')
            if formset_constraint:
                formset_constraint_read = formset_constraint[self.form_state][0].get('read')
                formset_constraint_hide = formset_constraint[self.form_state][0].get('hide')

            if request and not request.user.is_superuser:
                if form_constraint_hide:
                    self.make_hidden(form_constraint_hide)
                if form_constraint_read:
                    self.make_disable(form_constraint_read)
                if formset_constraint_hide:
                    self.make_hidden(formset_constraint_hide)
                if formset_constraint_read:
                    self.make_disable(formset_constraint_read)

                if not access:
                    self.make_disable(self.fields)
                    self.enable = False


class PaymentDocumentsFormPaymentWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "id__iexact",
    ]


class PaymentDocumentsForm(CustomBaseModelForm):
    file_model = File
    file_groups = 1

    class Meta:
        model = PaymentDocument
        fields = '__all__'

        widgets = {
            'payment_order': PaymentDocumentsFormPaymentWidget,
        }

    def __init__(self, *args, **kwargs):
        access = None
        super().__init__(*args, **kwargs)
        self.fields['description'].widget.attrs['rows'] = 1
        self.fields['total_amount'] = forms.CharField(label='مجموع مبلغ')
        self.fields['total_amount'].widget.attrs['class'] = "form-control comma-seperator"
        self.fields['total_amount'].widget.attrs['dir'] = "ltr"
        self.fields['from_date'] = JalaliDateField(
            widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=False)
        self.fields['to_date'] = JalaliDateField(
            widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=False)


class CreditCardForm(CustomBaseModelForm):

    class Meta:
        model = CreditCard
        exclude = ['group']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['credit_card_number'].widget.attrs['class'] = 'form-control comma-seperator ll'


class PaymentForm(CustomBaseModelForm):
    class Meta:
        model = Payment
        exclude = ['group']

    def __init__(self, *args, **kwargs):
        request = access = form_constraint = formset_constraint = form_constraint_read = form_constraint_hide = formset_constraint_read = formset_constraint_hide = None
        if self.form_state is None:
            if kwargs.get('initial') and (c := kwargs.get('initial').get('constraint')):
                self.form_state = c.get('form_state')
            elif kwargs.get('constraint'):
                self.form_state = kwargs.get('constraint').get('form_state')

        if self.form_state is not None:
            if kwargs.get('initial') and (c := kwargs.get('initial').get('constraint')):
                form_constraint = c.pop('form_constraint')  # remove unnecessary kwargs
                formset_constraint = c.pop('formset_constraint')  # remove unnecessary kwargs
                request = c.pop('request')  # remove unnecessary kwargs
                access = c.get('wf_access')
            elif kwargs.get('constraint'):
                form_constraint = kwargs.get('constraint').get('form_constraint')
                formset_constraint = kwargs.get('constraint').get('formset_constraint')
                request = kwargs.get('constraint').get('request')
                access = kwargs.get('constraint').get('wf_access')
                kwargs.pop('constraint')  # remove unnecessary kwargs
            if form_constraint:
                form_constraint_read = form_constraint[self.form_state].get('read')
                form_constraint_hide = form_constraint[self.form_state].get('hide')
            if formset_constraint:
                formset_constraint_read = formset_constraint[self.form_state][0].get('read')
                formset_constraint_hide = formset_constraint[self.form_state][0].get('hide')
        super(PaymentForm, self).__init__(*args, **kwargs)
        self.fields['from_date'] = JalaliDateField(label=_('from_date'),
                                                   widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=True)
        self.fields['to_date'] = JalaliDateField(label=_('to_date'),
                                                   widget=AdminJalaliDateWidget(
                                                       attrs={'class': 'jalali_date-date form-control', 'size': '10'}),
                                                   required=True)
        self.fields['description'].widget.attrs['rows'] = 3

        if request and request.user.is_superuser:
            if form_constraint_hide:
                self.make_hidden(form_constraint_hide)
            if form_constraint_read:
                self.make_disable(form_constraint_read)
            if formset_constraint_hide:
                self.make_hidden(formset_constraint_hide)
            if formset_constraint_read:
                self.make_disable(formset_constraint_read)

            if not access:
                self.make_disable(self.fields)
                self.enable = False


class GenericPaymentForm(CustomBaseModelForm):
    file_model = File
    file_groups = 1
    class Meta:
        model = GenericPaymentItem
        exclude = ['group']

        # widgets = {
        #     'payment': PaymentItemFormPaymentWidget,
        # }

    def __init__(self, *args, **kwargs):
        super(GenericPaymentForm, self).__init__(*args, **kwargs)
        self.fields['description'].widget.attrs['rows'] = 3
        self.fields['g_from_date'] = JalaliDateField(label="از تاریخ",
                                                   widget=AdminJalaliDateWidget(
                                                       attrs={'class': 'jalali_date-date form-control', 'size': '10'}),
                                                   required=False)
        self.fields['g_to_date'] = JalaliDateField(label="تا تاریخ",
                                                   widget=AdminJalaliDateWidget(
                                                       attrs={'class': 'jalali_date-date form-control', 'size': '10'}),
                                                   required=False)

        self.make_hidden(['object_id', 'content_type'])

        # payment = self.initial.get('packing')
        # if payment:
        #     self.fields['payment'].queryset = self.fields['payment'].queryset.filter(id=getattr(payment, 'pk', payment))