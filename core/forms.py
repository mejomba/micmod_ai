
from django import forms
from django.forms import DateInput
from django.forms.widgets import CheckboxInput, FileInput, DateTimeInput
from jalali_date.widgets import AdminJalaliDateWidget, AdminSplitJalaliDateTime

from files.models import UploadType
from tools.utils import show_error
from translator import get_text as _

from typing import List

from jalali_date.fields import JalaliDateField, JalaliDateTimeField


class CustomBaseForm(forms.Form):
    image_groups = None
    file_groups = None


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields:
            if not isinstance(self.fields[field].widget, CheckboxInput):
                self.fields[field].widget.attrs['class'] = 'form-control'
            if isinstance(self.fields[field].widget, DateTimeInput):
                self.fields[field] = JalaliDateField(label=_(field), widget=AdminJalaliDateWidget, required=True)

    # def make_optional(self, fields: List):
    #     for f in fields:
    #         self.fields[f].required = False

    def make_disable(self, fields: List):
        for field_name, field in self.fields.items():
            if field_name in fields:
                field.disabled = True

class CustomBaseModelForm(forms.ModelForm):
    image_groups = None
    file_groups = None
    image_model = None
    file_model = None
    has_comment = None
    has_addition = None
    has_payment = None
    crispy = None
    action = None
    enable = True
    form_state = None
    change_data_for_validation = False
    image_upload_type = False
    file_upload_type = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.image_groups:
            for idx in range(1, self.image_groups + 1):
                self.fields['image_{idx}'.format(idx=idx)] = forms.ImageField(widget=forms.FileInput(attrs={'multiple': 'off'}),
                                                                              label=f' تصاویر گروه{idx}', required=False)
                if self.image_upload_type:
                    self.fields['image_{idx}_upload_type'.format(idx=idx)] = forms.ModelChoiceField(
                        queryset=UploadType.objects.all(),
                        required=False,
                        empty_label=f""
                    )

        if self.file_groups:
            for idx in range(1, self.file_groups + 1):
                self.fields[f'file_{idx}'] = forms.FileField(widget=forms.FileInput(attrs={'multiple': 'on', 'accept': 'file'}),
                                                             label=f' فایل(ها) پیوست{idx}', required=False)
                if self.file_upload_type:
                    self.fields['file_{idx}_upload_type'.format(idx=idx)] = forms.ModelChoiceField(
                        queryset=UploadType.objects.all(),
                        required=False,
                        empty_label="---"
                    )

        for field in self.fields:
            if not isinstance(self.fields[field].widget, CheckboxInput):
                self.fields[field].widget.attrs['class'] = 'form-control'
            # if isinstance(self.fields[field].widget, (DateTimeInput, DateInput)):
            if isinstance(self.fields[field].widget, DateTimeInput):
                # self.fields[field] = JalaliDateField(label=_(field), widget=AdminJalaliDateWidget, required=True)
                self.fields[field] = JalaliDateField(label=_(field), widget=AdminJalaliDateWidget, required=False)
            if isinstance(self.fields[field].widget, DateInput):
                self.fields[field] = JalaliDateField(label=_(field), widget=AdminJalaliDateWidget(attrs={'class': 'form-control'}), required=False)

        try:
            if self.fields.get('creator_user') or self.fields.get('editor_user'):
                self.fields['creator_user'].widget = self.fields['creator_user'].hidden_widget()
                self.fields['editor_user'].widget = self.fields['editor_user'].hidden_widget()
                self.fields['creator_user'].disabled = True
                self.fields['editor_user'].disabled = True
        except Exception as e:
            show_error(e, __file__)

        # add source attribute for foreign keys
        for field in self.fields:
            ...
        # 'creator_user', 'editor_user'

    def make_optional(self, fields: List):
        for f in fields:
            self.fields[f].required = False

    def make_required(self, fields: List):
        for f in fields:
            self.fields[f].required = True

    def make_disable(self, fields: List):
        if '__all__' in fields:
            for field_name, field in self.fields.items():
                field.disabled = True
            return
        for field_name, field in self.fields.items():
            if field_name in fields:
                field.disabled = True

    # def set_field_level_permission(self, fields: List, action: int):
    def set_field_level_permission(self, fields_access):
        for action, fields in fields_access.items():
            if action == 1:
                for f in self.fields:
                    if f not in fields:
                        self.fields[f].disabled = True
            elif action == 2:
                for f in fields:
                    # hidden, disable
                    self.fields[f].widget = self.fields[f].hidden_widget()
                    self.fields[f].disabled = True

        # if action == 1:
        #     for f in self.fields:
        #         if f not in fields:
        #             self.fields[f].disabled = True
        # elif action == 2:
        #     for f in fields:
        #         # hidden, disable
        #         self.fields[f].widget = self.fields[f].hidden_widget()
        #         self.fields[f].disabled = True

    def make_hidden(self, fields: List):
        import sys
        # sys.setdefaultencoding('UTF8')
        for f in fields:
            try:
                self.fields[f].widget = self.fields[f].hidden_widget()
            except KeyError as e:
                show_error(e, __file__)

    def select2(self, fields):
        for f in fields:
            if self.fields[f].disabled:
                continue
            self.fields[f].select2 = True

    def display_as_input(self, fields):
        for f in fields:
            self.fields[f].as_input = True

    def display_as_label(self, fields):
        for f in fields:
            self.fields[f].as_label = True

    def remove_fields(self, fields):
        for f in fields:
            del self.fields[f]

    def is_valid(self):
        # cleaned_data = self.cleaned_data if getattr(self,'cleaned_data',None) else None
        # self.data._mutable = True
        # if not self.change_data_for_validation:
        #     for field_str, field in self.fields.items():
        #         if getattr(field, 'queryset', None) and getattr(field.queryset.model, 'auto_complete', None):
        #             model = field.queryset.model
        #             field_data = self.data.get(f'inp_{field_str}') or self.data.get(field_str)
        #             obj, _ = model.objects.get_or_create(**{model.auto_complete: field_data})
        #             if cleaned_data:
        #                 self.cleaned_data[field_str] = obj
        #             self.data[field_str] = f'{obj.pk}'
        #     self.change_data_for_validation = True
        # validation = super().is_valid()
        # if not validation and self.change_data_for_validation:
        #     for field_str, field in self.fields.items():
        #         if getattr(field, 'queryset', None) and getattr(field.queryset.model, 'auto_complete', None):
        #             model = field.queryset.model
        #             field_data = self.data.get(f'inp_{field_str}') or self.data.get(field_str)
        #             obj = model.objects.filter(**{model.auto_complete: field_data}).first()
        #             if obj:
        #                 self.data[field_str] = obj.str
        # self.data._mutable = False
        return super().is_valid()

    def save(self, commit=True):
        # return super().save()
        """if formset empty not save"""
        if any(item for item in self.cleaned_data):
            return super().save()
        return None


