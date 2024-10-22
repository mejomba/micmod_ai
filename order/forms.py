from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.db.models import Q
from jalali_date.fields import JalaliDateField
from jalali_date.widgets import AdminJalaliDateWidget
from translator import get_text as _

from core.forms import CustomBaseModelForm
from order.models import Order, OrderOrder


class OrderForm(CustomBaseModelForm):
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
        self.fields['trade_commitment_date'] = JalaliDateField(label=_('request_date'),
                                                      widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=False)
        self.fields['commitment_date_to_customer'] = JalaliDateField(label=_('request_date'),
                                                      widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=False)
        self.make_hidden(['item', 'qi'])
        self.fields['description_sale'].widget.attrs['rows'] = 10

        # ~Q(id=self.instance.pk), item = self.instance.item, cancel = False

        # self.instance.order_base_items.all().values_list('order_rel', flat=True)
        illegal_order_ids = list(map(lambda x: x.pk, filter(lambda x: x.remaining_quantity <= 0, Order.objects.filter(pk__in=self.instance.order_base_items.all().values_list('order_rel', flat=True))))) if self.instance.pk else []
        ooqs = Order.objects.filter(~Q(id=self.instance.pk), item=self.instance.item, cancel=False).exclude(
            pk__in=illegal_order_ids) if self.instance.cancel else Order.objects.none()
        self.fields['order_m2m'] = forms.ModelMultipleChoiceField(
            queryset=ooqs,
            required=False,
            widget=FilteredSelectMultiple(_("order_order"), is_stacked=False),
        )

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
