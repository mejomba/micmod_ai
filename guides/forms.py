from django import forms

from core.forms import CustomBaseModelForm
from files.models import File
from guides.models import Guides


class GuidesForm(CustomBaseModelForm):
    file_groups = 1
    file_model = File
    has_file = True

    class Meta:
        model = Guides
        exclude = ['group']
        widgets = {
            'description': forms.Textarea(attrs={"rows": 1}),
        }

