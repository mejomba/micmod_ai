import time

from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db.models import Q, Max
from django.forms import inlineformset_factory

from django import forms
from django.urls import reverse_lazy
from django_select2.forms import ModelSelect2MultipleWidget
from jalali_date.fields import JalaliDateField, JalaliDateTimeField, SplitJalaliDateTimeField
from jalali_date.widgets import AdminJalaliDateWidget, AdminSplitJalaliDateTime

from accounts.models import User
from core.forms import CustomBaseModelForm, FormMX
from extra_data.models import CustomerAddress
from factor.models import Factor, FactorItem, Delivery, FactorItemSupplyLocation
from files.models import File
from order.models import Order, OrderBazar
from tools.utils import timer
from translator import get_text as _
from django.utils.html import format_html
from workflow.models import FlowAdminGroup
from .services.supply import attach_supply


class x (AdminSplitJalaliDateTime):
    template_name = 'core/partial/jalali_split_datetime.html'


class UserSelectWidget(ModelSelect2MultipleWidget):
    search_fields = [
        "username__icontains",
        "first_name__icontains",
        "last_name__icontains",
        "email__icontains",
    ]


class FactorModelForm(CustomBaseModelForm):
    file_model = File
    file_groups = 4
    has_comment = True

    class Meta:
        model = Factor
        exclude = ['factor_self', 'guid', 'status', 'group', 'shop_document_id', 'shop_buy_factor_id', 'shop_payment_approved']

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
                flow_state_name = c.pop('flow_state_name', None)
            elif kwargs.get('constraint'):
                access = kwargs.get('constraint').get('wf_access')
                form_constraint = kwargs.get('constraint').get('form_constraint')
                formset_constraint = kwargs.get('constraint').get('formset_constraint')
                request = kwargs.get('constraint').get('request')  # remove unnecessary kwargs
                kwargs.pop('constraint')  # remove unnecessary kwargs
                flow_state_name = kwargs.pop('flow_state_name', None)

            if form_constraint:
                for item in form_constraint[self.form_state]:
                    if not isinstance(item, dict):
                        item = form_constraint[self.form_state]
                    if item.get('group') in request.user.groups.values_list('name', flat=True) or FlowAdminGroup.is_admin_of_group(request.user, item.get('group')):
                        form_constraint_read = item.get('read')  # form_constraint[self.form_state].get('read')
                        form_constraint_hide = item.get('hide')  # orm_constraint[self.form_state].get('hide')
            if formset_constraint:
                for item in formset_constraint[self.form_state]:
                    if not isinstance(item, dict):
                        item = formset_constraint[self.form_state]
                    if item.get('group') in request.user.groups.values_list('name', flat=True) or FlowAdminGroup.is_admin_of_group(request.user, item.get('group')):
                        formset_constraint_read = item.get('read')  # formset_constraint[self.form_state][0].get('read')
                        formset_constraint_hide = item.get('hide')  # formset_constraint[self.form_state][0].get('hide')
        super(FactorModelForm, self).__init__(*args, **kwargs)
        # self.make_hidden(['packing_json'])
        if self.instance.__class__.__name__.lower() == 'quotation':
            qs = (
                CustomerAddress.objects
                .filter(customer=self.instance.customer_party_id)
                .annotate(last_used=Max('factor__created_date'))
                .order_by('-last_used')
            )
            self.fields['address'].queryset = qs  # CustomerAddress.objects.filter(customer=self.instance.customer_party_id)
        elif self.instance.pk:
            customer = getattr(self.instance, 'customer_party_id', None) or self.instance.q.customer_party_id
            qs = (
                CustomerAddress.objects
                .filter(customer=customer)
                .annotate(last_used=Max('factor__created_date'))
                .order_by('-last_used')
            )
            self.fields['address'].queryset = qs  # CustomerAddress.objects.filter(customer=self.instance.q.customer_party_id)
        self.fields['is_official'].widget.attrs['onchange'] = 'factor_calculate_price_all_rows()'
        self.fields['official_value'].widget = forms.TextInput(attrs={'onchange': 'factor_calculate_price_all_rows()', 'class': 'LTR-RTL rounded font-size-11 text-center w-75'})
        self.fields['self_discount'].widget = forms.TextInput(attrs={'onchange': 'factor_calculate_price_all_rows()', 'class': 'LTR-RTL rounded font-size-11 text-center w-75'})

        self.make_hidden(['q'])
        self.fields['collecting_start_time'] = SplitJalaliDateTimeField(label=_('collecting_start_time'),
                                                      widget=x(
                                                          attrs={'class': 'jalali_date-date form-control',
                                                                 'size': '10'}), required=True if request and request.user.base_group == 'wh_admin' else False
                                                      )
        self.fields['collecting_end_time'] = forms.DateTimeField(required=False)
        self.fields['wh_user'] = forms.ModelMultipleChoiceField(queryset=User.objects.filter(Q(groups__name='wh_user') |
                                                                              Q(groups__name='wh_admin')).distinct(), required=False)
        self.fields['currency_amount'].widget.attrs.update({'class': 'form-control narrow-input', 'style': 'width: 70%;'})
        self.fields['notify_number'].widget.attrs.update({'class': 'form-control narrow-input font-size-12 pt-3 px-2 text-left', 'style': 'width: 70%;'})

        if request and request.user.base_group == 'accounting':
            self.fields['checker'] = forms.ModelMultipleChoiceField(queryset=User.objects.filter(Q(groups__name='accounting_user') |
                                                                                                 Q(groups__name='accounting_admin')).distinct(), required=False)
        else:
            self.fields['checker'] = forms.ModelMultipleChoiceField(
                queryset=User.objects.filter(Q(groups__name='accounting_user') |
                                             Q(groups__name='accounting_admin')).distinct(), required=False, disabled=True)

        self.make_disable(["sepidar_number", "sepidar_id"])
        self.make_hidden(form_constraint_hide or [])
        self.make_hidden(formset_constraint_hide or [])
        self.make_disable(form_constraint_read or [])
        self.make_disable(formset_constraint_read or [])
        self.make_hidden(['fiscalyearref', 'sepidar_voucher_id', 'sepidar_voucher_number',
                          'sepidar_inventory_delivery_id', 'sepidar_inventory_delivery_number', 'total_price'])
        if self.instance.pk and self.instance.sepidar_number:
            self.make_hidden(['cancel'])
        if self.form_state == 7:
            self.make_hidden(['self_discount', 'qi'])


