from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.db.models import Q
from jalali_date.fields import JalaliDateField
from jalali_date.widgets import AdminJalaliDateWidget

from files.models import File
from inquiry.models import Supplier
from translator import get_text as _

from core.forms import CustomBaseModelForm
from order.models import Order, OrderOrder, Packing, PackingItem, GIO, GIOItem, OrderPayment, OrderPaymentItem


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
        self.fields['gio_date'] = JalaliDateField(label=_('gio_date'),
                                                   widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=True)
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


class OrderPaymentForm(CustomBaseModelForm):
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
                form_constraint_read = form_constraint[self.form_state].get('read')
                form_constraint_hide = form_constraint[self.form_state].get('hide')
            if formset_constraint:
                formset_constraint_read = formset_constraint[self.form_state][0].get('read')
                formset_constraint_hide = formset_constraint[self.form_state][0].get('hide')
        super(OrderPaymentForm, self).__init__(*args, **kwargs)
        self.fields['from_date'] = JalaliDateField(label=_('from_date'),
                                                   widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=True)
        self.fields['to_date'] = JalaliDateField(label=_('to_date'),
                                                   widget=AdminJalaliDateWidget(
                                                       attrs={'class': 'jalali_date-date form-control', 'size': '10'}),
                                                   required=False)
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
        super(OrderPaymentItemForm, self).__init__(*args, **kwargs)
        self.make_hidden(['order', 'payment'])
        self.fields['description'].widget.attrs['rows'] = 6
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