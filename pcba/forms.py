from django import forms
from django.forms import inlineformset_factory
from jalali_date.fields import JalaliDateField
from jalali_date.widgets import AdminJalaliDateWidget
from django_select2 import forms as s2forms
from translator import get_text as _

from core.forms import CustomBaseModelForm
from .models import Contract, CustomerItemReceipt, ProjectItemList


class CustomerItemReceiptFormContractWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "contract_title__icontains",
        # "name__icontains",
        # "last_name__icontains",
        # "sepidar_party_id__icontains",
        # "sepidar_dl_id__icontains",
        # "sepidar_dl_code__icontains",
        "id__iexact",
    ]


class ProjectItemListFormContractWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "contract_title__icontains",
        "id__iexact",
    ]


class ProjectItemListFormGoodsCodeWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "sku__icontains",
        "id__iexact",
    ]


class ContractForm(CustomBaseModelForm):

    class Meta:
        model = Contract
        fields = ['contract_title', 'customer_party_id', 'goods_code_fk', 'project_name_en', 'customer_board_count',
                  'customer_sheet_count', 'customer_total_board_count', 'first_setup_time', 'second_setup_time',
                  'pad_count', 'ic_pad_count', 'first_setup_cost', 'second_setup_cost', 'pad_cost', 'ic_pad_cost',
                  'total_cost'
                  ]

    def __init__(self, *args, **kwargs):
        super(ContractForm, self).__init__(*args, **kwargs)
        self.make_hidden(['customer_party_id', 'goods_code_fk',])
        # self.select2(['customer', 'goods_code_fk'])
        # self.display_as_input(['customer', 'goods_code_fk'])
        # self.display_as_label(['customer', 'goods_code_fk'])
        # self.fields['customer'].name = 'customer'
        # self.fields['goods_code_fk'].name = 'goods_code_fk'


class CustomerItemReceiptForm(CustomBaseModelForm):

    def __init__(self, *args, **kwargs):
        super(CustomerItemReceiptForm, self).__init__(*args, **kwargs)
        self.fields['receipt_date'] = JalaliDateField(label=_('receipt_date'), widget=AdminJalaliDateWidget, required=False)
        self.fields['receipt_date'].widget.attrs.update(
            {'class': 'jalali_date-date form-control', 'placeholder': _('receipt_date'), 'required': False})
        # self.make_hidden(['parent', 'contract'])

    class Meta:
        model = CustomerItemReceipt
        exclude = ['group']

        widgets = {
            'contract': CustomerItemReceiptFormContractWidget,
        }


class ProjectItemListForm(CustomBaseModelForm):

    class Meta:
        model = ProjectItemList
        exclude = ['group']

        widgets = {
            'contract': ProjectItemListFormContractWidget,
            # 'goods_code_fk': ProjectItemListFormGoodsCodeWidget,
        }

    def __init__(self, *args, **kwargs):
        super(ProjectItemListForm, self).__init__(*args, **kwargs)
        self.fields['description'].widget.attrs['rows'] = 1
        self.fields['goods_code_fk'].widget.attrs['id'] = 'id_goods_code_fk2'

        self.make_hidden(['goods_code_fk'])

#
# project_items_fields = ['contract', 'goods_code_fk', 'part_number', 'quantity', 'description',]
#
# ProjectItemListFormset = inlineformset_factory(
#     Contract,
#     ProjectItemList,
#     form=ProjectItemListForm,
#     extra=2,
#     fields=project_items_fields,
#
# )