class FactorItemModelForm(CustomBaseModelForm):
    product_id = forms.CharField(
        # choices=[],
        label='کالای شاپ',
        widget=forms.Select,  # این ویجت پیش‌فرض است، اما برای وضوح ذکر شده
        required=False,
    )
    class Meta:
        model = FactorItem
        exclude = ['group']
    # supply_location = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        internal_call = kwargs.pop('internal_call', None)
        request = access = form_constraint = formset_constraint = form_constraint_read = form_constraint_hide = formset_constraint_read = formset_constraint_hide = flow_state_name = None
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
                flow_state_name = kwargs.pop('form_state_name', None)
            elif kwargs.get('constraint'):
                access = kwargs.get('constraint').get('wf_access')
                form_constraint = kwargs.get('constraint').get('form_constraint')
                formset_constraint = kwargs.get('constraint').get('formset_constraint')
                request = kwargs.get('constraint').get('request')  # remove unnecessary kwargs
                flow_state_name = kwargs.get('constraint').get('form_state_name')
                kwargs.pop('constraint')  # remove unnecessary kwargs

            if request and not request.user.is_superuser and form_constraint:
                if self.form_state + 1 == len(form_constraint):
                    self.form_state -= 1
                for item in form_constraint[self.form_state]:
                    if not isinstance(item, dict):
                        item = form_constraint[self.form_state]
                    if item.get('group') in request.user.groups.values_list('name', flat=True) or FlowAdminGroup.is_admin_of_group_cached(request.user, item.get('group'), flow_state_name):
                        form_constraint_read = item.get('read')  # form_constraint[self.form_state].get('read')
                        form_constraint_hide = item.get('hide')  # orm_constraint[self.form_state].get('hide')
            if request and not request.user.is_superuser and formset_constraint:
                if self.form_state + 1 == len(form_constraint):
                    self.form_state -= 1
                for item in formset_constraint[self.form_state]:
                    if not isinstance(item, dict):
                        item = formset_constraint[self.form_state]
                    if item.get('group') in request.user.groups.values_list('name', flat=True) or FlowAdminGroup.is_admin_of_group_cached(request.user, item.get('group'), flow_state_name):
                        formset_constraint_read = item.get('read')  # formset_constraint[self.form_state][0].get('read')
                        formset_constraint_hide = item.get('hide')  # formset_constraint[self.form_state][0].get('hide')

        super(FactorItemModelForm, self).__init__(*args, **kwargs)

        self.fields['product_id'].initial = [("x", "y")]
        self.fields['quantity'].widget.attrs['onkeyup'] = 'check_quantity(event)'
        self.fields['price'].widget.attrs['onkeyup'] = 'check_price(event)'
        self.fields['price'].widget.attrs['class'] += ' comma-seperator'
        self.fields['is_bazar'].widget.attrs['class'] = 'checkbox_is_bazar'
        if self.fields['is_bazar']:
            self.make_disable(['supply_locations'])
        if self.instance:
            self.fields['supply_locations'].queryset = Order.objects.filter(item_id=self.instance.goods_code)

        self.make_hidden(form_constraint_hide or [])
        self.make_hidden(formset_constraint_hide or [])
        self.make_disable(form_constraint_read or [])
        self.make_disable(formset_constraint_read or [])
        if not access and not internal_call:
            self.make_disable(self.fields)

        self.make_enable(['supply_location'])
        self.make_hidden(['product_name',])
        # self.fields.pop('quantity')


factor_item_fields = ['factor', 'qi', 'index', 'quantity', 'delivery_time', 'custom_price', 'goods_code', 'price',
                      'part_number_show', 'supply_location', 'supply_locations', 'is_bazar', 'reserve_count',
                      'discount_per_item', 'product_id', 'product_name'
                      ]

FactorItemFormset = inlineformset_factory(
    Factor,
    FactorItem,
    form=FactorItemModelForm,
    extra=0,
    fields=factor_item_fields,
)


