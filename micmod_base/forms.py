import datetime
from pprint import pprint
from typing import Dict

from django import forms
from jalali_date import datetime2jalali
from jalali_date.fields import SplitJalaliDateTimeField, JalaliDateField
from jalali_date.widgets import AdminSplitJalaliDateTime, AdminJalaliDateWidget

from accounts.mixins import FormFieldAccessMixin
from micmod_base.base import CurrencyExchange, Currency
from translator import get_text as _

from micmod_base.models import Quotation, QuotationItem
from django.forms import BaseInlineFormSet
from core.forms import CustomBaseModelForm


class QuotationForm(CustomBaseModelForm):
    form_state = None

    class Meta:
        model = Quotation
        fields = ["title", "code", "currency_ref", "status", "request_date", "expiration_date", "customer_code",
                  "customer_grade", "delivery_time", "payment_method", "market_grade", "description", "id", ]

        widgets = {
            # 'customer_code': forms.Select(
            #     attrs={"class": "select2", "id": "customer_code", "style": "width:100%", }),
            # 'customer_code': forms.TextInput(attrs={'hidden': True}),
            'description': forms.Textarea(attrs={"rows": 1}),
        }

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
            elif kwargs.get('constraint'):
                form_constraint = kwargs.get('constraint').get('form_constraint')
                formset_constraint = kwargs.get('constraint').get('formset_constraint')
                request = kwargs.get('constraint').get('request')  # remove unnecessary kwargs
                kwargs.pop('constraint')  # remove unnecessary kwargs

            form_constraint_read = form_constraint[self.form_state].get('read')
            form_constraint_hide = form_constraint[self.form_state].get('hide')
            formset_constraint_read = formset_constraint[self.form_state][0].get('read')
            formset_constraint_hide = formset_constraint[self.form_state][0].get('hide')

            # form_constraint_read = kwargs.get('form_constraint')[self.form_state].get('read')
            # form_constraint_hide = kwargs.pop('form_constraint')[self.form_state].get('hide')
            # formset_constraint_read = kwargs.get('formset_constraint')[self.form_state][0].get('read')
            # formset_constraint_hide = kwargs.pop('formset_constraint')[self.form_state][0].get('hide')

        super(QuotationForm, self).__init__(*args, **kwargs)
        self.fields['request_date'] = JalaliDateField(label=_('request_date'),
                                                      widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=True
                                                      )
        self.fields['expiration_date'] = JalaliDateField(label=_('expiration_date'),
                                                         widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=False
                                                         )

        if not request.user.is_superuser:
            if form_constraint_hide:
                self.make_hidden(form_constraint_hide)
            if form_constraint_read:
                self.make_disable(form_constraint_read)
            if formset_constraint_hide:
                self.make_hidden(formset_constraint_hide)
            if formset_constraint_read:
                self.make_disable(formset_constraint_read)
        # self.fields['request_date'].widget.attrs['class'] = 'form-control'
        # self.fields['expiration_date'].widget.attrs['class'] = 'form-control'
        # self.fields['code'].label = 'salam'
        # self.initial = {
        #     'request_date': self.data.get('request_date') if self.data.get('request_date') else datetime2jalali(
        #         datetime.datetime.now()).strftime('%Y-%m-%d'),
        #     'expiration_date': self.data.get('expiration_date') if self.data.get('expiration_date') else datetime2jalali(
        #         datetime.datetime.now() + datetime.timedelta(10)).strftime('%Y-%m-%d')
        # }

        if not self.initial.get('create') and not self.initial.get('wf_access'):
            self.make_disable(self.fields)
            self.enable = False
        self.select2(['customer_code'])


