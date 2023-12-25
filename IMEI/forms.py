import datetime

from django import forms
from jalali_date import datetime2jalali
from jalali_date.fields import SplitJalaliDateTimeField, JalaliDateField
from jalali_date.widgets import AdminSplitJalaliDateTime, AdminJalaliDateWidget

from translator import get_text as _

from .models import *
from django.forms import BaseInlineFormSet
from core.forms import CustomBaseModelForm

class IMEIListRegFrm(CustomBaseModelForm):
    crispy = True
    CHOICES = [
        ('1', _('update-items')),
        ('2', _('ignore-items'))
    ]
    action = forms.CharField(label='select option',
                             widget=forms.RadioSelect(choices=CHOICES)
                             )

    class Meta:
        model = IMEIListReg
        # fields = '__all__'
        exclude = ['creator_user', 'editor_user', 'title', 'group']

        widgets = {
            'description': forms.Textarea(attrs={"rows": 1}),
        }

    def __init__(self, *args, **kwargs):
        super(IMEIListRegFrm, self).__init__(*args, **kwargs)
        self.fields['register_date'] = JalaliDateField(label=_('register_date'),
                                                      widget=AdminJalaliDateWidget, required=False
                                                      )
        self.fields['source_file'].label = _('upload excel file')


class IMEIINTSWRegForm(forms.ModelForm):
    CHOICES = [
        ('1', _('update-items')),
        ('2', _('ignore-items'))
    ]
    action = forms.CharField(label='select option',
                             widget=forms.RadioSelect(choices=CHOICES,
                                                      # attrs={'checked': 'on'}
                                                      )
                             )

    class Meta:
        model = IMEINTSWReg
        exclude = ['creator_user', 'editor_user', 'title', 'group']

        widgets = {
            'description': forms.Textarea(attrs={"rows": 1}),
        }

    def __init__(self, *args, **kwargs):
        super(IMEIINTSWRegForm, self).__init__(*args, **kwargs)
        self.fields['register_date'] = JalaliDateField(label=_('register_date'),
                                                      widget=AdminJalaliDateWidget, required=False
                                                      )
        self.fields['source_file'].label = _('upload excel file')


class IMEISaleRegForm(forms.ModelForm):
    CHOICES = [
        ('1', _('update-items')),
        ('2', _('ignore-items'))
    ]
    action = forms.CharField(label='select option',
                             widget=forms.RadioSelect(choices=CHOICES),required=False
                             )

    class Meta:
        model = IMEISaleReg
        exclude = ['creator_user', 'editor_user', 'title', 'group', 'code', 'invoice_year', 'customer_name']

        widgets = {
            'description': forms.Textarea(attrs={"rows": 1}),
            'pack_numbers': forms.Textarea(attrs={'rows': 3}),
            'warning': forms.Textarea(attrs={'rows': 2, 'readonly': 'True'})
        }

    def __init__(self, *args, **kwargs):
        super(IMEISaleRegForm, self).__init__(*args, **kwargs)
        # self.fields['register_date'] = JalaliDateField(label=_('register_date'),
        #                                                widget=AdminJalaliDateWidget, required=False
        #                                               )
        self.fields['invoice_date'] = JalaliDateField(label=_('invoice_date'),
                                                       widget=AdminJalaliDateWidget, required=True
                                                       )
        self.fields['source_file'].label = _('upload excel file')
        self.fields['pack_numbers'].widget.attrs['class'] = 'LTR'


class IMEIErrRegForm(forms.ModelForm):

    class Meta:
        model = IMEIErrReg
        exclude = ['creator_user', 'editor_user', 'title', 'group']
