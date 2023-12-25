from django import forms
from django_select2 import forms as s2forms

from files.models import Image, File
from .models import Receipt, ReceiptDetail

from jalali_date.fields import JalaliDateField
from jalali_date.widgets import AdminJalaliDateWidget
from translator import get_text as _

from core.forms import CustomBaseModelForm


class ReceiptCreateForm2(CustomBaseModelForm):
    image_groups = 1
    image_model = Image
    file_model = File
    crispy = False
    state = ['None', 'dddd']

    class Meta:
        model = Receipt
        exclude = ['group']

        widgets = {
            'description': forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super(ReceiptCreateForm2, self).__init__(*args, **kwargs)
        self.fields['register_date'] = JalaliDateField(label=_('register_date'),
                                                       widget=AdminJalaliDateWidget, required=False)
        print(self.initial)
        self.make_optional(['image_1'])
        try:
            permission_access = kwargs.get('initial').get('permission_access')
            # self.set_field_level_permission(permission_access.get('fields'), permission_access.get('action'))
            self.set_field_level_permission(permission_access)
        except Exception as e:
            print('error: ', __name__, 'line',  e.__traceback__.tb_lineno, e)

        if not self.initial.get('wf_access'):
            self.make_disable(self.fields)
            self.enable = False


class ReceiptDetailWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "pack_number__icontains",
    ]


class ReceiptDetailSKUWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "sku__icontains",
    ]


class ReceiptDetailCreateForm2(CustomBaseModelForm):
    image_groups = 2
    file_groups = 1
    image_model = Image
    file_model = File
    crispy = False

    class Meta:
        model = ReceiptDetail
        exclude = ['group']

        widgets = {
            'description': forms.Textarea(attrs={"rows": 2}),
            'receipt_id': ReceiptDetailWidget,
            # 'sku': ReceiptDetailSKUWidget,
            'sku': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['register_date'] = JalaliDateField(label=_('register_date'),
                                                       widget=AdminJalaliDateWidget, required=False)

        self.make_optional(['image_1', 'image_2', 'file_1'])
        # try:
        #     permission_access = kwargs.get('initial').get('permission_access')
        #     self.set_field_level_permission(permission_access.get('fields'), permission_access.get('action'))
        # except Exception as e:
        #     print('error: ', __name__, 'line',  e.__traceback__.tb_lineno, e)
