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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = access = form_constraint = formset_constraint = form_constraint_read = form_constraint_hide = formset_constraint_read = formset_constraint_hide = None
        if kwargs.get('initial') and (c := kwargs.get('initial').get('constraint')):
            request = access = c.get('request')

        if request and not request.user.is_superuser:
            self.make_disable(self.fields)


