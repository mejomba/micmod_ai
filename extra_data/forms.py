from django.contrib.admin.widgets import FilteredSelectMultiple
from jalali_date.fields import JalaliDateField, JalaliDateTimeField
from jalali_date.widgets import AdminJalaliDateWidget

from core.forms import CustomBaseModelForm
from files.models import Image, File
from .models import ItemWeight, PurchaseGroup, HS, Customer, CustomerDocuments, ChangeCustomerGroup, CustomerExpert, \
    CustomerFields, CustomerContract, ItemPackage, AccountingUser
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
        fields = ['title', 'type', 'national_code', 'name', 'last_name', 'email', 'website', 'phone', 'customer_field',
                  'province', 'location', 'address', 'senf', 'sub_senf', 'active', 'revival_date', 'black_list',
                  'introduction_method', 'introducer', 'marketer', 'description', 'lat', 'long', 'meet_in_person',
                  'z_no', 'z_cheque_ns', 'z_cheque_s', 'z_safte', 'z_max_credit_rafi', 'cheque_to_delivery',
                  'extra_credit', 'i_type1_target', 'customer_sale_type', 'official_name', 'customer_grade', 'accounting_user',
                  'risk_status']

    def __init__(self, *args, **kwargs):
        access = None
        super().__init__(*args, **kwargs)
        self.fields['description'].widget.attrs['rows'] = 1
        self.fields['customer_field'] = forms.ModelMultipleChoiceField(
            queryset=CustomerFields.objects.all(),
            required=False,
            widget=FilteredSelectMultiple(_("customer field"), is_stacked=False),
        )

        self.fields['revival_date'] = JalaliDateField(widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=False)

        self.fields['z_safte'].widget = forms.TextInput(attrs={'class': 'form-control comma-seperator text-left LTR-RTL'})
        self.fields['z_cheque_s'].widget = forms.TextInput(attrs={'class': 'form-control comma-seperator text-left LTR-RTL'})
        self.fields['z_cheque_ns'].widget = forms.TextInput(attrs={'class': 'form-control comma-seperator text-left LTR-RTL'})
        self.fields['z_max_credit_rafi'].widget = forms.TextInput(attrs={'class': 'form-control comma-seperator text-left LTR-RTL'})
        self.fields['extra_credit'].widget = forms.TextInput(attrs={'class': 'form-control comma-seperator text-left LTR-RTL'})

    #
    #     if not access:
    #         self.make_disable(fields=self.fields)
    #
    #     self.make_optional(['introduction_method'])
    #     self.make_optional(['introducer'])
    #     self.select2(['sepidar_dl_id'])


class CustomerDocumentsFormCustomerWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "title__icontains",
        "name__icontains",
        "last_name__icontains",
        "sepidar_party_id__icontains",
        "sepidar_dl_id__icontains",
        "sepidar_dl_code__icontains",
        "id__iexact",
    ]


class CustomerDocumentsForm(CustomBaseModelForm):
    image_model = Image
    image_groups = 1

    class Meta:
        model = CustomerDocuments
        fields = '__all__'

        widgets = {
            'customer': CustomerDocumentsFormCustomerWidget,
        }

    def __init__(self, *args, **kwargs):
        access = None
        super().__init__(*args, **kwargs)
        self.fields['description'].widget.attrs['rows'] = 1
        self.fields['image_1'].widget.attrs['required'] = True


class ChangeCustomerGroupWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "title__icontains",
        "name__icontains",
        "last_name__icontains",
        "sepidar_party_id__icontains",
        "sepidar_dl_id__icontains",
        "sepidar_dl_code__icontains",
        "id__iexact",
    ]


class ChangeCustomerGroupMarketerWidget2(s2forms.ModelSelect2Widget):
    search_fields = [
        "title__icontains",
    ]


class ChangeCustomerGroupForm(CustomBaseModelForm):
    class Meta:
        model = ChangeCustomerGroup
        fields = '__all__'

        widgets = {
            'customer': ChangeCustomerGroupWidget,
            # 'from_marketer': ChangeCustomerGroupMarketerWidget2,
            # 'to_marketer': ChangeCustomerGroupMarketerWidget2,
        }

    def __init__(self, *args, **kwargs):
        access = None
        super().__init__(*args, **kwargs)
        self.make_hidden(['from_marketer'])


class CustomerExpertForm(CustomBaseModelForm):
    class Meta:
        model = CustomerExpert
        fields = '__all__'

        widgets = {
            'customer': ChangeCustomerGroupWidget,
        }

    def __init__(self, *args, **kwargs):
        access = None
        super().__init__(*args, **kwargs)


class CustomerContractForm(CustomBaseModelForm):
    file_groups = 1
    file_model = File
    class Meta:
        model = CustomerContract
        fields = '__all__'

        widgets = {
            'customer': ChangeCustomerGroupWidget,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['contract_date'] = JalaliDateField(widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=True)
        self.fields['contract_due_date'] = JalaliDateField(widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'}), required=True)
        self.fields['description'].widget.attrs.update({'rows': 2})


class ItemPackageForm(CustomBaseModelForm):
    class Meta:
        model = ItemPackage
        exclude = ['group']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].widget.attrs.update({'rows': 1})


class AccountingUserForm(CustomBaseModelForm):

    class Meta:
        model = AccountingUser
        exclude = ['group']

    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
