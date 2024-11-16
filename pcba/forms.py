from django import forms
from django.forms import inlineformset_factory
from jalali_date.fields import JalaliDateField
from jalali_date.widgets import AdminJalaliDateWidget
from django_select2 import forms as s2forms
from translator import get_text as _

from core.forms import CustomBaseModelForm
from .models import Contract, CustomerItemReceipt, ProjectItemList, ProductionDayActivities, ItemsInCustomerReceipt


class CustomerItemReceiptFormContractWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "contract_title__icontains",
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


class ProductionDayActivitiesFormCustomerWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "customer_party_id__title__icontains",
        "id__iexact",
    ]


class ContractForm(CustomBaseModelForm):

    class Meta:
        model = Contract
        fields = ['contract_title', 'customer_party_id', 'goods_code_fk', 'project_name_en', 'customer_board_count',
                  'customer_sheet_count', 'customer_total_board_count', 'first_setup_time', 'second_setup_time',
                  'pad_count', 'ic_pad_count', 'first_setup_cost', 'second_setup_cost', 'pad_cost', 'ic_pad_cost',
                  'total_cost', 'not_assembly_pad_count'
                  ]

    def __init__(self, *args, **kwargs):
        super(ContractForm, self).__init__(*args, **kwargs)
        self.make_hidden(['customer_party_id', 'goods_code_fk',])
        # self.select2(['customer', 'goods_code_fk'])
        # self.display_as_input(['customer', 'goods_code_fk'])
        # self.display_as_label(['customer', 'goods_code_fk'])
        # self.fields['customer'].name = 'customer'
        # self.fields['goods_code_fk'].name = 'goods_code_fk'


class ItemReceiptForm(CustomBaseModelForm):

    def __init__(self, *args, **kwargs):
        super(ItemReceiptForm, self).__init__(*args, **kwargs)
        self.fields['receipt_date'] = JalaliDateField(label=_('receipt_date'), widget=AdminJalaliDateWidget, required=False)
        self.fields['receipt_date'].widget.attrs.update(
            {'class': 'jalali_date-date form-control', 'placeholder': _('receipt_date'), 'required': False})
        # self.make_hidden(['parent', 'contract'])
        self.make_hidden(['goods_code_fk'])
        self.fields['goods_code_fk'].widget.attrs['id'] = 'id_goods_code_fk3'
        # self.fields['customer_item_receipt'].queryset = CustomerItemReceipt.objects.filter()

    class Meta:
        model = ItemsInCustomerReceipt
        exclude = ['group']


class CustomerItemReceiptForm(CustomBaseModelForm):

    def __init__(self, *args, **kwargs):
        contract = kwargs.pop('contract', None)
        super(CustomerItemReceiptForm, self).__init__(*args, **kwargs)
        if contract:
            self.fields['parent'].queryset = CustomerItemReceipt.objects.filter(contract_id=contract,
                                                                                status=CustomerItemReceipt.INCOMPLETE)
        self.fields['receipt_date'] = JalaliDateField(label=_('receipt_date'), widget=AdminJalaliDateWidget, required=False)
        self.fields['receipt_date'].widget.attrs.update(
            {'class': 'jalali_date-date form-control', 'placeholder': _('receipt_date'), 'required': False})

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
        }

    def __init__(self, *args, **kwargs):
        super(ProjectItemListForm, self).__init__(*args, **kwargs)
        self.fields['description'].widget.attrs['rows'] = 1
        self.make_hidden(['goods_code_fk'])
        self.fields['goods_code_fk'].widget.attrs['id'] = 'id_goods_code_fk2'


class ProductionDayActivitiesForm(CustomBaseModelForm):
    class Meta:
        model = ProductionDayActivities
        exclude = ['group']

        widgets = {
            'contract': ProjectItemListFormContractWidget,
            'goods_code_fk': ProjectItemListFormGoodsCodeWidget,
            'customer_party_id': ProductionDayActivitiesFormCustomerWidget,
        }

    def __init__(self, *args, **kwargs):
        super(ProductionDayActivitiesForm, self).__init__(*args, **kwargs)
        self.fields['production_date'] = JalaliDateField(label=_('production_date'), widget=AdminJalaliDateWidget,
                                                      required=False)
        self.fields['production_date'].widget.attrs.update(
            {'class': 'jalali_date-date form-control', 'placeholder': _('production_date'), 'required': False})