class QuotationItemForm(CustomBaseModelForm):
    def __init__(self, *args, **kwargs):
        super(QuotationItemForm, self).__init__(*args, **kwargs)
        self.fields['goods_sheet_date'] = JalaliDateField(label=_('goods_sheet_date'), required=False,
                                                          widget=forms.HiddenInput())
        self.fields['goods_market_date'] = JalaliDateField(label=_('goods_market_date'), required=False,
                                                           widget=forms.HiddenInput())
        self.fields['goods_last_sale'] = JalaliDateField(label=_('goods_last_sale'), required=False,
                                                         widget=forms.HiddenInput())
        self.fields['goods_q_last_sale'] = JalaliDateField(label=_('goods_last_sale_q'), required=False,
                                                         widget=forms.HiddenInput())
        # self.fields['goods_sheet_date'].attrs.update({'class': 'goods_sheet_date', 'disabled': True})
        # self.fields['goods_last_sale'].attrs.update({'class': 'goods_last_sale', 'disabled': True})
        # self.fields['goods_code'].label = ''
        # self.fields['goods_name'].label = ''
        # self.fields['price_method'].label = ''
        # self.fields['delivery_time'].label = ''
        # self.fields['goods_code_alt'].label = ''
        # self.fields['goods_name_alt'].label = ''
        # self.fields['goods_sheet_date'].label = ''
        # self.fields['goods_total_sales'].label = ''
        # self.fields['stock_amount'].lable = ''

        initial = self.initial.get('initial')
        if initial and not initial.get('create') and not initial.get('wf_access'):
            self.make_disable(self.fields)
            self.enable = False

        self.select2(['goods_code', 'goods_code_alt'])
        self.display_as_input(['customer_goods_name', 'customer_goods_code', 'quantity', 'goods_code', 'goods_code_alt',
                               'price_method', 'need_local_price_inquiry', 'local_price_inquiry_done'])
        self.display_as_label(['index', 'delivery_time', 'final_price', 'goods_name', 'stock_amount', 'goods_avg_price',
                               'goods_price_sheet1', 'goods_price_sheet2', 'goods_price_sheet3', 'goods_sheet_date',
                               'goods_market_date', 'goods_price_market', 'goods_avg_count', 'goods_name_alt',
                               'goods_last_sale', 'goods_last_price', 'goods_total_sales', 'stock_amount_res',
                               'goods_min_price', 'goods_max_price', 'goods_q_last_sale', 'goods_q_last_price',
                               'goods_q_total_sales', ])
        self.fields['goods_code'].html = '<div class="select2 goods_code " name="goods_code"></div>'
        self.fields['goods_code'].name = ''
        # print(type(self.fields['goods_code']))

    class Meta:
        model = QuotationItem
        fields = ['index', 'customer_goods_name', 'customer_goods_code', 'quantity',
                  'delivery_time', 'goods_code', 'goods_code_alt', 'price_method', 'final_price',
                  'goods_name', 'stock_amount', 'goods_avg_price', 'goods_price_sheet1', 'goods_price_sheet2',
                  'goods_price_sheet3',
                  'goods_sheet_date', 'goods_market_date', 'goods_price_market', 'goods_avg_count',
                  'goods_name_alt', 'goods_last_sale', 'goods_last_price', 'goods_total_sales',
                  'stock_amount_res','goods_min_price','goods_max_price',
                  'goods_q_last_sale','goods_q_last_price','goods_q_total_sales', 'need_local_price_inquiry',
                  'local_price_inquiry_done', 'need_foreign_price_inquiry','foreign_price_inquiry_done'
                  ]
        widgets = {
            'goods_code': forms.Select(
                attrs={"class": "select2 goods_code", "style": "width:100%", 'name': 'goods_code'}),
            'goods_code_alt': forms.Select(
                attrs={"class": "select2 goods_code_alt", "style": "width:100%", }),
            'customer_goods_name': forms.Textarea(attrs={'name': 'customer_goods_name', "rows": 1}),
            # 'price_method': forms.HiddenInput(),
            'price_method': forms.Select(attrs={'class': 'price_method w-100 '}),
            'final_price': forms.TextInput(attrs={'disabled': True, 'class': 'final_price w-100 text-center'}),
            # 'delivery_time': forms.TextInput(attrs={'hidden': False}),
            # 'goods_name': forms.TextInput(attrs={'hidden': False}),
            # 'stock_amount': forms.TextInput(attrs={'hidden': False}),
            # 'goods_avg_price': forms.TextInput(attrs={'hidden': False}),
            # 'goods_avg_count': forms.TextInput(attrs={'hidden': False}),
            # 'goods_price_sheet1': forms.TextInput(attrs={'hidden': False}),
            # 'goods_price_sheet2': forms.TextInput(attrs={'hidden': False}),
            # 'goods_price_sheet3': forms.TextInput(attrs={'hidden': False}),
            # 'goods_price_market': forms.TextInput(attrs={'hidden': False}),
            # # 'goods_sheet_date': forms.DateInput(attrs={'class': 'goods_sheet_date','disabled': True}),
            # 'goods_name_alt': forms.TextInput(attrs={'hidden': True}),
            # # 'goods_last_sale': forms.DateInput(attrs={'class': 'goods_last_sale','disabled': True}),
            # 'goods_last_price': forms.TextInput(attrs={'hidden': True}),
            # 'goods_total_sales': forms.TextInput(attrs={'hidden': True}),
            'goods_code': forms.HiddenInput(),
            'goods_code_alt': forms.HiddenInput(),
            'delivery_time': forms.HiddenInput(),
            'goods_name': forms.HiddenInput(),
            'stock_amount': forms.HiddenInput(),
            'stock_amount_res': forms.HiddenInput(),
            'goods_avg_price': forms.HiddenInput(),
            'goods_min_price': forms.HiddenInput(),
            'goods_max_price': forms.HiddenInput(),
            'goods_avg_count': forms.HiddenInput(),
            'goods_price_sheet1': forms.HiddenInput(),
            'goods_price_sheet2': forms.HiddenInput(),
            'goods_price_sheet3': forms.HiddenInput(),
            'goods_price_market': forms.HiddenInput(),
            # 'goods_sheet_date': forms.DateInput(attrs={'class': 'goods_sheet_date','disabled': True}),
            'goods_name_alt': forms.HiddenInput(),
            # 'goods_last_sale': forms.DateInput(attrs={'class': 'goods_last_sale','disabled': True}),
            'goods_last_price': forms.HiddenInput(),
            'goods_total_sales': forms.HiddenInput(),
            'goods_q_last_price': forms.HiddenInput(),
            'goods_q_total_sales': forms.HiddenInput(),
            # 'price_method': forms.RadioSelect(attrs={"class": "price_method","m-data":"price_method"}),
            # 'delivery_time': forms.RadioSelect(),
            # 'goods_name': forms.Textarea(attrs={'class': 'goods_name','hidden': False, "rows": 1}),
            # 'stock_amount': forms.TextInput(attrs={'class': 'stock_amount','hidden': False}),
            # 'goods_avg_price': forms.TextInput(attrs={'class': 'goods_avg_price','hidden': False}),
            # 'goods_price_sheet': forms.TextInput(attrs={'class': 'goods_price_sheet','hidden': False}),
            # # 'goods_sheet_date': forms.DateInput(attrs={'class': 'goods_sheet_date','disabled': True}),
            # 'goods_name_alt': forms.Textarea(attrs={'class': 'goods_name_alt','hidden': False, "rows": 1}),
            # # 'goods_last_sale': forms.DateInput(attrs={'class': 'goods_last_sale','disabled': True}),
            # 'goods_last_price': forms.TextInput(attrs={'class': 'goods_last_price','hidden': False}),
            # 'goods_total_sales': forms.TextInput(attrs={'class': 'goods_total_sales','hidden': True}),
            # 'final_price': forms.TextInput(attrs={'class': 'final_price','hidden': True, }),
            'quantity': forms.TextInput(attrs={'class': 'quantity  w-100', }),
        }


