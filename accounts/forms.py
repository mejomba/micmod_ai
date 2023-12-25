from django_select2 import forms as s2forms
from django import forms

from core.forms import CustomBaseModelForm
from .models import ManageFormField
from .extra_models import Profile


class RelatedModelWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "app_label__icontains",
    ]


class ManageFormFieldAdminForm(forms.ModelForm):
    class Meta:
        model = ManageFormField
        fields = ['title', 'content_type', 'fields_name', 'allowed_groups', 'action']

        widgets = {
            'content_type': RelatedModelWidget,
        }

        # field = [f.name for f in model._meta.get_fields()]
        # print(field)

class ProfileForm(CustomBaseModelForm):
    class Meta:
        model = Profile
        fields = '__all__'