class DeliveryForm(CustomBaseModelForm):

    class Meta:
        model = Delivery
        exclude = ['group', 'delivery_date', 'tracking_number']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

# ─── فیلدهای مجاز Factor به ازای هر گروه ────────────────────────────────────
# "app_name.code_name"
FACTOR_FIELDS_BY_PERMISSION = {
    "factor.cp_factor_sales": {
        0: {
            "edit": [
                "q", "customer_party_id", "payment_method", "sale_type", "address", "delivery_time", "description",
                "deliver_type", "deliver_method", "self_discount", "is_official", "official_value", "currency_ref",
                "to_be_collected", "request_cancel", "require_official_factor_with_delivery", "need_factor_document", "file_2",
                "currency_amount", "force_factor", "is_reserve",
            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price", "is_safe"
            ],
            "show": ["delivery_time", "created_date", "need_financial_approval", "wh_user", "checker",
                     "accounting_confirm", "file_1", "file_2", "file_3", "file_4",]
        },
        1: {
            "edit": [
                "customer_party_id", "payment_method", "sale_type", "address", "delivery_time", "description",
                "deliver_type", "deliver_method", "self_discount", "is_official", "official_value", "currency_ref",
                "to_be_collected", "request_cancel", "require_official_factor_with_delivery", "need_factor_document", "file_2",
                "currency_amount", "force_factor"
            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price",
            ],
            "show": ["delivery_time", "q", "created_date", "need_financial_approval", "wh_user", "checker",
                     "accounting_confirm", "file_1", "file_2", "file_3", "file_4"]
        },
        2: {
            "edit": [
                "payment_method", "sale_type", "address", "delivery_time", "description",
                "deliver_type", "self_discount", "is_official", "official_value", "currency_ref",
                "request_cancel", "require_official_factor_with_delivery", "need_factor_document",
                "currency_amount",
            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price",
            ],
            "show": ["customer_party_id", "delivery_time", "q", "created_date", "need_financial_approval", "wh_user",
                     "checker", "accounting_confirm", "file_1", "file_2", "file_3", "file_4", "q", "to_be_collected",
                     "force_factor", "deliver_method", ]
        },
        3: {
            "edit": [
                "payment_method", "sale_type", "address", "delivery_time", "description",
                "deliver_type", "self_discount", "is_official", "official_value", "currency_ref",
                "request_cancel", "require_official_factor_with_delivery", "need_factor_document", "file_2",
                "currency_amount",
            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price",
            ],
            "show": ["customer_party_id", "delivery_time", "q", "created_date", "need_financial_approval", "wh_user",
                     "checker", "accounting_confirm", "file_1", "file_2", "file_3", "file_4", "q", "to_be_collected",
                     "force_factor", "deliver_method", ]
        },
        4: {
            "edit": [
                "customer_party_id", "payment_method", "sale_type", "address", "delivery_time", "description",
                "deliver_type", "self_discount", "is_official", "official_value", "currency_ref",
                "request_cancel", "require_official_factor_with_delivery", "need_factor_document", "file_2",
                "currency_amount",
            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price",
            ],
            "show": ["customer_party_id", "delivery_time", "q", "created_date", "need_financial_approval", "wh_user",
                     "checker", "accounting_confirm", "file_1", "file_2", "file_3", "file_4", "q", "to_be_collected",
                     "force_factor", "deliver_method"]
        },
        5: {
            "edit": [
                "request_cancel",
            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price", "q",
            ],
            "show": ["customer_party_id", "payment_method", "sale_type", "address", "delivery_time", "description",
                     "deliver_type", "deliver_method", "self_discount", "is_official", "official_value", "currency_ref",
                     "to_be_collected", "cancel", "require_official_factor_with_delivery", "need_factor_document",
                     "file_2", "currency_amount","delivery_time", "q", "created_date", "need_financial_approval",
                     "wh_user", "checker", "accounting_confirm", "file_1", "file_3", "file_4", "q", "to_be_collected",
                     "force_factor", "sepidar_number", "sepidar_inventory_delivery_number", "sepidar_voucher_number", ]
        },
        6: {
            "edit": [

            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price", "q"
            ],
            "show": ["customer_party_id", "payment_method", "sale_type", "address", "delivery_time", "description",
                     "deliver_type", "deliver_method", "self_discount", "is_official", "official_value", "currency_ref",
                     "to_be_collected", "cancel", "require_official_factor_with_delivery", "need_factor_document",
                     "file_2", "currency_amount","delivery_time", "q", "created_date", "need_financial_approval",
                     "wh_user", "checker", "accounting_confirm", "file_1", "file_3", "file_4", "q", "to_be_collected",
                     "force_factor", "sepidar_number", "sepidar_inventory_delivery_number", "sepidar_voucher_number", ]
        },
        7: {
            "edit": [

            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price",
            ],
            "show": ["customer_party_id", "payment_method", "sale_type", "address", "delivery_time", "description",
                     "deliver_type", "deliver_method", "self_discount", "is_official", "official_value", "currency_ref",
                     "to_be_collected", "cancel", "require_official_factor_with_delivery", "need_factor_document",
                     "file_2", "currency_amount","delivery_time", "q", "created_date", "need_financial_approval",
                     "wh_user", "checker", "accounting_confirm", "file_1", "file_3", "file_4", "q", "to_be_collected",
                     "force_factor", "sepidar_number", "sepidar_inventory_delivery_number", "sepidar_voucher_number", ]
        },
    },
    "factor.cp_factor_sales_admin": {
        0: {
            "edit": [
                "customer_party_id", "payment_method", "sale_type", "address", "delivery_time", "description",
                "deliver_type", "deliver_method", "self_discount", "is_official", "official_value", "currency_ref",
                "to_be_collected", "request_cancel", "require_official_factor_with_delivery", "need_factor_document", "file_2",
                "currency_amount", "q", "force_factor", "is_reserve",
            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price", "is_safe"
            ],
            "show": ["delivery_time", "created_date", "need_financial_approval", "wh_user", "checker",
                     "accounting_confirm", "file_1", "file_2", "file_3", "file_4",]
        },
        1: {
            "edit": [
                "customer_party_id", "payment_method", "sale_type", "address", "delivery_time", "description",
                "deliver_type", "deliver_method", "self_discount", "is_official", "official_value", "currency_ref",
                "to_be_collected", "request_cancel", "require_official_factor_with_delivery", "need_factor_document", "file_2",
                "currency_amount", "force_factor",
            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price",
            ],
            "show": ["delivery_time", "q", "created_date", "need_financial_approval", "wh_user", "checker",
                     "accounting_confirm", "file_1", "file_2", "file_3", "file_4", "q",]
        },
        2: {
            "edit": [
                "payment_method", "sale_type", "address", "delivery_time", "description",
                "deliver_type", "deliver_method", "self_discount", "is_official", "official_value", "currency_ref",
                "request_cancel", "require_official_factor_with_delivery", "need_factor_document",
                "currency_amount",
            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price",
            ],
            "show": ["customer_party_id", "delivery_time", "q", "created_date", "need_financial_approval", "wh_user",
                     "checker", "accounting_confirm", "file_1", "file_2", "file_3", "file_4", "q", "to_be_collected", ]
        },
        3: {
            "edit": [
                "payment_method", "sale_type", "address", "delivery_time", "description",
                "deliver_type", "deliver_method", "self_discount", "is_official", "official_value", "currency_ref",
               "request_cancel", "require_official_factor_with_delivery", "need_factor_document", "file_2",
                "currency_amount",
            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price",
            ],
            "show": ["customer_party_id", "delivery_time", "q", "created_date", "need_financial_approval", "wh_user",
                     "checker", "accounting_confirm", "file_1", "file_2", "file_3", "file_4", "q", "to_be_collected", ]
        },
        4: {
            "edit": [
                "customer_party_id", "payment_method", "sale_type", "address", "delivery_time", "description",
                "deliver_type", "deliver_method", "self_discount", "is_official", "official_value", "currency_ref",
                "request_cancel", "require_official_factor_with_delivery", "need_factor_document", "file_2",
                "currency_amount",
            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price",
            ],
            "show": ["customer_party_id", "delivery_time", "q", "created_date", "need_financial_approval", "wh_user",
                     "checker", "accounting_confirm", "file_1", "file_2", "file_3", "file_4", "q", "to_be_collected", ]
        },
        5: {
            "edit": [
                "request_cancel",
            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price", "q",
            ],
            "show": ["customer_party_id", "payment_method", "sale_type", "address", "delivery_time", "description",
                     "deliver_type", "deliver_method", "self_discount", "is_official", "official_value", "currency_ref",
                     "to_be_collected", "cancel", "require_official_factor_with_delivery", "need_factor_document",
                     "file_2", "currency_amount","delivery_time", "q", "created_date", "need_financial_approval",
                     "wh_user", "checker", "accounting_confirm", "file_1", "file_3", "file_4", "q", "to_be_collected",
                     "sepidar_number", "sepidar_inventory_delivery_number", "sepidar_voucher_number", ]
        },
        6: {
            "edit": [

            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price", "q"
            ],
            "show": ["customer_party_id", "payment_method", "sale_type", "address", "delivery_time", "description",
                     "deliver_type", "deliver_method", "self_discount", "is_official", "official_value", "currency_ref",
                     "to_be_collected", "cancel", "require_official_factor_with_delivery", "need_factor_document",
                     "file_2", "currency_amount","delivery_time", "q", "created_date", "need_financial_approval",
                     "wh_user", "checker", "accounting_confirm", "file_1", "file_3", "file_4", "q", "to_be_collected",
                     "sepidar_number", "sepidar_inventory_delivery_number", "sepidar_voucher_number", ]
        },
        7: {
            "edit": [

            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price",
            ],
            "show": ["customer_party_id", "payment_method", "sale_type", "address", "delivery_time", "description",
                     "deliver_type", "deliver_method", "self_discount", "is_official", "official_value", "currency_ref",
                     "to_be_collected", "cancel", "require_official_factor_with_delivery", "need_factor_document",
                     "file_2", "currency_amount","delivery_time", "q", "created_date", "need_financial_approval",
                     "wh_user", "checker", "accounting_confirm", "file_1", "file_3", "file_4", "q", "to_be_collected",
                     "sepidar_number", "sepidar_inventory_delivery_number", "sepidar_voucher_number", ]
        },
    },
    "factor.cp_factor_wh": {
        1: {
            "edit": [

            ],
            "hidden": [
                "addition", "tax", "duty", "total_price",
            ],
            "show": ["customer_party_id", "delivery_time", "q", "created_date", "need_financial_approval",
                     "checker", "accounting_confirm", "wh_user", "file_1", "file_2", "file_3", "file_4"]
        },
        2: {
            "edit": [
                "collecting_start_time", "address", "deliver_type", "deliver_method",
                "file_2", "file_3", "file_4", "wh_user"
            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price",
            ],
            "show": ["customer_party_id", "delivery_time", "q", "created_date", "need_financial_approval",
                     "checker", "accounting_confirm", "file_1"]
        },
        3: {
            "edit": [
                "address", "deliver_type", "deliver_method", "file_2", "file_3", "file_4"
            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price",
            ],
            "show": ["customer_party_id", "delivery_time", "q", "created_date", "need_financial_approval", "wh_user",
                     "checker", "accounting_confirm", "file_1", "collecting_start_time"]
        },
        4: {
            "edit": [
                "address", "deliver_type", "deliver_method", "file_2", "file_3", "file_4", "final_check"
            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price",
            ],
            "show": ["customer_party_id", "delivery_time", "q", "created_date", "need_financial_approval", "wh_user",
                     "checker", "accounting_confirm", "file_1", "collecting_start_time"]
        },
        5: {
            "edit": [
                "address", "deliver_type", "deliver_method", "file_2", "file_3", "file_4",
            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price",
            ],
            "show": ["customer_party_id", "wh_user", "checker", "accounting_confirm", "file_1", "collecting_start_time",
                     "sepidar_number", "sepidar_inventory_delivery_number", "sepidar_voucher_number", ]
        },
        6: {
            "edit": [
                "address", "deliver_type", "deliver_method", "file_2", "file_3", "file_4",
            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price",
            ],
            "show": ["customer_party_id", "wh_user", "checker", "accounting_confirm", "file_1", "collecting_start_time",
                     "sepidar_number", "sepidar_inventory_delivery_number", "sepidar_voucher_number", ]
            },
        7: {
            "edit": [

            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price",
            ],
            "show": ["customer_party_id", "wh_user", "checker", "accounting_confirm", "file_1", "collecting_start_time",
                     "sepidar_number", "sepidar_inventory_delivery_number", "sepidar_voucher_number", ]
        },
    },
    "factor.cp_factor_accounting": {
        2: {
            "edit": [
                "file_1", "file_4", "checker", "official_factor_for_this_factor", "accounting_confirm"
            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price",
            ],
            "show": ["customer_party_id", "q", "created_date", "self_discount",
                     "file_2", "file_3", "wh_user", "deliver_method", "sale_type",
                     "is_official", "official_value", "payment_method", "currency_ref", "currency_amount",
                     "creator_user", "description"]
        },
        3: {
            "edit": [
                "file_1", "file_4", "checker", "official_factor_for_this_factor", "accounting_confirm"
            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price",
            ],
            "show": ["customer_party_id", "q", "created_date", "self_discount",
                     "file_2", "file_3", "wh_user", "deliver_method", "sale_type",
                     "is_official", "official_value", "payment_method", "currency_ref", "currency_amount",
                     "creator_user", "description"]
        },
        4: {
            "edit": [
                "file_1", "file_4", "checker", "official_factor_for_this_factor", "accounting_confirm"
            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price",
            ],
            "show": ["customer_party_id", "q", "created_date", "self_discount",
                     "file_2", "file_3", "wh_user", "deliver_method", "sale_type",
                     "is_official", "official_value", "payment_method", "currency_ref", "currency_amount",
                     "creator_user", "description"]
        },
        5: {
            "edit": [
                "file_1", "file_4", "checker", "official_factor_for_this_factor", "accounting_confirm"
            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price",
            ],
            "show": ["customer_party_id", "q", "created_date", "self_discount",
                     "file_2", "file_3", "wh_user", "deliver_method", "sale_type",
                     "is_official", "official_value", "payment_method", "currency_ref", "currency_amount",
                     "creator_user", "description",
                     "sepidar_number", "sepidar_inventory_delivery_number", "sepidar_voucher_number", ]
        },
        6: {
            "edit": [
                "file_1", "file_4", "checker", "official_factor_for_this_factor", "accounting_confirm"
            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price",
            ],
            "show": ["customer_party_id", "q", "created_date", "self_discount",
                     "file_2", "file_3", "wh_user", "deliver_method", "sale_type",
                     "is_official", "official_value", "payment_method", "currency_ref", "currency_amount",
                     "creator_user", "description",
                     "sepidar_number", "sepidar_inventory_delivery_number", "sepidar_voucher_number", ]
            },
        7: {
            "edit": [
                "file_1", "file_4", "checker", "official_factor_for_this_factor", "accounting_confirm"
            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price",
            ],
            "show": ["customer_party_id", "q", "created_date", "self_discount",
                     "file_2", "file_3", "wh_user", "deliver_method", "sale_type",
                     "is_official", "official_value", "payment_method", "currency_ref", "currency_amount",
                     "creator_user", "description",
                     "sepidar_number", "sepidar_inventory_delivery_number", "sepidar_voucher_number", ]
        },
    },
    "factor.cp_factor_admin": {},
    "factor.cp_factor_superuser": {},
}

