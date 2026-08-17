from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from jalali_date.fields import JalaliDateField
from jalali_date.widgets import AdminJalaliDateWidget

from accounts.mixins import FormFieldAccessMixin
from extra_data.models import PriceSettings
from inquiry.forms import InquiryResultForm
from inquiry.models import InquiryResult, PriceInquiryResult
from micmod_base.base import CurrencyExchange, Currency
from translator import get_text as _

from micmod_base.models import Quotation, QuotationItem, CustomerRequest, CustomerRequestItem
from django.forms import BaseInlineFormSet, inlineformset_factory
from core.forms import CustomBaseModelForm, CustomBaseForm
import json

from transportation.models import TradeTransportationMethod


class QuotationForm(CustomBaseModelForm):
    form_state = None
    has_comment = True
    has_addition = True

    class Meta:
        model = Quotation
        fields = ["title", "code", "currency_ref", "status", "request_date", "expiration_date", "customer_code",
                  "customer_party_id", "customer_grade", "delivery_time", "payment_method", "market_grade",
                  "description", "id", 'sepidar_number', 'self_discount', 'addition', 'duty', 'tax',
                  "is_official", "official_value", 'cancel', 'force_inquiry', 'sale_type', 'is_direct',
                  'sales_admin_confirm', 'description_sales', 'customer_request', 'q_price_setting', 'can_observe',
                  'notify_number', "prepayment"]

        widgets = {
            'description': forms.Textarea(attrs={"rows": 1}),
            'description_sales': forms.Textarea(attrs={"rows": 1}),
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

            # if form_constraint:
            #     for item in form_constraint[self.form_state]:
            #         if item.get('group') in request.user.groups.values_list('name', flat=True):
            #             form_constraint_read = item.get('read')  # form_constraint[self.form_state].get('read')
            #             form_constraint_hide = item.get('hide')  # orm_constraint[self.form_state].get('hide')
            # if formset_constraint:
            #     for item in formset_constraint[self.form_state]:
            #         if item.get('group') in request.user.groups.values_list('name', flat=True):
            #             formset_constraint_read = item.get('read')  # formset_constraint[self.form_state][0].get('read')
            #             formset_constraint_hide = item.get('hide')  # formset_constraint[self.form_state][0].get('hide')

            if form_constraint:
                if isinstance(form_constraint[self.form_state], list):
                    for item in form_constraint[self.form_state]:
                        if item.get('group') in request.user.groups.values_list('name', flat=True):
                            form_constraint_read = item.get('read')  # form_constraint[self.form_state].get('read')
                            form_constraint_hide = item.get('hide')  # orm_constraint[self.form_state].get('hide')
                else:
                    form_constraint_read = form_constraint[self.form_state].get('read')
                    form_constraint_hide = form_constraint[self.form_state].get('hide')
            if formset_constraint:
                if isinstance(formset_constraint[self.form_state], list):
                    for item in formset_constraint[self.form_state]:
                        if item.get('group') in request.user.groups.values_list('name', flat=True):
                            formset_constraint_read = item.get('read')  # formset_constraint[self.form_state][0].get('read')
                            formset_constraint_hide = item.get('hide')  # formset_constraint[self.form_state][0].get('hide')
                else:
                    formset_constraint_read = formset_constraint[self.form_state][0].get('read')
                    formset_constraint_hide = formset_constraint[self.form_state][0].get('hide')

        super(QuotationForm, self).__init__(*args, **kwargs)
        ps = PriceSettings.objects.none()
        if request:
            for user_group in request.user.groups.values_list('name', flat=True):
                ps |= PriceSettings.objects.filter(Q(permission_json__group__icontains=user_group))
            ps |= PriceSettings.objects.filter(
                Q(permission_json__user__icontains='all') | Q(permission_json__user__icontains=request.user.username))

        self.fields['q_price_setting'] = forms.ModelChoiceField(widget=forms.Select(attrs={'class': 'mb-1 w-100 form-control'}), queryset=ps, required=False)
        self.fields['q_price_setting'].widget.attrs['onchange'] = 'refresh_prices()'

        self.fields['request_date'] = JalaliDateField(label=_('request_date'),
                                                      widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=True
                                                      )
        self.fields['expiration_date'] = JalaliDateField(label=_('expiration_date'),
                                                         widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=True
                                                         )
        self.fields['cancel'].widget = forms.HiddenInput()

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

        self.select2(['customer_code'])
        self.make_hidden(['customer_party_id'])
        self.make_disable(['sepidar_number'])
        self.fields['currency_ref'].widget.attrs['onchange'] = 'refresh_prices()'
        self.fields['currency_ref'].widget.attrs['onchange'] = 'refresh_prices()'
        self.fields['payment_method'].widget.attrs['onchange'] = 'refresh_prices()'
        self.fields['customer_grade'].widget.attrs['onchange'] = 'refresh_prices()'
        self.fields['is_official'].widget.attrs['onchange'] = 'refresh_front_prices()'  # 'refresh_prices()'
        self.fields['official_value'].widget.attrs['onchange'] = 'refresh_front_prices()'  # 'refresh_prices()'
        self.fields['official_value'].widget.attrs['required'] = 'required'
        self.fields['self_discount'].widget.attrs['onchange'] = 'refresh_front_prices()'  # 'refresh_prices()'
        self.fields.pop('customer_request', None)
        self.fields.pop('shop_document_id', None)
        self.fields.pop('shop_payment_id', None)
        self.fields.pop('payment_status', None)


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
                if isinstance(form_constraint[self.form_state], list):
                    for item in formset_constraint[self.form_state]:
                        if item.get('group') in request.user.groups.values_list('name', flat=True):
                            formset_constraint_read = item.get('read')  # formset_constraint[self.form_state][0].get('read')
                            formset_constraint_hide = item.get('hide')  # formset_constraint[self.form_state][0].get('hide')
                else:
                    form_constraint_read = form_constraint[self.form_state].get('read')
                    form_constraint_hide = form_constraint[self.form_state].get('hide')
            if formset_constraint:
                if isinstance(formset_constraint[self.form_state], list):
                    for item in formset_constraint[self.form_state]:
                        if item.get('group') in request.user.groups.values_list('name', flat=True):
                            formset_constraint_read = item.get(
                                'read')  # formset_constraint[self.form_state][0].get('read')
                            formset_constraint_hide = item.get(
                                'hide')  # formset_constraint[self.form_state][0].get('hide')
                else:
                    formset_constraint_read = formset_constraint[self.form_state][0].get('read')
                    formset_constraint_hide = formset_constraint[self.form_state][0].get('hide')

        super(QuotationItemForm2, self).__init__(*args, **kwargs)
        self.fields['goods_sheet_date'] = JalaliDateField(label=_('goods_sheet_date'), required=False,
                                                          widget=forms.HiddenInput())
        self.fields['goods_market_date'] = JalaliDateField(label=_('goods_market_date'), required=False,
                                                           widget=forms.HiddenInput())
        self.fields['goods_last_sale'] = JalaliDateField(label=_('goods_last_sale'), required=False,
                                                         widget=forms.HiddenInput())
        self.fields['goods_q_last_sale'] = JalaliDateField(label=_('goods_last_sale_q'), required=False,
                                                           widget=forms.HiddenInput())
        self.fields['discount_per_item'].widget.attrs['onchange'] = 'refresh_front_prices()'
        self.fields['quantity'].widget.attrs['onkeyup'] = 'setPriceWithAjax(event)'
        self.fields['sales_description'].widget.attrs.update({'class': 'w-100 narrow-input', 'placeholder': "توضیحات فروش برای مشتری (تا 255 کاراکتر)"})
        self.fields['supply_date'] = JalaliDateField(label=_('request_date'),
                                                      widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date w-100 narrow-input', 'placeholder': "زمان تعهد"}), required=False
                                                      )

        self.fields['trade_price_code'] = forms.ModelChoiceField(widget=forms.Select(attrs={'class': 'mb-1 w-100 form-control'}),
                                                                     queryset=PriceInquiryResult.inquiry_list(request.user, {'sku': self.instance.goods_code,'inquiry_type__base_group': 'trade'}) if self.instance.goods_code else PriceInquiryResult.objects.none(),
                                                                     initial=self.instance.trade_price_code if self.instance.trade_price_code else None
                                                                     )
        self.fields['bazar_price_code'] = forms.ModelChoiceField(widget=forms.Select(attrs={'class': 'w-100 form-control'}),
                                                                     queryset=PriceInquiryResult.inquiry_list(request.user, {'sku': self.instance.goods_code,'inquiry_type__base_group': 'bazar'}) if self.instance.goods_code else PriceInquiryResult.objects.none(),
                                                                     initial=self.instance.bazar_price_code if self.instance.bazar_price_code else None,
                                                                     )
        self.fields['customer_goods_name'].widget.attrs['onchange'] = 'customerItem(event)'
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
                m_fields = self.fields.copy()
                m_fields.pop('trade_price_code')
                m_fields.pop('bazar_price_code')
                self.make_disable(m_fields)

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
        self.fields['final_price'].widget.attrs['class'] += ' replace-digits bold text-black s-0 comma-seperator'
        # self.fields['final_price'].widget.attrs['onkeyup'] = "formatNumber(event)"

        self.make_optional(['bazar_price_code', 'trade_price_code'])
        self.make_required(['quantity'])
        user_groups = request.user.groups.values_list('name', flat=True) if request else None
        if request and not request.user.is_superuser:
            if 'trade_user' not in user_groups:
                self.make_disable(['foreign_price_inquiry_done', 'lead_time']) # 'trade_price_code',
            if 'bazar_user' not in user_groups:
                self.make_disable(['local_price_inquiry_done', ]) #'bazar_price_code'
            if request.user.base_group == 'sales':
                self.fields.pop('foreign_price_inquiry_done_date', None)
                self.fields.pop('local_price_inquiry_done_date', None)
            # if get_user_model().objects.filter(pk=request.user.pk, groups__name='sales_admin').exists():
                # self.fields['goods_code_alt'].disabled = False
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

            # self.fields['need_local_price_inquiry'].widget.attrs[
            #     'url'] = f'/core/ajax/micmod_base/quotationitem/up_create?pk={self.instance.pk}'
            # self.fields['need_local_price_inquiry'].widget.attrs['onchange'] = "post_ajax_data(event)"

            self.fields['has_delay'].widget.attrs[
                'url'] = f'/core/ajax/micmod_base/quotationitem/up_create?pk={self.instance.pk}'
            self.fields['has_delay'].widget.attrs['onchange'] = "post_ajax_data(event)"


        except Exception as e:
            pass



    class Meta:
        model = QuotationItem
        localized_fields = '__all__'
        fields = ['index', 'customer_goods_name', 'customer_goods_code', 'quantity', 'itemid', 'price_target',
                  'delivery_time', 'goods_code', 'goods_code_alt', 'price_method', 'final_price',
                  'goods_name', 'stock_amount', 'goods_avg_price', 'goods_price_sheet1', 'goods_price_sheet2',
                  'goods_price_sheet3', 'discount_per_item',
                  'goods_sheet_date', 'goods_market_date', 'goods_price_market', 'goods_avg_count',
                  'goods_name_alt', 'goods_last_sale', 'goods_last_price', 'goods_total_sales',
                  'stock_amount_res', 'goods_min_price', 'goods_max_price', 'trade_price_code', 'bazar_price_code',
                  'goods_q_last_sale', 'goods_q_last_price', 'goods_q_total_sales', 'local_price_inquiry_done',
                  'need_local_price_inquiry', 'foreign_price_inquiry_done', 'need_foreign_price_inquiry', 'description',
                  'assigned_trade_user', 'lead_time', 'assigned_trade_user2', 'task_start', 'task_start2',
                  'task_start_date', 'task_start_date2', 'has_delay', 'delay_reason', 'delay_time', 'item_in_china',
                  'selected_price_code', 'price_json', 'sales_description', 'supply_status', 'customer_request_item',
                  "supply_date", "pre_paid_amount",
                  #'bazar_selected_price_code', 'trade_selected_price_code'
                  ]
        widgets = {
            'selected_price_code': forms.Select(
                attrs={"class": "select2 selected_price_code", "style": "width:100%", 'name': 'selected_price_code'}),
            # 'goods_code': forms.Select(
            #     attrs={"class": "select2 goods_code", "style": "width:100%", 'name': 'goods_code'}),
            'goods_code_alt': forms.Select(
                attrs={"class": "select2 goods_code_alt", "style": "width:100%", }),
            'customer_goods_name': forms.Textarea(attrs={'name': 'customer_goods_name', "rows": 1}),
            'price_method': forms.HiddenInput(attrs={'class': 'price_method'}),
            # 'price_method': forms.Select(attrs={'class': 'price_method w-100 '}),
            'final_price': forms.TextInput(attrs={'disabled': True, 'class': 'final_price w-100 text-center'}),
            'goods_code': forms.HiddenInput(),
            'selected_price_code': forms.HiddenInput(),
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
            # 'goods_price_market': forms.HiddenInput(),
            'goods_name_alt': forms.HiddenInput(),
            'goods_last_price': forms.HiddenInput(),
            'goods_total_sales': forms.HiddenInput(),
            'goods_q_last_price': forms.HiddenInput(),
            'goods_q_total_sales': forms.HiddenInput(),
            'itemid': forms.HiddenInput(),
            'bazar_price_code': forms.HiddenInput(),
            'trade_price_code': forms.HiddenInput(),
            'goods_code_fk': forms.HiddenInput(),
            'index': forms.HiddenInput(),
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
        # print('new form nested: ===== ', index)

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
                    form.instance.is_deleted = True
                    form.instance.save()
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
    'index', 'customer_goods_name', 'customer_goods_code', 'quantity', 'itemid', 'price_target',
    'delivery_time', 'goods_code', 'goods_code_alt', 'price_method',
    'goods_name', 'stock_amount', 'goods_avg_price', 'goods_price_sheet1', 'goods_price_sheet2',
    'goods_price_sheet3', 'final_price', 'lead_time',
    'goods_sheet_date', 'goods_market_date', 'goods_price_market', 'goods_avg_count',
    'goods_name_alt', 'goods_last_sale', 'goods_last_price', 'goods_total_sales',
    'stock_amount_res', 'goods_min_price', 'goods_max_price',
    'goods_q_last_sale', 'goods_q_last_price', 'goods_q_total_sales', 'need_local_price_inquiry',
    'local_price_inquiry_done', 'need_foreign_price_inquiry', 'foreign_price_inquiry_done', 'description',
    'item_in_china', 'goods_code_fk', 'discount_per_item', 'selected_price_code', 'price_json', 'pre_paid_amount',
    'sales_description', 'supply_status', 'supply_date', 'customer_request_item',  #'bazar_selected_price_code', 'trade_selected_price_code'
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
                      ('time_range', _('time_range')),
                      ('my_quotations', _('my_quotations')),
                      ('quotation', _('quotation')),
                      ('customer_code', _('customer_code')),
                      ('search_sku', _('goods_code')),
                      ('my_inquiry_not_started', _('my_inquiry_not_started')),
                      ('inquiry_not_assigned', _('inquiry_not_assigned')),
                      ('force_inquiry', _('force_inquiry')),
                      ('search_part_number', _('part_number')),
                      ('customer_name', _('search_customer_name')),
                      # ('search_create_date', _('create_date')),
                      ('all', _('all'))
                        ]
    choice = forms.ChoiceField(choices=BLANK_CHOICE_DASH + CHOOSE_CHOICES)
    from_time = forms.DateField(required=False)
    to_time = forms.DateField(required=False)
    quotation = forms.IntegerField(required=False)
    customer_code = forms.IntegerField(required=False)
    my_quotations = forms.CharField(required=False)
    search_sku = forms.CharField(required=False)
    my_inquiry_not_started = forms.CharField(required=False)
    inquiry_not_assigned = forms.CharField(required=False)
    force_inquiry = forms.CharField(required=False)
    customer_name = forms.CharField(required=False)
    search_part_number = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super(PendingFormFilter, self).__init__(*args, **kwargs)
        self.fields['choice'].widget.attrs.update()
        self.fields['from_time'] = JalaliDateField(label=_('from_time'), widget=AdminJalaliDateWidget, required=False)
        self.fields['to_time'] = JalaliDateField(label=_('from_time'), widget=AdminJalaliDateWidget, required=False)
        self.fields['from_time'].widget.attrs.update(
            {'class': 'jalali_date-date d-none form-control', 'placeholder': _('from_time'), 'required': False})
        self.fields['to_time'].widget.attrs.update(
            {'class': 'jalali_date-date d-none form-control', 'placeholder': _('to_time'), 'required': False})

        self.fields['quotation'].widget.attrs.update({'class': 'd-none form-control', 'placeholder': _('quotation')})
        self.fields['customer_code'].widget.attrs.update({'class': 'd-none form-control', 'placeholder': _('customer_code')})
        self.fields['my_quotations'].widget.attrs.update({'class': 'd-none form-control', 'placeholder': _('my_quotations')})
        self.fields['search_sku'].widget.attrs.update({'class': 'd-none form-control', 'placeholder': _('goods_code')})
        self.fields['my_inquiry_not_started'].widget.attrs.update({'class': 'd-none form-control', 'placeholder': _('my_inquiry_not_started')})
        self.fields['inquiry_not_assigned'].widget.attrs.update({'class': 'd-none form-control', 'placeholder': _('inquiry_not_assigned')})
        self.fields['force_inquiry'].widget.attrs.update({'class': 'd-none form-control', 'placeholder': _('force_inquiry')})
        self.fields['search_part_number'].widget.attrs.update({'class': 'd-none form-control', 'placeholder': _('search_part_number')})
        self.fields['customer_name'].widget.attrs.update({'class': 'd-none form-control', 'placeholder': _('search_customer_name')})
        # self.fields['search_create_date'].widget.attrs.update({'class': 'd-none form-control', 'placeholder': _('goods_code')})


class TimeForm(CustomBaseForm):
    from_time = forms.DateField(required=False)
    to_time = forms.DateField(required=False)

    def __init__(self, *args, **kwargs):
        super(TimeForm, self).__init__(*args, **kwargs)
        self.fields['from_time'] = JalaliDateField(label=_('from_time'), widget=AdminJalaliDateWidget, required=False)
        self.fields['to_time'] = JalaliDateField(label=_('to_time'), widget=AdminJalaliDateWidget, required=False)
        self.fields['from_time'].widget.attrs.update(
            {'class': 'jalali_date-date form-control', 'placeholder': _('from_time'), 'required': False})
        self.fields['to_time'].widget.attrs.update(
            {'class': 'jalali_date-date form-control', 'placeholder': _('to_time'), 'required': False})


class CustomerRequestForm(CustomBaseModelForm):
    pass

    # class Meta:
    #     model = Quotation
    #
    #     fields = [
    #         "request_date",
    #         "expire_date",
    #         "customer_party_id", #"customer",
    #         "customer_phone",
    #         "cart_id",
    #         "request_extra_data",
    #               ]
    #
    # def __init__(self, *args, **kwargs):
    #     super(CustomerRequestForm, self).__init__(*args, **kwargs)
    #     self.fields['request_date'] = JalaliDateField(label=_('request_date'),
    #                                                   widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=True
    #                                                   )
    #     self.fields['expiration_date'] = JalaliDateField(label=_('expiration_date'),
    #                                                      widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=True
    #                                                      )


class CustomerRequestItemForm(CustomBaseModelForm):
    pass

    # class Meta:
    #     model = QuotationItem
    #     fields = [
    #         "cr",
    #         "cart_item_id",
    #         "quantity",
    #         "product_id",
    #         "customer_part_number",
    #         "customer_sku",
    #         "customer_description",
    #         "request_item_extra_data",
    #     ]
    #
    # def __init__(self, *args, **kwargs):
    #     super(CustomerRequestItemForm, self).__init__(*args, **kwargs)
