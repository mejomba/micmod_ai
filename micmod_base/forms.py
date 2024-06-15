import datetime
from pprint import pprint
from typing import Dict

from django import forms
from django.contrib.auth import get_user_model
from jalali_date import datetime2jalali
from jalali_date.fields import SplitJalaliDateTimeField, JalaliDateField
from jalali_date.widgets import AdminSplitJalaliDateTime, AdminJalaliDateWidget

from accounts.mixins import FormFieldAccessMixin
from inquiry.forms import InquiryResultForm
from inquiry.models import InquiryResult, PriceInquiryResult
from micmod_base.base import CurrencyExchange, Currency
from translator import get_text as _

from micmod_base.models import Quotation, QuotationItem
from django.forms import BaseInlineFormSet, inlineformset_factory
from core.forms import CustomBaseModelForm, CustomBaseForm
import json


class QuotationForm(CustomBaseModelForm):
    form_state = None
    has_comment = True
    has_addition = True

    class Meta:
        model = Quotation
        fields = ["title", "code", "currency_ref", "status", "request_date", "expiration_date", "customer_code",
                  "customer_party_id", "customer_grade", "delivery_time", "payment_method", "market_grade",
                  "description", "id", 'sepidar_number', 'self_discount', 'addition', 'duty', 'tax',
                  "is_official", "official_value", 'cancel', 'force_inquiry', 'sale_type']

        widgets = {
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
                access = c.pop('wf_access')
                form_constraint = c.pop('form_constraint')  # remove unnecessary kwargs
                formset_constraint = c.pop('formset_constraint')  # remove unnecessary kwargs
                request = c.pop('request')  # remove unnecessary kwargs
            elif kwargs.get('constraint'):
                access = kwargs.get('constraint').get('wf_access')
                form_constraint = kwargs.get('constraint').get('form_constraint')
                formset_constraint = kwargs.get('constraint').get('formset_constraint')
                request = kwargs.get('constraint').get('request')  # remove unnecessary kwargs
                kwargs.pop('constraint')  # remove unnecessary kwargs


            if form_constraint:
                form_constraint_read = form_constraint[self.form_state].get('read')
                form_constraint_hide = form_constraint[self.form_state].get('hide')
            if formset_constraint:
                formset_constraint_read = formset_constraint[self.form_state][0].get('read')
                formset_constraint_hide = formset_constraint[self.form_state][0].get('hide')

        super(QuotationForm, self).__init__(*args, **kwargs)
        self.fields['request_date'] = JalaliDateField(label=_('request_date'),
                                                      widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=True
                                                      )
        self.fields['expiration_date'] = JalaliDateField(label=_('expiration_date'),
                                                         widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=True
                                                         )
        self.fields['cancel'].widget = forms.HiddenInput()

        # if self.has_addition:
        #     self.fields['addition_currency'] = forms.ModelChoiceField(queryset=Currency.objects.all(), widget=forms.Select(attrs={'class': 'form-control mb-3 ', 'placeholder': 'نوع ارز', 'id': 'id_addition_currency'}), required=False)
        #     self.fields['addition_title'] = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control mb-3 ', 'placeholder': 'عنوان'}))
        #     self.fields['addition_description'] = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control mb-3 ','placeholder': 'توضیحات خود را بنویسید :)'}))
        #     self.fields['addition_count'] = forms.IntegerField(widget=forms.TextInput(attrs={'class': 'form-control mb-3', 'placeholder': 'تعداد'}))

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
                self.fields['customer_code'] = forms.CharField(widget=forms.TextInput(
                    attrs={'class': 'form-control select2-selection__rendered',
                           "style": "width:100%", 'name': 'customer_code'}
                ))
                self.make_disable(self.fields)
                self.enable = False
            if self.instance and self.instance.cancel:
                self.make_disable(self.fields)

        if not self.initial.get('create') and not self.initial.get('wf_access'):
            ...
            # self.make_disable(self.fields)
            # self.enable = False
        self.select2(['customer_code'])
        self.make_hidden(['customer_party_id'])
        self.make_disable(['sepidar_number'])
        self.fields['currency_ref'].widget.attrs['onchange'] = 'refresh_prices()'
        self.fields['currency_ref'].widget.attrs['onchange'] = 'refresh_prices()'
        self.fields['payment_method'].widget.attrs['onchange'] = 'refresh_prices()'
        self.fields['customer_grade'].widget.attrs['onchange'] = 'refresh_prices()'
        self.fields['is_official'].widget.attrs['onchange'] = 'refresh_prices()'
        self.fields['official_value'].widget.attrs['onchange'] = 'refresh_prices()'
        self.fields['self_discount'].widget.attrs['onchange'] = 'refresh_prices()'
        # self.fields['customer_code'].widget.attrs['onchange'] = 'refresh_prices()'


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
                  'local_price_inquiry_done', 'need_foreign_price_inquiry','foreign_price_inquiry_done',
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
            # 'final_price': forms.HiddenInput(),
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
            if form_constraint:
                form_constraint_read = form_constraint[self.form_state].get('read')
                form_constraint_hide = form_constraint[self.form_state].get('hide')
            if formset_constraint:
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


        # if self.instance.trade_price_code:
        self.fields['trade_price_code'] = forms.ModelChoiceField(widget=forms.Select(attrs={'class': 'mb-1 w-100 form-control'}),
                                                                     queryset=PriceInquiryResult.inquiry_list_datatable(request.user, {'sku': self.instance.goods_code,'inquiry_type__base_group': 'trade'}) if self.instance.goods_code else PriceInquiryResult.objects.none(),
                                                                     initial=(self.instance.trade_price_code,
                                                                              self.instance.trade_price_code) if self.instance.trade_price_code else None
                                                                     )
        # else:
        #     self.fields['trade_price_code'] = forms.ModelChoiceField(widget=forms.Select(attrs={'class': 'mb-1 w-100'}),
        #                                                              queryset=PriceInquiryResult.inquiry_list_datatable(
        #                                                                  request.user, {
        #                                                                      'sku': self.instance.goods_code}) if self.instance.goods_code else PriceInquiryResult.objects.none(),
        #                                                              )
        # if self.instance.bazar_price_code:
        self.fields['bazar_price_code'] = forms.ModelChoiceField(widget=forms.Select(attrs={'class': 'w-100 form-control'}),
                                                                     queryset=PriceInquiryResult.inquiry_list_datatable(request.user, {'sku': self.instance.goods_code,'inquiry_type__base_group': 'bazar'}) if self.instance.goods_code else PriceInquiryResult.objects.none(),
                                                                     initial=(self.instance.bazar_price_code,
                                                                              self.instance.bazar_price_code) if self.instance.bazar_price_code else None,
                                                                     )
        # else:
        #     self.fields['bazar_price_code'] = forms.ModelChoiceField(widget=forms.Select(attrs={'class': 'w-100'}),
        #                                                              queryset=PriceInquiryResult.inquiry_list_datatable(
        #                                                                  request.user, {
        #                                                                      'sku': self.instance.goods_code}) if self.instance.goods_code else PriceInquiryResult.objects.none(),
        #                                                              initial=0
        #                                                              )
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
                self.fields['goods_code'] = forms.CharField(widget=forms.TextInput(
                    attrs={"class": "form-control select2-selection__rendered", "style": "width:100%", 'name': '-goods_name_lbl'}
                ))
                self.fields['goods_code_alt'] = forms.CharField(widget=forms.TextInput(
                    attrs={"class": "form-control ", "style": "width:100%", 'name': '-goods_name_lbl'}
                ))
                self.make_disable(self.fields)
                self.enable = False
            if self.instance and getattr(self.instance, 'quotation', None) and getattr(self.instance.quotation, 'cancel', None):
                self.make_disable(self.fields)


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
        self.fields['final_price'].widget.attrs['class'] += ' replace-digits bold text-black'

        self.make_optional(['bazar_price_code', 'trade_price_code'])
        # if not request.user.is_superuser and kwargs.get('instance') and kwargs.get('instance').quotation.workflows.last() and not kwargs.get('instance').quotation.workflows.last().to_user == request.user:
        user_groups = request.user.groups.values_list('name', flat=True) if request else None
        if request and not request.user.is_superuser:
            if 'trade_user' not in user_groups:
                self.make_disable(['foreign_price_inquiry_done', 'lead_time']) # 'trade_price_code',
            if 'bazar_user' not in user_groups:
                self.make_disable(['local_price_inquiry_done', ]) #'bazar_price_code'
        try:
            x = get_user_model().objects.filter(groups__name__in=['trade_user', 'trade_admin'])
            self.fields['assigned_trade_user'].queryset = x.distinct() if x else None
            self.fields['assigned_trade_user2'].queryset = x.distinct() if x else None

            self.fields['assigned_trade_user'].widget.attrs['onchange'] = "post_ajax_data(event)"
            self.fields['assigned_trade_user'].widget.attrs[
                'url'] = f'/core/ajax/micmod_base/quotationitem/up_create?pk={self.instance.pk}'
            self.fields['assigned_trade_user2'].widget.attrs['onchange'] = "post_ajax_data(event)"
            self.fields['assigned_trade_user2'].widget.attrs[
                'url'] = f'/core/ajax/micmod_base/quotationitem/up_create?pk={self.instance.pk}'

            self.fields['task_start'].widget.attrs['onchange'] = "post_ajax_data(event)"
            self.fields['task_start'].widget.attrs[
                'url'] = f'/core/ajax/micmod_base/quotationitem/up_create?pk={self.instance.pk}'
            self.fields['task_start2'].widget.attrs['onchange'] = "post_ajax_data(event)"
            self.fields['task_start2'].widget.attrs[
                'url'] = f'/core/ajax/micmod_base/quotationitem/up_create?pk={self.instance.pk}'

        except Exception as e:
            pass

    class Meta:
        model = QuotationItem
        localized_fields = '__all__'
        fields = ['index', 'customer_goods_name', 'customer_goods_code', 'quantity', 'itemid',
                  'delivery_time', 'goods_code', 'goods_code_alt', 'price_method', 'final_price',
                  'goods_name', 'stock_amount', 'goods_avg_price', 'goods_price_sheet1', 'goods_price_sheet2',
                  'goods_price_sheet3',
                  'goods_sheet_date', 'goods_market_date', 'goods_price_market', 'goods_avg_count',
                  'goods_name_alt', 'goods_last_sale', 'goods_last_price', 'goods_total_sales',
                  'stock_amount_res', 'goods_min_price', 'goods_max_price', 'trade_price_code', 'bazar_price_code',
                  'goods_q_last_sale', 'goods_q_last_price', 'goods_q_total_sales', 'local_price_inquiry_done',
                  'need_local_price_inquiry', 'foreign_price_inquiry_done', 'need_foreign_price_inquiry', 'description',
                  'assigned_trade_user', 'lead_time', 'assigned_trade_user2', 'task_start', 'task_start2',
                  'task_start_date', 'task_start_date2', 'has_delay', 'delay_reason', 'delay_time', 'item_in_china',
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
            # 'final_price': forms.HiddenInput(),
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
            'itemid': forms.HiddenInput(),
            'bazar_price_code': forms.HiddenInput(),
            'trade_price_code': forms.HiddenInput(),
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


iqr_fields = [
    "goods_price_market",
    "goods_market_date",
    "goods_avg_price",
    "goods_min_price",
    "goods_max_price",
    "goods_last_sale",
    "goods_total_sales",
    "goods_last_price",
    "goods_q_last_sale",
    "goods_q_total_sales",
    "goods_q_last_price",
    "stock_amount",
    "stock_amount_res",
    "express_transportation_cost_1",
    "air_transportation_cost_1",
    "sea_transportation_cost_1",
    "express_transportation_cost_2",
    "air_transportation_cost_2",
    "sea_transportation_cost_2",
    "express_transportation_cost_3",
    "air_transportation_cost_3",
    "sea_transportation_cost_3",
    "quotation_item",
    "price_settings",
    "price_update_date",
]
InquiryResultFormset = inlineformset_factory(QuotationItem, InquiryResult, form=InquiryResultForm, extra=1, fields=iqr_fields)


class BaseQIFormset(BaseInlineFormSet):
    def add_fields(self, form, index):
        x = super(BaseQIFormset, self).add_fields(form, index)

        form.nested = InquiryResultFormset(
                        instance=form.instance,
                        data=form.data if form.is_bound else None,
                        files=form.files if form.is_bound else None,
                        prefix='qir-%s-%s' % (
                            form.prefix,
                            InquiryResultFormset.get_default_prefix()),
                        )
        print('new form nested: ===== ', index)

    def is_valid(self):
        result = super(BaseQIFormset, self).is_valid()

        if self.is_bound:
            for form in self.forms:
                if hasattr(form, 'nested'):
                    # Todo use and
                    nv = form.nested.is_valid()
                    result = result and nv

        return result

    def save(self, commit=True, request=None, related_name_fk=None):
        # result = super(BaseQIFormset, self).save(commit=commit)
        result = []

        idx = 0
        for form in self.forms:
            form.instance.extra_data.request = request
            if 'DELETE' in form.changed_data and form.cleaned_data['DELETE']:
                if form.instance.pk:
                    form.instance.delete()
                    obj = None
                else:
                    # Don't save form
                    obj = None
            else:
                obj = form.save(commit=commit)
            if not obj:
                continue
            result.append(obj)
            qi_instance = form.instance
            # if form.changed_data and hasattr(form, 'nested') and not self._should_delete_form(form):
            if any([f.changed_data for f in form.nested.forms]) and hasattr(form, 'nested') and not self._should_delete_form(form):
                for form_n in form.nested.forms:
                    form_n.instance.extra_data.request = request
                    form_n.instance.result_parameter = json.dumps({
                        # 'currency_ref': result[idx].quotation.currency_ref.pk,
                        # 'payment_method': result[idx].quotation.payment_method,
                        # 'quantity': result[idx].quantity,
                        # 'customer_grade': result[idx].quotation.customer_grade,
                        # 'customer_code': result[idx].quotation.customer_code
                        'currency_ref': qi_instance.quotation.currency_ref.pk,
                        'payment_method': qi_instance.quotation.payment_method,
                        'quantity': qi_instance.quantity,
                        'customer_grade': qi_instance.quotation.customer_grade,
                        'customer_code': qi_instance.quotation.customer_code
                    })
                    form_n.save(commit=commit)

        return result


qi_fields = [
    'index', 'customer_goods_name', 'customer_goods_code', 'quantity', 'itemid',
    'delivery_time', 'goods_code', 'goods_code_alt', 'price_method',
    'goods_name', 'stock_amount', 'goods_avg_price', 'goods_price_sheet1', 'goods_price_sheet2',
    'goods_price_sheet3', 'final_price',
    'goods_sheet_date', 'goods_market_date', 'goods_price_market', 'goods_avg_count',
    'goods_name_alt', 'goods_last_sale', 'goods_last_price', 'goods_total_sales',
    'stock_amount_res', 'goods_min_price', 'goods_max_price',
    'goods_q_last_sale', 'goods_q_last_price', 'goods_q_total_sales', 'need_local_price_inquiry',
    'local_price_inquiry_done', 'need_foreign_price_inquiry', 'foreign_price_inquiry_done', 'description', 'item_in_china'
    ]


QuotationItemFormset = inlineformset_factory(
    Quotation,
    QuotationItem,
    formset=BaseQIFormset,
    form=QuotationItemForm2,
    extra=1,
    fields=qi_fields,
)


class PendingFormFilter(CustomBaseForm):
    from django.db.models.fields import BLANK_CHOICE_DASH
    CHOOSE_CHOICES = [
                      # ('time', _('time')),
                      ('my_quotations', _('my_quotations')),
                      ('quotation', _('quotation')),
                      ('customer_code', _('customer_code')),
                      ('search_sku', _('goods_code')),
                      ('my_inquiry_not_started', _('my_inquiry_not_started')),
                      ('inquiry_not_assigned', _('inquiry_not_assigned')),
                      ('force_inquiry', _('force_inquiry')),
                      # ('search_part_number', _('part_number')),
                      # ('search_customer_name', _('customer_name')),
                      # ('search_create_date', _('create_date')),
                      ('all', _('all'))
                        ]
    choice = forms.ChoiceField(choices=BLANK_CHOICE_DASH + CHOOSE_CHOICES)
    # from_time = forms.DateTimeField(required=False)
    # to_time = forms.DateTimeField(required=False)
    quotation = forms.IntegerField(required=False)
    customer_code = forms.IntegerField(required=False)
    my_quotations = forms.CharField(required=False)
    search_sku = forms.CharField(required=False)
    my_inquiry_not_started = forms.CharField(required=False)
    inquiry_not_assigned = forms.CharField(required=False)
    force_inquiry = forms.CharField(required=False)
    # search_part_number = forms.CharField(required=False)
    # search_customer_name = forms.CharField(required=False)
    # search_create_date = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super(PendingFormFilter, self).__init__(*args, **kwargs)
        self.fields['choice'].widget.attrs.update()
        # self.fields['from_time'].widget.attrs.update({'class': 'd-none form-control', 'placeholder': _('from_time')})
        # self.fields['to_time'].widget.attrs.update({'class': 'd-none form-control', 'placeholder': _('to_time')})
        self.fields['quotation'].widget.attrs.update({'class': 'd-none form-control', 'placeholder': _('quotation')})
        self.fields['customer_code'].widget.attrs.update({'class': 'd-none form-control', 'placeholder': _('customer_code')})
        self.fields['my_quotations'].widget.attrs.update({'class': 'd-none form-control', 'placeholder': _('my_quotations')})
        self.fields['search_sku'].widget.attrs.update({'class': 'd-none form-control', 'placeholder': _('goods_code')})
        self.fields['my_inquiry_not_started'].widget.attrs.update({'class': 'd-none form-control', 'placeholder': _('my_inquiry_not_started')})
        self.fields['inquiry_not_assigned'].widget.attrs.update({'class': 'd-none form-control', 'placeholder': _('inquiry_not_assigned')})
        self.fields['force_inquiry'].widget.attrs.update({'class': 'd-none form-control', 'placeholder': _('force_inquiry')})
        # self.fields['search_part_number'].widget.attrs.update({'class': 'd-none form-control', 'placeholder': _('search_part_number')})
        # self.fields['search_customer_name'].widget.attrs.update({'class': 'd-none form-control', 'placeholder': _('goods_code')})
        # self.fields['search_create_date'].widget.attrs.update({'class': 'd-none form-control', 'placeholder': _('goods_code')})

