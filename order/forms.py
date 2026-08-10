from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.db.models import Q
from jalali_date.fields import JalaliDateField
from jalali_date.widgets import AdminJalaliDateWidget

from files.models import File
from inquiry.models import Supplier, PriceInquiryResult
from micmod_base.base import Currency
from translator import get_text as _

from core.forms import CustomBaseModelForm, CustomBaseForm, FormMX
from order.models import Order, OrderOrder, Packing, PackingItem, GIO, GIOItem, OrderPayment, OrderPaymentItem, ACNT, \
    OrderBazar, OrderDelayReason
from dal import autocomplete

from django.forms import inlineformset_factory, formset_factory

class OrderSafeForm(FormMX, CustomBaseModelForm):
    has_comment = True
    field_layout = [
        "customer_party_id", "order_title", "order_number", "item",
        "transportation_method", "commitment_date_to_customer", "quantity", "description_sale", "order_type", "price",
        "item_trade", "quantity_trade", "po_number_trade", "supplier_trade", "price_trade", "description_trade",
        "apply_mac", "mohandes_confirmation", "trade_commitment_date", "production_lead_time", "trade_lock_order",
        "supplier_mac", "price_mac", "part_number_mac", "po_number_mac", "quantity_mac", "description_mac",
        "sales_admin_confirmation", "cancel", "qi", "currency", "order_m2m", "customer_request_item",
        "buy_factors", "buy_factor_quantity_in_sepidar", "order_report_data", "sepidar_wh_code", "receipt_in_wh",
        "price_inquiry_result", "trade_user", "is_bazar", "is_wh", "is_over", "is_kasri", "sales_admin_cancel",
    ]
    select2_url_name = "order:order.select2-search"  # نام URL ویوی سرچ AJAX
    select2_fields = {
        "currency": {},  # لوکال
        "pay_operator": {},  # لوکال
        "buy_operator": {},  # لوکال
        "item": {"ajax": "item", "min_input": 2, "placeholder": "انتخاب کالا"},
        "item_trade": {"ajax": "item", "min_input": 2, "placeholder": "انتخاب کالا بازرگانی"},
        # "supplier_trade": {"ajax": "supplier", "min_input": 2, "placeholder": "انتخاب تامین کننده بازرگانی"},
        # "supplier_mac": {"ajax": "supplier", "min_input": 2, "placeholder": "select supplier (mac)"},
        "price_inquiry_result": {"ajax": "inquiry", "min_input": 0, "placeholder": "جستجو با کد کالا"},
        "trade_user": {"ajax": "trade_user", "min_input": 0, "placeholder": "کارشناس بازرگانی"},
        "customer_party_id": {"ajax": "customer_party_id", "min_input": 2, "placeholder": "انتخاب مشتری"},
    }

    class Meta:
        model = Order
        fields = "__all__"
        widgets = {
            "description_sale": forms.Textarea(attrs={"rows": 1}),
        }

    def __init__(self, *args, allowed_fields=None, allowed_hidden=None, only_show=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.only_show = list(only_show or [])
        self.allowed_fields = list(allowed_fields or [])
        self._add_file_fields()
        self._apply_select2()

        # ========= customize fields before permission apply
        self.make_required(['price_trade', 'item', 'quantity',
                            'supplier_trade', 'currency', 'trade_user'])
        self.fields['description_sale'].widget.attrs['rows'] = 1
        self.fields['description_trade'].widget.attrs['rows'] = 1
        self.fields['description_mac'].widget.attrs['rows'] = 1

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


class PriceInquiryResultChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        # return ''
        return f"{obj.supplier} - {obj.inquiry_type} - ({obj.price}) - {obj.price_update_date.date()}"


class OrderForm(CustomBaseModelForm):
    has_comment = True

    class Meta:
        model = Order
        exclude = ['group', 'last_work_flow']

    def order_zero_state_access(self):
        user = self.request.user
        if user.has_perm('order.zero_state'):
            self.access = True
        else:
            self.access = False

    def order_first_state_access(self):
        if self.request.user.has_perm('x'):
            pass

    def order_second_state_access(self):
        pass

    def order_third_state_access(self):
        pass

    def order_forth_state_access(self):
        pass

    def order_fiveth_state_access(self):
        pass

    def order_sixth_state_access(self):
        pass

    def order_seventh_state_access(self):
        pass

    def order_eighth_state_access(self):
        pass

    def __init__(self, *args, **kwargs):
        self.request = self.access = self.form_constraint = self.formset_constraint = self.form_constraint_read = self.form_constraint_hide = self.formset_constraint_read = self.formset_constraint_hide = None
        if self.form_state is None:
            if kwargs.get('initial') and (c := kwargs.get('initial').get('constraint')):
                self.form_state = c.get('form_state')
            elif kwargs.get('constraint'):
                self.form_state = kwargs.get('constraint').get('form_state')

        if self.form_state is not None:
            if kwargs.get('initial') and (c := kwargs.get('initial').get('constraint')):
                self.form_constraint = c.pop('form_constraint')  # remove unnecessary kwargs
                self.formset_constraint = c.pop('formset_constraint')  # remove unnecessary kwargs
                self.request = c.pop('request')  # remove unnecessary kwargs
                self.access = c.get('wf_access')
            elif kwargs.get('constraint'):
                self.form_constraint = kwargs.get('constraint').get('form_constraint')
                self.formset_constraint = kwargs.get('constraint').get('formset_constraint')
                self.request = kwargs.get('constraint').get('request')
                self.access = kwargs.get('constraint').get('wf_access')
                kwargs.pop('constraint')  # remove unnecessary kwargs
            if self.form_constraint:
                self.form_constraint_read = self.form_constraint[self.form_state].get('read')
                self.form_constraint_hide = self.form_constraint[self.form_state].get('hide')
            if self.formset_constraint:
                self.formset_constraint_read = self.formset_constraint[self.form_state][0].get('read')
                self.formset_constraint_hide = self.formset_constraint[self.form_state][0].get('hide')
        super(OrderForm, self).__init__(*args, **kwargs)
        qs = Supplier.objects.filter(base_group='trade')
        self.fields['supplier_trade'] = forms.ModelChoiceField(
            queryset=qs,
            widget=forms.Select(attrs={'class': 'form-control'}),
            initial=self.instance.supplier_trade,  # or qs.first().pk if qs.first() else 0,
            required=False
        )
        self.fields['supplier_mac'] = forms.ModelChoiceField(
            queryset=qs,
            widget=forms.Select(attrs={'class': 'form-control'}),
            initial=self.instance.supplier_mac,  # or qs.first().pk if qs.first() else 0,
            required=False
        )
        self.fields['price_inquiry_result'] = PriceInquiryResultChoiceField(
            queryset=PriceInquiryResult.objects.filter(sku=self.instance.final_item, is_deleted=False, active=True),
            widget=forms.Select(attrs={'class': 'form-control'}),
            initial=self.instance.price_inquiry_result,  # or qs.first().pk if qs.first() else 0,
            required=False
        )
        self.fields['trade_commitment_date'] = JalaliDateField(label=_('trade_commitment_date'),
                                                      widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=False)
        self.fields['commitment_date_to_customer'] = JalaliDateField(label=_('commitment_date_to_customer'),
                                                      widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=False)
        self.make_hidden(['item', 'qi', 'item_trade', 'customer_party_id'])
        self.fields['description_sale'].widget.attrs['rows'] = 6
        self.fields['description_trade'].widget.attrs['rows'] = 3
        # self.fields['quantity_trade'].widget.attrs['value'] = self.instance.quantity_trade or self.instance.quantity

        if self.instance.cancel:
            self.make_disable(['quantity'])
        if self.instance.is_bazar:
            self.make_hidden(['transportation_method', 'order_type'])
        if self.request and self.request.user.base_group == 'trade':
            self.make_required(['price_trade'])

        illegal_order_ids = list(map(lambda x: x.pk, filter(lambda x: x.remaining_quantity < 0, Order.objects.filter(Q(pk__in=self.instance.order_base_items.all().values_list('order_rel', flat=True)) )))) if self.instance.pk else []
        ooqs = Order.objects.filter(~Q(id=self.instance.pk), item=self.instance.item, cancel=False).exclude(
            pk__in=illegal_order_ids) if self.instance.cancel else Order.objects.none()
        self.fields['order_m2m'] = forms.ModelMultipleChoiceField(
            queryset=ooqs,
            required=False,
            widget=FilteredSelectMultiple(_("order_order"), is_stacked=False),
        )
        # self.make_disable(['cancel'])
        if self.instance and self.instance.qi and not self.instance.production_lead_time:
            self.initial.update({'production_lead_time': self.instance.qi.lead_time_day})
            # self.fields['production_lead_time'].initial = self.instance.qi.lead_time_day

        if self.request and not self.request.user.is_superuser and self.form_constraint_read and '__all__' in self.form_constraint_read:
            self.make_disable(self.fields)

        elif self.request and not self.request.user.is_superuser:
            if self.form_constraint_hide:
                self.make_hidden(self.form_constraint_hide)
            if self.form_constraint_read:
                self.make_disable(self.form_constraint_read)
                if 'supplier_trade' in self.form_constraint_read:
                    self.fields['supplier_trade'].widget.attrs['disabled'] = "disabled"
            if self.formset_constraint_hide:
                self.make_hidden(self.formset_constraint_hide)
            if self.formset_constraint_read:
                self.make_disable(self.formset_constraint_read)

            if not self.access:
                self.make_disable(self.fields)
                self.enable = False

        if self.instance.cancel:
            self.make_disable(self.fields)


class BazarOrderForm(CustomBaseModelForm):
    has_comment = True

    class Meta:
        model = OrderBazar
        fields = ['item', 'quantity', 'description', 'cancel']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.make_hidden(['item'])
        self.fields['description'].widget.attrs['rows'] = 1


class PackingForm(CustomBaseModelForm):
    class Meta:
        model = Packing
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
        super(PackingForm, self).__init__(*args, **kwargs)
        # self.fields['pack_date'] = JalaliDateField(label=_('pack_date'),
        #                                            widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=True)
        self.fields['departure_date'].widget = forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
        self.fields['arrival_date'].widget = forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
        self.fields['arrive_to_wh_date'].widget = forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
        self.fields['estimated_delivery_date'].widget = forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
        self.fields['delivery_to_salehi_date'].widget = forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
        self.fields['cl_10_date'].widget = forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
        self.fields['cl_90_date'].widget = forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
        self.fields['cl_100_date'].widget = forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
        self.fields['description'].widget.attrs['rows'] = 3

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


class PackingItemForm(CustomBaseModelForm):
    class Meta:
        model = PackingItem
        exclude = ['group']

    def __init__(self, *args, **kwargs):
        request = kwargs['initial'].pop('request', None) if kwargs.get('initial') else None
        super(PackingItemForm, self).__init__(*args, **kwargs)
        self.make_hidden(['order'])
        self.fields['description'].widget.attrs['rows'] = 8
        # if self.instance.pk and (packing := self.initial.get('packing')):
        packing = self.initial.get('packing')
        if packing:
            self.fields['packing'].queryset = self.fields['packing'].queryset.filter(id=getattr(packing, 'pk', packing))

        if request and request.user.base_group == 'wh':
            # self.make_disable(['order'])
            self.make_hidden(['price'])
            self.make_readonly(
                [
                    'order',
                    'part_number',
                    'quantity',
                    'price',
                    'packing',
                    'carton_number',
                    'net_weight_kg',
                    'gross_weight_kg',
                    'size',
                    'brand',
                    'description',
                    'sales_conf',
                    'sales_conf_date',
                    'invoice_conf',
                    'invoice_conf_date',
                ]
            )

        if request and request.user.base_group == 'trade':
            self.make_hidden(['wh_receipt_quantity'])



class GIOForm(CustomBaseModelForm):
    class Meta:
        model = GIO
        exclude = ['group']

    def __init__(self, *args, **kwargs):
        # request = access = form_constraint = formset_constraint = form_constraint_read = form_constraint_hide = formset_constraint_read = formset_constraint_hide = None
        # if self.form_state is None:
        #     if kwargs.get('initial') and (c := kwargs.get('initial').get('constraint')):
        #         self.form_state = c.get('form_state')
        #     elif kwargs.get('constraint'):
        #         self.form_state = kwargs.get('constraint').get('form_state')
        #
        # if self.form_state is not None:
        #     if kwargs.get('initial') and (c := kwargs.get('initial').get('constraint')):
        #         form_constraint = c.pop('form_constraint')  # remove unnecessary kwargs
        #         formset_constraint = c.pop('formset_constraint')  # remove unnecessary kwargs
        #         request = c.pop('request')  # remove unnecessary kwargs
        #         access = c.get('wf_access')
        #     elif kwargs.get('constraint'):
        #         form_constraint = kwargs.get('constraint').get('form_constraint')
        #         formset_constraint = kwargs.get('constraint').get('formset_constraint')
        #         request = kwargs.get('constraint').get('request')
        #         access = kwargs.get('constraint').get('wf_access')
        #         kwargs.pop('constraint')  # remove unnecessary kwargs
        #     if form_constraint:
        #         form_constraint_read = form_constraint[self.form_state].get('read')
        #         form_constraint_hide = form_constraint[self.form_state].get('hide')
        #     if formset_constraint:
        #         formset_constraint_read = formset_constraint[self.form_state][0].get('read')
        #         formset_constraint_hide = formset_constraint[self.form_state][0].get('hide')
        super(GIOForm, self).__init__(*args, **kwargs)
        self.make_hidden(['sepidar_buy_factor_response_json'])
        if self.instance.pk:
            self.fields['quantity'].widget.attrs['onkeyup'] = 'check_gio_item_quantity_eq_to_qio()'
        # self.fields['gio_date'] = JalaliDateField(label=_('gio_date'),
        #                                            widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=True)

        self.fields['gio_date'] = forms.DateField(label=_('gio_date'),
                                                  widget=forms.DateInput(
                                                  attrs={'class': 'form-control', 'size': '10', 'type': 'date'}),
                                                  required=True)

        self.fields['description'].widget.attrs['rows'] = 1

        # if request and not request.user.is_superuser:
        #     if form_constraint_hide:
        #         self.make_hidden(form_constraint_hide)
        #     if form_constraint_read:
        #         self.make_disable(form_constraint_read)
        #     if formset_constraint_hide:
        #         self.make_hidden(formset_constraint_hide)
        #     if formset_constraint_read:
        #         self.make_disable(formset_constraint_read)

            # if not access:
            #     self.make_disable(self.fields)
            #     self.enable = False


class GIOItemForm(CustomBaseModelForm):
    class Meta:
        model = GIOItem
        exclude = ['group']

    def __init__(self, *args, **kwargs):
        super(GIOItemForm, self).__init__(*args, **kwargs)
        self.fields['quantity'].widget.attrs['onkeyup'] = 'check_gio_item_quantity_less_than_order(event)'
        self.make_hidden(['order'])
        self.fields['description'].widget.attrs['rows'] = 1
        # if self.instance.pk and (packing := self.initial.get('packing')):
        gio = self.initial.get('gio')
        if gio:
            self.fields['gio'].queryset = self.fields['gio'].queryset.filter(id=getattr(gio, 'pk', gio))
            self.make_hidden(['gio'])

GIOItemFormSet = formset_factory(GIOItemForm, extra=1)

class OrderPaymentForm(CustomBaseModelForm):
    file_model = File
    file_groups = 1

    class Meta:
        model = OrderPayment
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
                form_constraint_read = form_constraint[self.form_state][0].get('read')
                form_constraint_hide = form_constraint[self.form_state][0].get('hide')
            if formset_constraint:
                formset_constraint_read = formset_constraint[self.form_state][0].get('read')
                formset_constraint_hide = formset_constraint[self.form_state][0].get('hide')
        super(OrderPaymentForm, self).__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['currency'].widget.attrs.update({'onclick': 'prevent_change(event)'})
            self.fields['karmozd_currency'].widget.attrs.update({'onclick': 'prevent_change(event)'})
        qs = Supplier.objects.filter(base_group='trade', partyid__isnull=False, dlref__isnull=False)
        self.fields['vendor_party'] = forms.ModelChoiceField(
            queryset=qs,
            widget=forms.Select(attrs={'class': 'form-control'}),
            # initial=self.instance.vendor_party# or qs.first().pk if qs.first() else 0
        )
        # self.fields['from_date'] = JalaliDateField(label=_('from_date'),
        #                                            widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=True)
        # self.fields['to_date'] = JalaliDateField(label=_('to_date'),
        #                                            widget=AdminJalaliDateWidget(
        #                                                attrs={'class': 'jalali_date-date form-control', 'size': '10'}),
        #                                            required=False)
        self.fields['description'].widget.attrs['rows'] = 2

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


class OrderPaymentItemForm(CustomBaseModelForm):
    file_model = File
    file_groups = 1

    class Meta:
        model = OrderPaymentItem
        exclude = ['group']

        # widgets = {
        #     'payment': PaymentItemFormPaymentWidget,
        # }

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
                            formset_constraint_read = item.get('read')  # formset_constraint[self.form_state][0].get('read')
                            formset_constraint_hide = item.get('hide')  # formset_constraint[self.form_state][0].get('hide')
                else:
                    formset_constraint_read = formset_constraint[self.form_state][0].get('read')
                    formset_constraint_hide = formset_constraint[self.form_state][0].get('hide')
        super(OrderPaymentItemForm, self).__init__(*args, **kwargs)
        self.make_hidden(['order', 'payment'])
        self.fields['description'].widget.attrs['rows'] = 1
        self.fields['from_date'] = JalaliDateField(label=_('from_date'),
                                                   widget=AdminJalaliDateWidget(
                                                       attrs={'class': 'jalali_date-date form-control', 'size': '10', 'id': 'id_g_from_date'}),
                                                   required=False)
        self.fields['to_date'] = JalaliDateField(label=_('to_date'),
                                                   widget=AdminJalaliDateWidget(
                                                       attrs={'class': 'jalali_date-date form-control', 'size': '10', 'id': 'id_g_to_date'}),
                                                   required=False)

        payment = self.initial.get('packing')
        if payment:
            self.fields['payment'].queryset = self.fields['payment'].queryset.filter(id=getattr(payment, 'pk', payment))



order_payment_item_fields = ['order', 'payment', 'description', 'total_amount']

OrderPaymentItemFormSet = inlineformset_factory(
    parent_model=OrderPayment,
    model=OrderPaymentItem,
    form=OrderPaymentItemForm,
    extra=0,            # چندتا فرم خالی برای آیتم‌های جدید داشته باشه
    can_delete=True,
    fields=order_payment_item_fields
)


class BazarBuyFactorForm(CustomBaseForm):
    bazar_supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.filter(base_group='bazar', is_deleted=False),
        widget=autocomplete.ModelSelect2(url='inquiry:supplier-autocomplete', attrs={
                    'data-autocomplete-delay': 1000,
                }),
        label=_('supplier')
    )
    currency = forms.ChoiceField(label="currency_ref", initial='1')
    rate = forms.FloatField(label="Exchange Rate", initial=1)
    tax = forms.FloatField(label="Tax", required=False)
    discount = forms.FloatField(label="Discount", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # مقدار choices رو از مدل می‌خونیم: [(value, label), ...]
        self.fields['currency'].choices = [
            (str(c.sepidar_id), c.title) for c in Currency.objects.all()
        ]

        self.make_disable(['currency', 'rate'])
        self.fields['tax'].widget.attrs['onkeyup'] = 'calculate_price()'
        self.fields['discount'].widget.attrs['onkeyup'] = 'calculate_price()'


class BazarBuyFactorItemForm(CustomBaseForm):
    item = forms.IntegerField(label='item')
    portal_order_id = forms.IntegerField(widget=forms.HiddenInput, label='portal_order_id')
    itemref = forms.IntegerField(widget=forms.HiddenInput, label='itemref')
    price = forms.FloatField(label="Price", required=True)
    quantity = forms.IntegerField(label="Quantity", required=True)
    discount = forms.FloatField(label="discount", required=False)
    addition = forms.FloatField(label="Addition", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['addition'].widget.attrs['onkeyup'] = 'calculate_price()'


BazarPurchaseItemFormSet = formset_factory(BazarBuyFactorItemForm, extra=1)


class TradeBuyFactorForm(CustomBaseForm):
    trade_supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.all(),
        widget=autocomplete.ModelSelect2(url='inquiry:supplier-autocomplete')
    )
    currency = forms.ChoiceField(label="currency_ref", initial='1')
    rate = forms.FloatField(label="Exchange Rate", initial=1)
    tax = forms.FloatField(label="Tax", required=False)
    discount = forms.FloatField(label="Discount", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # مقدار choices رو از مدل می‌خونیم: [(value, label), ...]
        self.fields['currency'].choices = [
            (str(c.sepidar_id), c.title) for c in Currency.objects.all()
        ]

        self.make_disable(['currency', 'rate'])
        self.fields['tax'].widget.attrs['onkeyup'] = 'calculate_price()'
        self.fields['discount'].widget.attrs['onkeyup'] = 'calculate_price()'


class TradeBuyFactorItemForm(CustomBaseForm):
    item = forms.IntegerField(label='item')
    portal_order_id = forms.IntegerField(widget=forms.HiddenInput, label='portal_order_id')
    itemref = forms.IntegerField(widget=forms.HiddenInput, label='itemref')
    price = forms.FloatField(label="Price", required=True)
    quantity = forms.IntegerField(label="Quantity", required=True)
    discount = forms.FloatField(label="discount", required=False)
    addition = forms.FloatField(label="Addition", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['addition'].widget.attrs['onkeyup'] = 'calculate_price()'


TradePurchaseItemFormSet = formset_factory(TradeBuyFactorItemForm, extra=1)


class ACNTForm(CustomBaseModelForm):
    class Meta:
        model = ACNT
        exclude = ['group']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].widget.attrs['rows'] = 1


class OrderDelayReasonModelForm(CustomBaseModelForm):
    class Meta:
        model = OrderDelayReason
        fields = ['id', 'creator_user', 'editor_user', "order", "quantity",
                  "reason", "start", "start_date", "end", "end_date", "actor", "description", ]
