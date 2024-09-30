from django import forms
from jalali_date.fields import JalaliDateField
from jalali_date.widgets import AdminJalaliDateWidget
from translator import get_text as _

from core.forms import CustomBaseModelForm
from order.models import Order


class OrderForm(CustomBaseModelForm):
    class Meta:
        model = Order
        exclude = ['group']

    def __init__(self, *args, **kwargs):
        super(OrderForm, self).__init__(*args, **kwargs)
        self.fields['trade_commitment_date'] = JalaliDateField(label=_('request_date'),
                                                      widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=False)
        self.fields['commitment_date_to_customer'] = JalaliDateField(label=_('request_date'),
                                                      widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=False)
        # self.select2(['item'])
        # self.select2(['customer'])
        self.make_hidden(['customer', 'item'])
