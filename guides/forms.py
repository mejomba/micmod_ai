from django import forms

from core.forms import CustomBaseModelForm
from files.models import File
from guides.models import Guides


class GuidesForm(CustomBaseModelForm):
    file_groups = 1
    file_model = File
    has_file = True
    file_upload_type = True

    class Meta:
        model = Guides
        exclude = ['group']
        widgets = {
            'description': forms.Textarea(attrs={"rows": 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        allowed_type = [
            "quotation",
            "payment_order",
            "shenasname_farayand",
        ]

        request = access = form_constraint = formset_constraint = form_constraint_read = form_constraint_hide = formset_constraint_read = formset_constraint_hide = None
        if kwargs.get('initial') and (c := kwargs.get('initial').get('constraint')):
            request = access = c.get('request')

        if request:
            if not request.user.is_superuser:
                self.make_disable(self.fields)

            #  filter doc type
            doc_type = request.GET.get('type')

            if doc_type == 'shenasname_farayand':
                allowed_type = ["shenasname_farayand"]
            else:
                allowed_type = [
                    "quotation",
                    "payment_order",
                    "inquiry",
                    "factor",
                    "order"
                ]

            self.fields['section_id'].choices = [
                choice for choice in self.fields['section_id'].choices if choice[0] in allowed_type
            ]




