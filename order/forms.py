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
        super(OrderForm, self).__init__(*args, **kwargs)
        self.fields['trade_commitment_date'] = JalaliDateField(label=_('request_date'),
                                                      widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=False)
        self.fields['commitment_date_to_customer'] = JalaliDateField(label=_('request_date'),
                                                      widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=False)
        self.make_hidden(['item', 'qi'])
        self.fields['description_sale'].widget.attrs['rows'] = 10

        self.fields['order_m2m'] = forms.ModelMultipleChoiceField(
            queryset=Order.objects.filter(~Q(id=self.instance.pk), item=self.instance.item, cancel=False),
            required=False,
            widget=FilteredSelectMultiple(_("order_order"), is_stacked=False),
        )
