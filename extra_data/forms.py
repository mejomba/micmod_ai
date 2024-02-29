from core.forms import CustomBaseModelForm
from .models import ItemWeight
from django_select2 import forms as s2forms
from django import forms
from tools.utils import c_get

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
        # self.make_hidden(['sku'])