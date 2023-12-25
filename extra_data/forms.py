from core.forms import CustomBaseModelForm
from .models import ItemWeight
from django_select2 import forms as s2forms


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