# ─── فیلدهای مجاز FactorItem به ازای هر گروه ─────────────────────────────────
FACTOR_ITEM_FIELDS_BY_PERMISSION = {
    "factor.cp_factor_item_sales": {
        0: {
            "edit": [
                "goods_code", "part_number_show", "quantity", "price", "final_amount", "discount_per_item",
                'product_id', 'product_name'
            ],
            "hidden": [
                "qi", "factor"
            ],
            "show": [

            ]
        },
        1: {
            "edit": [
                "goods_code", "part_number_show", "quantity", "price", "final_amount", "discount_per_item",
                'product_id', 'product_name'
            ],
            "hidden": [
                "qi", "factor"
            ],
            "show": [

            ]
        },
        2: {
            "edit": [
                "price", "final_amount", "discount_per_item",
            ],
            "hidden": [
                "qi", "factor", "total_forms", "initial_forms", "min_num_forms", "max_num_forms",
            ],
            "show": [
                "quantity",
            ]
        },
        3: {
            "edit": [
                "price", "final_amount", "discount_per_item",
            ],
            "hidden": [
                "qi", "factor", "total_forms", "initial_forms", "min_num_forms", "max_num_forms",
            ],
            "show": [
                "quantity",
            ]
        },
        4: {
            "edit": [
                "price", "final_amount", "discount_per_item",
            ],
            "hidden": [
                "qi", "factor", "total_forms", "initial_forms", "min_num_forms", "max_num_forms",
            ],
            "show": [
                "quantity",
            ]
        },
        5: {
            "edit": [

            ],
            "hidden": [
                "qi", "factor", "total_forms", "initial_forms", "min_num_forms", "max_num_forms",
            ],
            "show": [
                "price", "final_amount", "quantity", "discount_per_item"
            ]
        },
        6: {
            "edit": [

            ],
            "hidden": [
                "qi", "factor", "total_forms", "initial_forms", "min_num_forms", "max_num_forms",
            ],
            "show": [
                "price", "final_amount", "quantity", "discount_per_item"
            ]
        },
        7: {
            "edit": [

            ],
            "hidden": [
                "qi", "factor", "total_forms", "initial_forms", "min_num_forms", "max_num_forms",
            ],
            "show": [
                "price", "final_amount", "quantity", "discount_per_item"
            ]
        },

    },
    "factor.cp_factor_item_sales_admin": {
        0: {
            "edit": [
                "goods_code", "part_number_show", "quantity", "price", "final_amount", "discount_per_item",
                'product_id', 'product_name'
            ],
            "hidden": [
                "qi", "factor"
            ]
        },
    },
    "factor.cp_factor_item_wh": {
        1: {
            "edit": [

            ],
            "hidden": [
                "qi", "factor", "total_forms", "initial_forms", "min_num_forms", "max_num_forms"
            ],
            "show": ["goods_code", "part_number_show", "quantity",]
        },
        2: {
                "edit": [

                ],
                "hidden": [
                    "qi", "factor", "total_forms", "initial_forms", "min_num_forms", "max_num_forms"
                ],
                "show": ["goods_code", "part_number_show", "quantity",]
        },
        3: {
                "edit": [

                ],
                "hidden": [
                    "qi", "factor", "total_forms", "initial_forms", "min_num_forms", "max_num_forms"
                ],
                "show": ["goods_code", "part_number_show", "quantity",]
        },
        4: {
                "edit": [

                ],
                "hidden": [
                    "qi", "factor", "total_forms", "initial_forms", "min_num_forms", "max_num_forms"
                ],
                "show": ["goods_code", "part_number_show", "quantity",]
            },
        5: {
                "edit": [

                ],
                "hidden": [
                    "qi", "factor", "total_forms", "initial_forms", "min_num_forms", "max_num_forms"
                ],
                "show": ["goods_code", "part_number_show", "quantity",]
            },
        6: {
                "edit": [

                ],
                "hidden": [
                    "qi", "factor", "total_forms", "initial_forms", "min_num_forms", "max_num_forms"
                ],
                "show": ["goods_code", "part_number_show", "quantity",]
            },
        7: {
                "edit": [

                ],
                "hidden": [
                    "qi", "factor", "total_forms", "initial_forms", "min_num_forms", "max_num_forms"
                ],
                "show": ["goods_code", "part_number_show", "quantity",]
        },
    },
    "factor.cp_factor_item_accounting": {
        1: {
            "edit": [

            ],
            "hidden": [
                "qi", "factor", "total_forms", "initial_forms", "min_num_forms", "max_num_forms"
            ],
            "show": ["goods_code", "part_number_show", "quantity", "price", "final_amount", "discount_per_item"]
        },
        2: {
            "edit": [

            ],
            "hidden": [
                "qi", "factor", "total_forms", "initial_forms", "min_num_forms", "max_num_forms"
            ],
            "show": ["goods_code", "part_number_show", "quantity", "price", "final_amount", "discount_per_item"]
        },
        3: {
            "edit": [

            ],
            "hidden": [
                "qi", "factor", "total_forms", "initial_forms", "min_num_forms", "max_num_forms"
            ],
            "show": ["goods_code", "part_number_show", "quantity", "price", "final_amount", "discount_per_item"]
        },
        4: {
            "edit": [

            ],
            "hidden": [
                "qi", "factor", "total_forms", "initial_forms", "min_num_forms", "max_num_forms"
            ],
            "show": ["goods_code", "part_number_show", "quantity", "price", "final_amount", "discount_per_item"]
            },
        5: {
            "edit": [

            ],
            "hidden": [
                "qi", "factor", "total_forms", "initial_forms", "min_num_forms", "max_num_forms"
            ],
            "show": ["goods_code", "part_number_show", "quantity", "price", "final_amount", "discount_per_item"]
            },
        6: {
                "edit": [

                ],
                "hidden": [
                    "qi", "factor", "total_forms", "initial_forms", "min_num_forms", "max_num_forms"
                ],
                "show": ["goods_code", "part_number_show", "quantity", "price", "final_amount", "discount_per_item"]
            },
        7: {
                "edit": [

                ],
                "hidden": [
                    "qi", "factor", "total_forms", "initial_forms", "min_num_forms", "max_num_forms"
                ],
                "show": ["goods_code", "part_number_show", "quantity", "price", "final_amount", "discount_per_item"]
            },
        }
    }


