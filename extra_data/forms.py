from jalali_date.fields import JalaliDateField
from jalali_date.widgets import AdminJalaliDateWidget

from core.forms import CustomBaseModelForm
from .models import ItemWeight, PurchaseGroup, HS, Customer
from django_select2 import forms as s2forms
from django import forms
from tools.utils import c_get
from translator import get_text as _


class SKUWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "item__icontains",
        # "item__part_number__icontains",
    ]


class ItemWeightForm(CustomBaseModelForm):
    class Meta:
        model = ItemWeight
        fields = ['sku','weight',]
        # widgets = {
        #     'item': SKUWidget,
        # }

    def __init__(self,*args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['sku_c'] = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}), required=False)
        # self.fields['sku_c'].initial = self.instance.sku.c_get('sku')
        self.make_hidden(['sku'])


class PurchaseGroupForm(CustomBaseModelForm):
    class Meta:
        model = PurchaseGroup
        fields = '__all__'


class HsForm(CustomBaseModelForm):
    class Meta:
        model = HS
        fields = '__all__'


class CustomerForm(CustomBaseModelForm):
    class Meta:
        model = Customer
        fields = '__all__'# ['title', 'type', 'national_code', 'name', 'last_name', 'email', 'website', 'phone', 'mobile',
                  # 'max_credit', 'customer_group', 'province', 'location', 'address', 'senf', 'sub_senf',
                  # 'introduction_method', 'introducer', 'marketer', 'revival_date', 'sepidar_dl_id']

    def __init__(self, *args, **kwargs):
        access = None
        super().__init__(*args, **kwargs)
    #
    #     self.fields['revival_date'] = JalaliDateField(lable=_('revival_date'), widget=AdminJalaliDateWidget(
    #                                   attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=True)
    #
    #     if not access:
    #         self.make_disable(fields=self.fields)
    #
    #     self.make_optional(['introduction_method'])
    #     self.make_optional(['introducer'])
    #     self.select2(['sepidar_dl_id'])
