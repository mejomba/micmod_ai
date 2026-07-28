from collections import namedtuple

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist
from django.forms import DateInput
from django.forms.widgets import CheckboxInput, FileInput, DateTimeInput
from django.urls import reverse_lazy
from jalali_date.widgets import AdminJalaliDateWidget, AdminSplitJalaliDateTime

from core.models import Work
from files.models import UploadType, File
from tools.utils import show_error
from translator import get_text as _

from typing import List

from jalali_date.fields import JalaliDateField, JalaliDateTimeField
import json

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
                self.fields[field].widget.attrs['class'] = self.fields[field].widget.attrs.get('class', "") + ' form-control '
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

    def make_readonly(self, fields: List):
        for f in fields:
            self.fields[f].widget.attrs['readonly'] = True

    def make_disable(self, fields: List):
        if '__all__' in fields:
            for field_name, field in self.fields.items():
                field.disabled = True
            return
        for field_name, field in self.fields.items():
            if field_name in fields:
                field.disabled = True

    def make_enable(self, fields: List):
        if '__all__' in fields:
            for field_name, field in self.fields.items():
                field.disabled = False
            return
        for field_name, field in self.fields.items():
            if field_name in fields:
                field.disabled = False

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
        for f in fields:
            try:
                if f in self.fields:
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

from django.contrib.admin.widgets import FilteredSelectMultiple


class WorkModelForm(CustomBaseModelForm):
    file_model = File
    file_groups = 1

    class Meta:
        model = Work
        exclude = ['factor_self', 'guid', 'status', 'group', ]

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        self.fields['to_users'] = forms.ModelChoiceField(
            queryset=get_user_model().objects.all(),
            required=True,
            widget=FilteredSelectMultiple(_("to_users"), is_stacked=False),
        )
        self.fields['to_users'].widget.attrs['placeholder'] = 'کاربرانی که میخواهید این اعلان را دریافت کنند'
        self.fields['address'].widget.attrs['placeholder'] = 'آدرس صفحه پرتال که کاربران باید به آن مراجعه کنند (به صورت پیشفرض صفحه فعلی در نظر گرفته میشود)'
        self.fields['address'].widget.attrs['rows'] = 3
        self.fields['address'].initial = request.META.get('HTTP_REFERER') if request else ''
        self.fields['body'].widget.attrs['rows'] = 3


DisplayField = namedtuple("DisplayField", ["name", "value", "kind", "label"])
DisplayField.__new__.__defaults__ = (None,)     # label اختیاری


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"class": "file-input", "multiple": "on"}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single = super().clean
        if isinstance(data, (list, tuple)):
            return [single(d, initial) for d in data]
        return single(data, initial)