# ─── فرم Factor ───────────────────────────────────────────────────────────────


class FactorEditForm(FormMX, CustomBaseModelForm):
    has_comment = True
    # ── پیکربندی فایل ──
    file_model = File  # مدل File (generic FK)
    file_groups_2 = 4  # تعداد اسلات‌های فایل
    file_labels = {1: "اسناد مالی", 2: "اسناد انبار", 3: "اسناد تحویل", 4: "فاکتور رسمی"}
    file_group_field = "group"  # فیلدی در File که شماره‌ی گروه را نگه می‌دارد (توصیه‌شده)
    file_file_field = "file"  # نام FileField در مدل File
    file_field_prefix = "file_"
    field_layout = [
        "q", "customer_party_id", "address", "delivery_time",  "sepidar_number", "sepidar_id", "sepidar_inventory_delivery_number",
        "sepidar_inventory_delivery_id", "sepidar_voucher_number", "sepidar_voucher_id", "fiscalyearref", "factor_self",
        "self_discount", "official_value", "wh_user", "deliver_type", "payment_method", "sale_type",
        "need_financial_approval","accounting_confirm", "collecting_start_time", "collecting_end_time",
        "official_factor_send_with_this_factor", "official_factor_for_this_factor",
        "checker", "packing_json", "customer_request", "currency_ref", "deliver_method",  "description",
        # "rate",
        "total_price", "tax", "final_price", "addition", "tax", "duty", "currency_amount",
        # checkbox section
        "is_official", "request_cancel", "cancel", "deliver_to_customer", "sales_admin_confirm", "final_check", "force_factor",
        "require_official_factor_with_delivery", "to_be_collected", "need_factor_document", "is_reserve",
        # file section
        "file_1",  # اسناد مالی
        "file_2",  # اسناد انبار
        "file_3",  # اسناد تحویل
        "file_4",  # فاکتور رسمی
    ]
    select2_url_name = "factor:select2-search"  # نام URL ویوی سرچ AJAX
    select2_fields = {
        "currency_ref": {},  # لوکال
        "sale_type": {},  # لوکال
        "wh_user": {"ajax": "wh_user", "min_input": 0, "placeholder": "انتخاب کارشناس انبار"},
        "checker": {"ajax": "checker", "min_input": 0, "placeholder": "انتخاب کارشناس مالی"},  # لوکال M2M
        "address": {"ajax": "address", "placeholder": "جستجوی آدرس", "min_input": 0},
        "customer_party_id": {"ajax": "customer_party_id", "min_input": 2, "placeholder": "انتخاب مشتری"},
        "q": {"ajax": "q", "min_input": 2, "placeholder": "انتخاب پیش فاکتور"},
    }  # {field: {"ajax": key, "placeholder": str, "min_input": int}}

    class Meta:
        model = Factor
        fields = "__all__"
        widgets = {
            "description": forms.Textarea(attrs={"rows": 1}),
            "official_factor_send_with_this_factor": forms.TextInput(),
            "official_factor_for_this_factor": forms.TextInput(),
            "collecting_start_time": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "collecting_end_time": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
        }

    def __init__(self, *args, allowed_fields=None, allowed_hidden=None, only_show=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.only_show = list(only_show or [])
        self.allowed_fields = list(allowed_fields or [])
        self._add_file_fields()

        self._apply_select2()
        self.make_optional(['checker', 'q'])
        self.make_required(['customer_party_id'])

        self.fields['is_safe'].initial = True
        self.fields['collecting_start_time'] = SplitJalaliDateTimeField(label=_('collecting_start_time'),
                                                                        widget=x(
                                                                            attrs={
                                                                                'class': 'jalali_date-date form-control',
                                                                                'size': '10'}),
                                                                        required=False
                                                                        )

        self.fields['q'].widget.attrs['data-on-select'] = 'prefactorSelected'
        self.fields['q'].widget.attrs['data-detail-url'] = reverse_lazy('factor:prefactor-json', args=[0])

        # ========= remove field
        if self.instance.pk and 'q' in self.allowed_fields:
            self.allowed_fields.remove('q')
            self.only_show.append('q')
        if self.allowed_fields is not None or allowed_hidden is not None:
            keep = set(self.allowed_fields or []) | set(allowed_hidden or [])
            for name in list(self.fields):
                if name not in keep:
                    self.fields.pop(name)

        # ========= hide field
        if allowed_hidden is not None:
            for field_name in list(self.fields):
                if field_name in allowed_hidden:
                    self.fields[field_name].widget = self.fields[field_name].hidden_widget()

        for name in self.only_show:  # only_show نباید در فرم باشد (دفاعی)
            self.fields.pop(name, None)




# ─── فرم FactorItem ───────────────────────────────────────────────────────────
import json
class FactorItemForm(CustomBaseModelForm):
    field_layout = []
    supply_locations = forms.CharField(
        required=False, widget=forms.HiddenInput
    )
    class Meta:
        model = FactorItem
        fields = "__all__"
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "quantity": forms.TextInput(attrs={"inputmode": "decimal", "class": " js-thousands"}),
            "price": forms.TextInput(attrs={"inputmode": "decimal", "class": " js-thousands"}),
            # "discount_per_item": forms.TextInput(attrs={"inputmode": "decimal", "class": " js-thousands"}),
            "final_amount": forms.TextInput(attrs={"inputmode": "decimal", "class": " js-thousands"}),
        }

    def __init__(self, *args, allowed_fields=None, allowed_hidden=None, only_show=None, **kwargs):
        super().__init__(*args, **kwargs)

        """prepare fields default value and widget customization before permission section"""
        self.fields['price'].widget.attrs['onkeyup'] = "factor_calculate_price(this)"
        self.fields['discount_per_item'].widget.attrs['onkeyup'] = "factor_calculate_price(this)"
        self.fields['final_amount'].widget.attrs['onkeyup'] = "factor_calculate_price(this)"
        self.make_required(['quantity', 'price', 'discount_per_item', 'goods_code', 'part_number_show'])

        self.fields['quantity'].widget.attrs['required'] = 'required'
        self.fields['price'].widget.attrs['required'] = 'required'
        self.fields['final_amount'].widget.attrs['required'] = 'required'
        self.fields['goods_code'].widget.attrs['required'] = 'required'
        self.fields['part_number_show'].widget.attrs['required'] = 'required'

        for f in self.fields:
            self.fields[f].widget.attrs['class'] = self.fields[f].widget.attrs.get('class', '') + " p-5px"

        if not self.instance.pk:
            self.fields['discount_per_item'].initial = 0

        """permission section: del and hiddel fields"""
        if allowed_fields is not None:
            for field_name in list(self.fields):
                if field_name not in allowed_fields and field_name not in allowed_hidden:
                    del self.fields[field_name]

        if allowed_hidden is not None:
            for field_name in list(self.fields):
                if field_name in allowed_hidden:
                    self.fields[field_name].widget = self.fields[field_name].hidden_widget()

    def clean_supply_locations(self):
        raw = self.cleaned_data.get('supply_locations') or '[]'
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise forms.ValidationError("داده‌ی محل تامین معتبر نیست")
        # اعتبارسنجی اولیه — مجموع باید با quantity برابر باشد و غیره
        return data