class QuotationItemForm2(CustomBaseModelForm, FormFieldAccessMixin):
    form_state = None

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

            form_constraint_read = form_constraint[self.form_state].get('read')
            form_constraint_hide = form_constraint[self.form_state].get('hide')
            formset_constraint_read = formset_constraint[self.form_state][0].get('read')
            formset_constraint_hide = formset_constraint[self.form_state][0].get('hide')

        # if kwargs.get('request'):
        #     request = kwargs.pop('request')

        super(QuotationItemForm2, self).__init__(*args, **kwargs)
        self.fields['goods_sheet_date'] = JalaliDateField(label=_('goods_sheet_date'), required=False,
                                                          widget=forms.HiddenInput())
        self.fields['goods_market_date'] = JalaliDateField(label=_('goods_market_date'), required=False,
                                                           widget=forms.HiddenInput())
        self.fields['goods_last_sale'] = JalaliDateField(label=_('goods_last_sale'), required=False,
                                                         widget=forms.HiddenInput())
        self.fields['goods_q_last_sale'] = JalaliDateField(label=_('goods_last_sale_q'), required=False,
                                                           widget=forms.HiddenInput())

        if not request.user.is_superuser:
            if form_constraint_hide:
                self.make_hidden(form_constraint_hide)
            if form_constraint_read:
                self.make_disable(form_constraint_read)
            if formset_constraint_hide:
                self.make_hidden(formset_constraint_hide)
            if formset_constraint_read:
                self.make_disable(formset_constraint_read)

        initial = kwargs.get('initial')
        if not access:
            self.fields['goods_code'] = forms.CharField(widget=forms.TextInput(
                attrs={"class": "form-control select2-selection__rendered", "style": "width:100%", 'name': '-goods_name_lbl'}
            ))
            self.fields['goods_code_alt'] = forms.CharField(widget=forms.TextInput(
                attrs={"class": "form-control ", "style": "width:100%", 'name': '-goods_name_lbl'}
            ))
            self.make_disable(self.fields)
            self.enable = False

        main_initial = self.initial.get('initial')

        self.select2(['goods_code', 'goods_code_alt', 'goods_name_alt'])
        self.display_as_input(['customer_goods_name', 'customer_goods_code', 'quantity', 'goods_code', 'goods_code_alt',
                               'price_method', 'need_foreign_price_inquiry', 'foreign_price_inquiry_done'])
        self.display_as_label(['index', 'delivery_time', 'final_price', 'goods_name', 'stock_amount', 'goods_avg_price',
                               'goods_price_sheet1', 'goods_price_sheet2', 'goods_price_sheet3', 'goods_sheet_date',
                               'goods_market_date', 'goods_price_market', 'goods_avg_count', 'goods_name_alt',
                               'goods_last_sale', 'goods_last_price', 'goods_total_sales', 'stock_amount_res',
                               'goods_min_price', 'goods_max_price', 'goods_q_last_sale', 'goods_q_last_price',
                               'goods_q_total_sales', ])

        self.fields['goods_code'].name = 'goods_code'
        self.fields['quantity'].widget.attrs['class'] += ' quantity comma-seperator  w-100'
        self.fields['final_price'].widget.attrs['class'] += ' replace-digits'

    class Meta:
        model = QuotationItem
        localized_fields = '__all__'
        fields = ['index', 'customer_goods_name', 'customer_goods_code', 'quantity',
                  'delivery_time', 'goods_code', 'goods_code_alt', 'price_method', 'final_price',
                  'goods_name', 'stock_amount', 'goods_avg_price', 'goods_price_sheet1', 'goods_price_sheet2',
                  'goods_price_sheet3',
                  'goods_sheet_date', 'goods_market_date', 'goods_price_market', 'goods_avg_count',
                  'goods_name_alt', 'goods_last_sale', 'goods_last_price', 'goods_total_sales',
                  'stock_amount_res', 'goods_min_price', 'goods_max_price',
                  'goods_q_last_sale', 'goods_q_last_price', 'goods_q_total_sales', 'local_price_inquiry_done',
                  'need_local_price_inquiry', 'foreign_price_inquiry_done', 'need_foreign_price_inquiry'
                  ]
        # exclude = ['quotation', 'created_date', 'last_update_date', 'editor_user']
        widgets = {
            'goods_code': forms.Select(
                attrs={"class": "select2 goods_code", "style": "width:100%", 'name': 'goods_code'}),
            'goods_code_alt': forms.Select(
                attrs={"class": "select2 goods_code_alt", "style": "width:100%", }),
            'customer_goods_name': forms.Textarea(attrs={'name': 'customer_goods_name', "rows": 1}),
            # 'price_method': forms.HiddenInput(),
            'price_method': forms.Select(attrs={'class': 'price_method w-100 '}),
            'final_price': forms.TextInput(attrs={'disabled': True, 'class': 'final_price w-100 text-center'}),
            # 'delivery_time': forms.TextInput(attrs={'hidden': False}),
            # 'goods_name': forms.TextInput(attrs={'hidden': False}),
            # 'stock_amount': forms.TextInput(attrs={'hidden': False}),
            # 'goods_avg_price': forms.TextInput(attrs={'hidden': False}),
            # 'goods_avg_count': forms.TextInput(attrs={'hidden': False}),
            # 'goods_price_sheet1': forms.TextInput(attrs={'hidden': False}),
            # 'goods_price_sheet2': forms.TextInput(attrs={'hidden': False}),
            # 'goods_price_sheet3': forms.TextInput(attrs={'hidden': False}),
            # 'goods_price_market': forms.TextInput(attrs={'hidden': False}),
            # # 'goods_sheet_date': forms.DateInput(attrs={'class': 'goods_sheet_date','disabled': True}),
            # 'goods_name_alt': forms.TextInput(attrs={'hidden': True}),
            # # 'goods_last_sale': forms.DateInput(attrs={'class': 'goods_last_sale','disabled': True}),
            # 'goods_last_price': forms.TextInput(attrs={'hidden': True}),
            # 'goods_total_sales': forms.TextInput(attrs={'hidden': True}),
            'goods_code': forms.HiddenInput(),
            'goods_code_alt': forms.HiddenInput(),
            'delivery_time': forms.HiddenInput(),
            'goods_name': forms.HiddenInput(),
            'stock_amount': forms.HiddenInput(),
            'stock_amount_res': forms.HiddenInput(),
            'goods_avg_price': forms.HiddenInput(),
            'goods_min_price': forms.HiddenInput(),
            'goods_max_price': forms.HiddenInput(),
            'goods_avg_count': forms.HiddenInput(),
            'goods_price_sheet1': forms.HiddenInput(),
            'goods_price_sheet2': forms.HiddenInput(),
            'goods_price_sheet3': forms.HiddenInput(),
            'goods_price_market': forms.HiddenInput(),
            # 'goods_sheet_date': forms.DateInput(attrs={'class': 'goods_sheet_date','disabled': True}),
            'goods_name_alt': forms.HiddenInput(),
            # 'goods_last_sale': forms.DateInput(attrs={'class': 'goods_last_sale','disabled': True}),
            'goods_last_price': forms.HiddenInput(),
            'goods_total_sales': forms.HiddenInput(),
            'goods_q_last_price': forms.HiddenInput(),
            'goods_q_total_sales': forms.HiddenInput(),
            # 'price_method': forms.RadioSelect(attrs={"class": "price_method","m-data":"price_method"}),
            # 'delivery_time': forms.RadioSelect(),
            # 'goods_name': forms.Textarea(attrs={'class': 'goods_name','hidden': False, "rows": 1}),
            # 'stock_amount': forms.TextInput(attrs={'class': 'stock_amount','hidden': False}),
            # 'goods_avg_price': forms.TextInput(attrs={'class': 'goods_avg_price','hidden': False}),
            # 'goods_price_sheet': forms.TextInput(attrs={'class': 'goods_price_sheet','hidden': False}),
            # # 'goods_sheet_date': forms.DateInput(attrs={'class': 'goods_sheet_date','disabled': True}),
            # 'goods_name_alt': forms.Textarea(attrs={'class': 'goods_name_alt','hidden': False, "rows": 1}),
            # # 'goods_last_sale': forms.DateInput(attrs={'class': 'goods_last_sale','disabled': True}),
            # 'goods_last_price': forms.TextInput(attrs={'class': 'goods_last_price','hidden': False}),
            # 'goods_total_sales': forms.TextInput(attrs={'class': 'goods_total_sales','hidden': True}),
            # 'final_price': forms.TextInput(attrs={'class': 'final_price','hidden': True, }),
            'quantity': forms.TextInput(attrs={'class': 'quantity comma-seperator  w-100',
                                               }),
        }


class CurrencyExchangeForm(CustomBaseModelForm):
    def __init__(self, *args, **kwargs):
        super(CurrencyExchangeForm, self).__init__(*args, **kwargs)
        self.fields['currency'] = forms.ModelChoiceField(
            queryset=Currency.objects.all(),
            initial=2,
        )
        self.fields['currency'].widget.attrs['class'] = 'form-control'

    class Meta:
        model = CurrencyExchange
        fields = ['currency', 'buy_exchange', 'sell_exchange']
