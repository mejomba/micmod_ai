from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.db.models import Q
from jalali_date.fields import JalaliDateField
from jalali_date.widgets import AdminJalaliDateWidget

from files.models import File
from inquiry.models import Supplier
from micmod_base.base import Currency
from translator import get_text as _

from core.forms import CustomBaseModelForm, CustomBaseForm
from order.models import Order, OrderOrder, Packing, PackingItem, GIO, GIOItem, OrderPayment, OrderPaymentItem, ACNT
from dal import autocomplete


class OrderForm(CustomBaseModelForm):
    has_comment = True

    class Meta:
        model = Order
        exclude = ['group', 'last_work_flow']

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
        self.fields['trade_commitment_date'] = JalaliDateField(label=_('request_date'),
                                                      widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=False)
        self.fields['commitment_date_to_customer'] = JalaliDateField(label=_('request_date'),
                                                      widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=False)
        self.make_hidden(['item', 'qi', 'item_trade'])
        self.fields['description_sale'].widget.attrs['rows'] = 6
        self.fields['description_trade'].widget.attrs['rows'] = 3
        # self.fields['quantity_trade'].widget.attrs['value'] = self.instance.quantity_trade or self.instance.quantity

        if self.instance.cancel:
            self.make_disable(['quantity'])
        if self.instance.is_bazar:
            self.make_hidden(['transportation_method', 'order_type'])
        if request and request.user.base_group == 'trade':
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

        if request and not request.user.is_superuser and '__all__' in form_constraint_read:
            self.make_disable(self.fields)

        elif request and not request.user.is_superuser:
            if form_constraint_hide:
                self.make_hidden(form_constraint_hide)
            if form_constraint_read:
                self.make_disable(form_constraint_read)
                if 'supplier_trade' in form_constraint_read:
                    self.fields['supplier_trade'].widget.attrs['disabled'] = "disabled"
            if formset_constraint_hide:
                self.make_hidden(formset_constraint_hide)
            if formset_constraint_read:
                self.make_disable(formset_constraint_read)

            if not access:
                self.make_disable(self.fields)
                self.enable = False

        if self.instance.cancel:
            self.make_disable(self.fields)

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


class PackingItemForm(CustomBaseModelForm):
    class Meta:
        model = PackingItem
        exclude = ['group']

    def __init__(self, *args, **kwargs):
        super(PackingItemForm, self).__init__(*args, **kwargs)
        self.make_hidden(['order'])
        self.fields['description'].widget.attrs['rows'] = 8
        # if self.instance.pk and (packing := self.initial.get('packing')):
        packing = self.initial.get('packing')
        if packing:
            self.fields['packing'].queryset = self.fields['packing'].queryset.filter(id=getattr(packing, 'pk', packing))


class GIOForm(CustomBaseModelForm):
    class Meta:
        model = GIO
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
        super(GIOForm, self).__init__(*args, **kwargs)
        # self.fields['gio_date'] = JalaliDateField(label=_('gio_date'),
        #                                            widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=True)

        self.fields['gio_date'] = forms.DateField(label=_('gio_date'),
                                                  widget=forms.DateInput(
                                                  attrs={'class': 'form-control', 'size': '10', 'type': 'date'}),
                                                  required=True)

        self.fields['description'].widget.attrs['rows'] = 1

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


class GIOItemForm(CustomBaseModelForm):
    class Meta:
        model = GIOItem
        exclude = ['group']

    def __init__(self, *args, **kwargs):
        super(GIOItemForm, self).__init__(*args, **kwargs)
        self.make_hidden(['order'])
        self.fields['description'].widget.attrs['rows'] = 1
        # if self.instance.pk and (packing := self.initial.get('packing')):
        gio = self.initial.get('gio')
        if gio:
            self.fields['gio'].queryset = self.fields['gio'].queryset.filter(id=getattr(gio, 'pk', gio))
            self.make_hidden(['gio'])


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


from django.forms import inlineformset_factory, formset_factory
from .models import OrderPayment, OrderPaymentItem

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