class FormMX(forms.ModelForm):
    file_model = File  # مدل File (generic FK)
    file_groups_2 = 0  # تعداد اسلات‌های فایل
    file_labels = dict()
    file_group_field = "group"  # فیلدی در File که شماره‌ی گروه را نگه می‌دارد (توصیه‌شده)
    file_file_field = "file"  # نام FileField در مدل File
    file_field_prefix = "file_"
    field_layout = []
    select2_url_name = ""  # نام URL ویوی سرچ AJAX
    select2_fields = {}  # {field: {"ajax": key, "placeholder": str, "min_input": int}}

    def __init__(self, *args, allowed_fields=None, allowed_hidden=None, only_show=None, **kwargs):
        super().__init__(*args, **kwargs)

    def _file_field_names(self):
        return {f"{self.file_field_prefix}{i}" for i in range(1, self.file_groups_2 + 1)}

    def _add_file_fields(self):
        self.file_existing = {}
        if not self.file_model or not self.file_groups_2:
            return
        existing = self._load_existing_files()  # {i: [File, ...]}
        only = []
        for o in self.only_show:
            if o not in only:
                only.append(o)
        for i in range(1, self.file_groups_2 + 1):
            name = f"{self.file_field_prefix}{i}"
            self.file_existing[name] = existing.get(i, [])
            if name in only:
                continue  # only_show: فقط نمایش
            label = self.file_labels.get(i) or self.file_labels.get(str(i)) or f"فایل {i}"
            self.fields[name] = MultipleFileField(label=label, required=False)

    def _load_existing_files(self):
        inst = self.instance
        if not inst or inst.pk is None:
            return {}
        ct = ContentType.objects.get_for_model(inst.__class__)
        qs = self.file_model.objects.filter(content_type=ct, object_id=inst.pk).order_by("pk")
        out = {}
        if self.file_group_field:
            for f in qs:
                g = getattr(f, self.file_group_field, None)
                if g:
                    out.setdefault(int(g), []).append(f)
        else:
            out.setdefault(1, []).extend(list(qs))  # بدون فیلد گروه، تفکیک ممکن نیست
        return out

    def iter_file_fields(self):
        """فقط گروه‌های فایلِ ادیتبل (only_showها در iter_only_show می‌آیند)."""
        if not self.file_model or not self.file_groups_2:
            return []
        only = []
        for o in self.only_show:
            if o not in only:
                only.append(o)
        out = []
        for i in range(1, self.file_groups_2 + 1):
            name = f"{self.file_field_prefix}{i}"
            if name in only:
                continue
            out.append({
                "name": name,
                "label": self.file_labels.get(i) or self.file_labels.get(str(i)) or f"فایل {i}",
                "field": self[name] if name in self.fields else None,
                "files": self._group_files(name),
            })
        return out

    def _group_files(self, name):
        out = []
        for o in self.file_existing.get(name, []):
            # ff = getattr(o, self.file_file_field, None)
            if o:
                out.append({
                    "url": o.path,
                    "filename": o.name().rsplit("/", 1)[-1],
                    "pk": o.pk,
                    "is_image": o.name().lower().endswith(
                        (".png", ".jpg", ".jpeg", ".gif", ".webp")),
                })
        return out

    def select2_extra_params(self, name, cfg):
        if name == "address":
            cust = self._current_customer_id()
            if cust:
                return {"customer": cust.sepidar_party_id}
        if name == 'q':
            q = self._current_user_id()
            if q:
                return {'creator_user': q.pk}
        return {}

    def _current_customer_id(self):
        inst = self.instance
        if not inst or inst.pk is None:
            return None
        return getattr(inst, "customer_party_id", None)  # یا inst.q.customer_id و ...

    def _current_user_id(self):
        try:
            user = self.initial.get('constraint').get('request').user
            return user
        except Exception as e:
            inst = self.instance
            if not inst or inst.pk is None:
                return None
            return getattr(inst, "creator_user", None)  # یا inst.q.customer_id و ...

    def _apply_select2(self):
        for name, cfg in self.select2_fields.items():
            field = self.fields.get(name)
            if field is None or isinstance(field.widget, forms.HiddenInput):
                continue  # با نقش حذف/هیدن شده
            is_multi = isinstance(field, forms.ModelMultipleChoiceField)
            w = field.widget
            w.attrs["class"] = (w.attrs.get("class", "") + " select2").strip()
            w.attrs.setdefault("data-placeholder", cfg.get("placeholder", "انتخاب کنید"))
            w.attrs.setdefault("data-width", "100%")
            if not is_multi and cfg.get("allow_clear", True):
                w.attrs.setdefault("data-allow-clear", "1")
            if "min_results_search" in cfg:
                w.attrs["data-min-results-search"] = cfg["min_results_search"]
            ajax_key = cfg.get("ajax")
            if ajax_key:
                w.attrs["data-ajax-url"] = str(
                    reverse_lazy(self.select2_url_name, kwargs={"key": ajax_key}))
                w.attrs["data-min-input"] = cfg.get("min_input", 1)
                self._limit_rendered_choices(name, field)  # کلید کارایی

            extra = self.select2_extra_params(name, cfg)
            if extra:
                w.attrs["data-ajax-extra"] = json.dumps(extra)

    def _limit_rendered_choices(self, name, field):
        is_m2m = isinstance(field, forms.ModelMultipleChoiceField)
        vfield = field.to_field_name or "pk"  # جنگو خودش from to_field پرش می‌کند
        values = []
        if self.is_bound:
            values = (self.data.getlist(self.add_prefix(name)) if is_m2m
                      else [self.data.get(self.add_prefix(name))])
        elif self.instance.pk:
            if is_m2m:
                values = list(getattr(self.instance, name).values_list(vfield, flat=True))
            else:
                values = [getattr(self.instance, f"{name}_id", None)]  # ستون FK همان مقدار to_field است
        elif self.initial.get(name) is not None:
            init = self.initial[name]
            values = list(init) if is_m2m else [init]

        values = [v for v in values if v not in (None, "")]
        objs = list(field.queryset.filter(**{f"{vfield}__in": values})) if values else []

        def _val(o):
            return o.pk if vfield == "pk" else getattr(o, vfield)

        choices = [(_val(o), field.label_from_instance(o)) for o in objs]
        if not is_m2m:
            choices = [("", field.empty_label or "---------")] + choices
        field.widget.choices = choices

    def iter_editable(self):
        """فقط فیلدهای قابل ویرایش (غیرهیدن) به ترتیب field_layout."""
        l = []
        only = []
        for o in self.only_show:
            if o not in only:
                only.append(o)
        names = self.field_layout or list(self.fields.keys())
        # for name in names:
        for name in self.allowed_fields:
            if name in only:
                continue
            if name in self.fields:
                bf = self[name]
                if isinstance(bf.field.widget, forms.FileInput):
                    continue
                if not bf.is_hidden:
                    l.append(bf)
        return l

    def iter_only_show(self):
        fnames = self._file_field_names()
        out = []
        for i_name in self.only_show:
            if i_name in fnames:
                idx = int(i_name.rsplit("_", 1)[-1])
                label = self.file_labels.get(idx) or self.file_labels.get(str(idx)) or i_name
                out.append(DisplayField(i_name, self._group_files(i_name), "files", label))
            else:
                out.append(self._resolve_display(i_name))  # label پیش‌فرض None
        return out

    def _resolve_display(self, name):
        instance = self.instance
        try:
            mf = instance._meta.get_field(name)
        except FieldDoesNotExist:
            return DisplayField(name, getattr(instance, name, None), "text")  # annotation/free_qty

        if getattr(mf, "choices", None):
            getter = getattr(instance, f"get_{name}_display", None)
            return DisplayField(name, getter() if getter else None, "text")
        if mf.many_to_one or mf.one_to_one:
            rel = getattr(instance, name, None)
            return DisplayField(name, str(rel) if rel is not None else None, "text")
        if mf.many_to_many:
            if instance.pk is None:
                return DisplayField(name, None, "text")
            rels = getattr(instance, name).all()
            return DisplayField(name, "، ".join(str(o) for o in rels) or None, "text")

        internal = mf.get_internal_type()
        raw = getattr(instance, name, None)
        if internal == "BooleanField":
            return DisplayField(name, raw, "bool")
        if internal == "DateTimeField":
            return DisplayField(name, raw, "datetime")
        if internal == "DateField":
            return DisplayField(name, raw, "date")
        return DisplayField(name, raw, "text")