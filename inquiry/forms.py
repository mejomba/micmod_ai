from django import forms
from core.forms import CustomBaseModelForm
from files.models import File, Image
from tools.utils import show_error
from .models import PriceInquiryFile, PriceInquiryResult, SalesPriceInqueryLog, InquiryResult
from extra_data.models import Item

from translator import get_text as _

from django_select2 import forms as s2forms


class SkuCreateForm(CustomBaseModelForm):
    image_groups = 2
    file_groups = 1
    image_model = Image
    file_model = File
    has_file = True
    has_image = True
    crispy = True

    class Meta:
        model = Item
        exclude = ['group']

    def __init__(self, *args, **kwargs):
        kwargs.pop('constraint')
        super().__init__(*args, **kwargs)

        self.make_optional(['brand', 'quality', 'sale_group',
                            'purchase_group', 'customs_group',
                            'package', 'batch_type', 'batch_count',
                            'image_1', 'image_2', 'file_1'])

        try:
            initial = kwargs.get('initial')
            if initial:
                permission_access = initial.get('permission_access')
                # self.set_field_level_permission(permission_access.get('fields'), permission_access.get('action'))
                self.set_field_level_permission(permission_access)
        except Exception as e:
            print(e)

        if not self.initial.get('create') and not self.initial.get('wf_access'):
            self.make_disable(self.fields)
            self.enable = False

    def save(self, commit=True):
        return super().save(commit=True)


class PriceInquiryFileSKUWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "sku__icontains",
        "part_number__icontains",
    ]


class PriceInquiryFileCreateForm(CustomBaseModelForm):
    crispy = True
    image_groups = 1
    image_model = Image

    class Meta:
        model = PriceInquiryFile
        exclude = ['group']

        widgets = {
            'item': PriceInquiryFileSKUWidget,
        }

    def __init__(self, *args, **kwargs):
        try:
            kwargs.pop('constraint')
            print("sdfsdf cons")
        except:
            print('err cons')
        super(PriceInquiryFileCreateForm, self).__init__(*args, **kwargs)
        self.make_optional(['image_1'])


class PriceInquiryResultCreateForm(CustomBaseModelForm):
    image_groups = 1
    file_groups = 1
    image_model = Image
    file_model = File
    update_price = forms.BooleanField(widget=forms.CheckboxInput(), label=_('update_price'), required=False)

    class Meta:
        model = PriceInquiryResult
        exclude = ['group','price_update_date']

        widgets = {
            'sku': PriceInquiryFileSKUWidget,
        }
        
    def __init__(self, *args, **kwargs):
        # kwargs.pop('constraint')
        super(PriceInquiryResultCreateForm, self).__init__(*args, **kwargs)
        self.make_optional(['image_1', 'file_1'])
        self.make_hidden(['price_inquiry_file'])
        self.fields['active'].initial = True

        try:
            initial = kwargs.get('initial')
            print(__file__, 'initial in formset ===== ', initial)
            if initial:
                permission_access = initial.get('permission_access')
                # self.set_field_level_permission(permission_access.get('fields'), permission_access.get('action'))
                self.set_field_level_permission(initial)
        except Exception as e:
            show_error(e, __file__)


class SalesPriceInqueryLogForm(CustomBaseModelForm):
    sku_c = forms.CharField(max_length=100, label=_('sku'))

    class Meta:
        model = SalesPriceInqueryLog
        fields = ['sku_c', 'sku', 'party_code', 'quantity', 'grade', 'payment_method', 'currency', 'price_setting']
        # widgets = {
        #     'sku': PriceInquiryFileSKUWidget,
        # }

    def __init__(self, *args, **kwargs):
        super(SalesPriceInqueryLogForm, self).__init__(*args, **kwargs)
        self.fields['sku'].widget = forms.HiddenInput()
        self.fields['payment_method'] = forms.ChoiceField(widget=forms.Select(attrs={'class': 'form-control'}))
        self.fields['grade'] = forms.ChoiceField(widget=forms.Select(attrs={'class': 'form-control'}))
        for field in self.fields.values():
            field.widget.attrs['onchange'] = "refresh_data(event)"



class InquiryResultForm(CustomBaseModelForm):

    class Meta:
        model = InquiryResult
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(InquiryResultForm, self).__init__(*args, **kwargs)