from django.forms.models import BaseInlineFormSet
from django.db.models import Prefetch

class FactorItemInlineFormSetBase(BaseInlineFormSet):
    """
    در GET، آیتم‌ها را با prefetch روی محل تامین‌ها لود می‌کند و .supply می‌چسباند.
    در POST از این کار صرف نظر می‌کند چون داده‌ی فرم در حال validate شدن است.
    """
    supply_locations = forms.CharField(
        required=False, widget=forms.HiddenInput
    )
    @timer
    def get_queryset(self):
        print('get_queryset ...')
        if not hasattr(self, "_queryset"):
            if self.instance.pk is None:
                # فاکتور هنوز ساخته نشده — هیچ آیتمی نیست
                self._queryset = []
                return self._queryset

            qs = (
                self.model._default_manager
                .filter(**{self.fk.name: self.instance})
                .order_by("pk")
            )

            if not self.is_bound:  # فقط GET
                qs = qs.prefetch_related(
                    Prefetch(
                        "factoritemsupplylocation_set",
                        queryset=FactorItemSupplyLocation.objects.select_related(
                            "wh_reserve", "order", "order_bazar",
                        ),
                    )
                )
                items = list(qs)
                attach_supply(items)            # تابعی که قبلاً نوشتیم
                self._queryset = items
            else:
                self._queryset = list(qs)

        return self._queryset