#########new_hajinezhad#############
class CustomBaseModelFormAuto(forms.ModelForm):
    image_groups = None
    file_groups = None
    image_model = None
    file_model = None
    crispy = None
    action = None
    enable = True
    form_state = None
    change_data_for_validation = False
    auto_form = True
    is_used = False

    class Meta:
        ...

    def __init__(self, model=None, fields=None, request=None, *args, **kwargs):
        self.forms = list()
        self.serialized_ = None
        self.s_errors = None
        self.is_valid_ = None
        instance = kwargs.get("instance")
        if not model:
            if not instance:
                return
            else:
                model = instance._meta.model
        if not instance:
            instance = model()
        self.request = request
        total_fields = instance.get_base_fields()
        enabled_fields = list()
        disabled_fields = list()
        hidden_fields = list()
        if not self._meta.fields or self.auto_form:
            if isinstance(fields, dict):
                enabled_fields = fields.get('enabled', list())
                disabled_fields = fields.get('disabled', list())
                hidden_fields = fields.get('hidden', list())
                if enabled_fields and enabled_fields[0] == '__all__':
                    enabled_fields = list(set(total_fields) - set(disabled_fields) - set(hidden_fields))
                if disabled_fields and disabled_fields[0] == '__all__':
                    disabled_fields = list(set(total_fields) - set(enabled_fields) - set(hidden_fields))
                if hidden_fields and enabled_fields[0] == '__all__':
                    hidden_fields = total_fields
                fields = enabled_fields + disabled_fields + hidden_fields
                fields.sort()
            if not fields:
                fields = total_fields
            else:
                fields = [field for field in fields if field in total_fields]
            self._meta.fields = fields
        else:
            fields = self._meta.fields
        if self.is_used:
            return
        self.__class__.is_used = True
        self.base_fields = instance.get_fields(fields)
        self._meta.model = model
        # set auto_complete
        # data = kwargs.get('data')
        # if data:
        #     for key, value in data.items():
        #         if key.__contains__("__auto__"):
        #             key = key.replace("__auto__", "")
        #             value = value.strip()
        #             if value:
        #                 model = self.base_fields[key].queryset.model
        #                 obj, is_create = model.objects.get_or_create(**{model.auto_complete: value})
        #                 value = getattr(obj, self.base_fields[key].to_field_name, None)
        #             data[key] = value
        #     kwargs['data'] = data

        super().__init__(*args, **kwargs)
        self.__class__.is_used = False
        for field in self.fields:
            if not isinstance(self.fields[field].widget, CheckboxInput):
                self.fields[field].widget.attrs['class'] = 'form-control'
            m_field = self.fields[field]
            if isinstance(m_field.widget, DateInput) or isinstance(m_field.widget, DateTimeInput):
                self.fields[field] = JalaliDateField(label=m_field.label
                            , widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-date form-control', 'size': '10'})
                            , required=m_field.required)

        # disabled_fields += ['creator_user', 'editor_user']
        # hidden_fields += ['creator_user', 'editor_user']
        self.change_disabled(disabled_fields, True)
        self.change_hidden(hidden_fields, True)

    @property
    def get_field_groups(self):
        if self.instance.field_groups:
            field_groups = []
            for item in self.instance.field_groups:
                fields = []
                for field in item.get('fields',[]):
                    fields.append([f for f in self if f.name == field][0])
                # fields = {f for f in self if f.name in item.get('fields',[])}
                # for field in item.get('fields',[]):
                #     fields[field] = (self.fields[field])
                field_groups.append({'title': item.get('title', ''), 'css_class': item.get('css_class', 'row row-cols5'), 'fields': fields})
            return field_groups
        else:
            return [{'title': '', 'css_class': 'row row-cols5', 'fields': self.fields}]

    def save(self, commit=True):
        if self.is_valid_:
            self.instance.save()
        # super().save(commit)
        for form in self.forms:
            form.save(commit)

    def serialized(self):
        if self.instance:
            self.serialized_ = self.instance.serialized
            return self.serialized_

    def change_optional(self, fields: List, required=False):
        for field in fields:
            if self.fields.get(field):
                self.fields[field].required = required

    def change_disabled(self, fields: List, disabled=True):
        for field in fields:
            if self.fields.get(field):
                self.fields[field].disabled = disabled

    def change_hidden(self, fields: List,hidden=True):
        for field in fields:
            if self.fields.get(field):
                self.fields[field].widget = self.fields[field].hidden_widget()

    def select2(self, fields):
        for f in fields:
            if self.fields[f].disabled:
                continue
            self.fields[f].select2 = True

    def display_as_input(self, fields):
        for f in fields:
            self.fields[f].as_input = True

    def display_as_label(self, fields):
        for f in fields:
            self.fields[f].as_label = True

    def remove_fields(self, fields):
        for f in fields:
            del self.fields[f]

    def is_valid(self):
        if self.is_valid_ is None:
            self.s_errors = list()
            self.is_valid_ = super().is_valid()
            self.s_errors = self._errors
            for form in self.forms:
                self.is_valid_ = self.is_valid_ and form.is_valid()
                self.s_errors += form._errors
            return self.is_valid_
        else:
            return self.is_valid_
        # cleaned_data = self.cleaned_data if getattr(self,'cleaned_data',None) else None
        # self.data._mutable = True
        # if not self.change_data_for_validation:
        #     for field_str, field in self.fields.items():
        #         if getattr(field, 'queryset', None) and getattr(field.queryset.model, 'auto_complete', None):
        #             model = field.queryset.model
        #             field_data = self.data.get(f'inp_{field_str}') or self.data.get(field_str)
        #             obj, _ = model.objects.get_or_create(**{model.auto_complete: field_data})
        #             if cleaned_data:
        #                 self.cleaned_data[field_str] = obj
        #             self.data[field_str] = f'{obj.pk}'
        #     self.change_data_for_validation = True
        # validation = super().is_valid()
        # if not validation and self.change_data_for_validation:
        #     for field_str, field in self.fields.items():
        #         if getattr(field, 'queryset', None) and getattr(field.queryset.model, 'auto_complete', None):
        #             model = field.queryset.model
        #             field_data = self.data.get(f'inp_{field_str}') or self.data.get(field_str)
        #             obj = model.objects.filter(**{model.auto_complete: field_data}).first()
        #             if obj:
        #                 self.data[field_str] = obj.str
        # self.data._mutable = False
        # return super().is_valid()



    # def save(self, commit=True):
    #     # return super().save()
    #     """if formset empty not save"""
    #     if any(item for item in self.cleaned_data):
    #         return super().save()
    #     return None
