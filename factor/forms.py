import time

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q, Max
from django.forms import inlineformset_factory

from django import forms
from django.urls import reverse_lazy
from django_select2.forms import ModelSelect2MultipleWidget
from jalali_date.fields import JalaliDateField, JalaliDateTimeField, SplitJalaliDateTimeField
from jalali_date.widgets import AdminJalaliDateWidget, AdminSplitJalaliDateTime

from accounts.models import User
from core.forms import CustomBaseModelForm
from extra_data.models import CustomerAddress
from factor.models import Factor, FactorItem, Delivery, FactorItemSupplyLocation
from files.models import File
from order.models import Order, OrderBazar
from tools.utils import timer
from translator import get_text as _
from django.utils.html import format_html
from workflow.models import FlowAdminGroup
from .services.supply import attach_supply


class x (AdminSplitJalaliDateTime):
    template_name = 'core/partial/jalali_split_datetime.html'


class UserSelectWidget(ModelSelect2MultipleWidget):
    search_fields = [
        "username__icontains",
        "first_name__icontains",
        "last_name__icontains",
        "email__icontains",
    ]


class FactorModelForm(CustomBaseModelForm):
    file_model = File
    file_groups = 4
    has_comment = True

    class Meta:
        model = Factor
        exclude = ['factor_self', 'guid', 'status', 'group', ]

    def __init__(self, *args, **kwargs):
        request = access = form_constraint = formset_constraint = form_constraint_read = form_constraint_hide = formset_constraint_read = formset_constraint_hide = None
        if self.form_state is None:
            if kwargs.get('initial') and (c := kwargs.get('initial').get('constraint')):
                self.form_state = c.get('form_state')
            elif kwargs.get('constraint'):
                self.form_state = kwargs.get('constraint').get('form_state')

        if self.form_state is not None:
            if kwargs.get('initial') and (c := kwargs.get('initial').get('constraint')):
                access = c.pop('wf_access')
                form_constraint = c.pop('form_constraint')  # remove unnecessary kwargs
                formset_constraint = c.pop('formset_constraint')  # remove unnecessary kwargs
                request = c.pop('request')  # remove unnecessary kwargs
                flow_state_name = c.pop('flow_state_name', None)
            elif kwargs.get('constraint'):
                access = kwargs.get('constraint').get('wf_access')
                form_constraint = kwargs.get('constraint').get('form_constraint')
                formset_constraint = kwargs.get('constraint').get('formset_constraint')
                request = kwargs.get('constraint').get('request')  # remove unnecessary kwargs
                kwargs.pop('constraint')  # remove unnecessary kwargs
                flow_state_name = kwargs.pop('flow_state_name', None)

            if form_constraint:
                for item in form_constraint[self.form_state]:
                    if not isinstance(item, dict):
                        item = form_constraint[self.form_state]
                    if item.get('group') in request.user.groups.values_list('name', flat=True) or FlowAdminGroup.is_admin_of_group(request.user, item.get('group')):
                        form_constraint_read = item.get('read')  # form_constraint[self.form_state].get('read')
                        form_constraint_hide = item.get('hide')  # orm_constraint[self.form_state].get('hide')
            if formset_constraint:
                for item in formset_constraint[self.form_state]:
                    if not isinstance(item, dict):
                        item = formset_constraint[self.form_state]
                    if item.get('group') in request.user.groups.values_list('name', flat=True) or FlowAdminGroup.is_admin_of_group(request.user, item.get('group')):
                        formset_constraint_read = item.get('read')  # formset_constraint[self.form_state][0].get('read')
                        formset_constraint_hide = item.get('hide')  # formset_constraint[self.form_state][0].get('hide')
        super(FactorModelForm, self).__init__(*args, **kwargs)
        # self.make_hidden(['packing_json'])
        if self.instance.__class__.__name__.lower() == 'quotation':
            qs = (
                CustomerAddress.objects
                .filter(customer=self.instance.customer_party_id)
                .annotate(last_used=Max('factor__created_date'))
                .order_by('-last_used')
            )
            self.fields['address'].queryset = qs  # CustomerAddress.objects.filter(customer=self.instance.customer_party_id)
        elif self.instance.pk:
            qs = (
                CustomerAddress.objects
                .filter(customer=self.instance.q.customer_party_id)
                .annotate(last_used=Max('factor__created_date'))
                .order_by('-last_used')
            )
            self.fields['address'].queryset = qs  # CustomerAddress.objects.filter(customer=self.instance.q.customer_party_id)
        self.fields['is_official'].widget.attrs['onchange'] = 'factor_calculate_price_all_rows()'
        self.fields['official_value'].widget = forms.TextInput(attrs={'onchange': 'factor_calculate_price_all_rows()', 'class': 'LTR-RTL rounded font-size-11 text-center w-75'})
        self.fields['self_discount'].widget = forms.TextInput(attrs={'onchange': 'factor_calculate_price_all_rows()', 'class': 'LTR-RTL rounded font-size-11 text-center w-75'})

        self.make_hidden(['q'])
        self.fields['collecting_start_time'] = SplitJalaliDateTimeField(label=_('collecting_start_time'),
                                                      widget=x(
                                                          attrs={'class': 'jalali_date-date form-control',
                                                                 'size': '10'}), required=True if request and request.user.base_group == 'wh' else False
                                                      )
        self.fields['collecting_end_time'] = forms.DateTimeField(required=False)
        self.fields['wh_user'] = forms.ModelMultipleChoiceField(queryset=User.objects.filter(Q(groups__name='wh_user') |
                                                                              Q(groups__name='wh_admin')).distinct(), required=False)

        if request and request.user.base_group == 'accounting':
            self.fields['checker'] = forms.ModelMultipleChoiceField(queryset=User.objects.filter(Q(groups__name='accounting_user') |
                                                                                                 Q(groups__name='accounting_admin')).distinct(), required=False)
        else:
            self.fields['checker'] = forms.ModelMultipleChoiceField(
                queryset=User.objects.filter(Q(groups__name='accounting_user') |
                                             Q(groups__name='accounting_admin')).distinct(), required=False, disabled=True)

        self.make_disable(["sepidar_number", "sepidar_id"])
        self.make_hidden(form_constraint_hide or [])
        self.make_hidden(formset_constraint_hide or [])
        self.make_disable(form_constraint_read or [])
        self.make_disable(formset_constraint_read or [])
        self.make_hidden(['fiscalyearref', 'sepidar_voucher_id', 'sepidar_voucher_number',
                          'sepidar_inventory_delivery_id', 'sepidar_inventory_delivery_number', 'total_price'])
        if self.instance.pk and self.instance.sepidar_number:
            self.make_hidden(['cancel'])
        if self.form_state == 7:
            self.make_hidden(['self_discount', 'qi'])


class FactorItemModelForm(CustomBaseModelForm):
    class Meta:
        model = FactorItem
        exclude = ['group']
    # supply_location = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        internal_call = kwargs.pop('internal_call', None)
        request = access = form_constraint = formset_constraint = form_constraint_read = form_constraint_hide = formset_constraint_read = formset_constraint_hide = flow_state_name = None
        if self.form_state is None:
            if kwargs.get('initial') and (c := kwargs.get('initial').get('constraint')):
                self.form_state = c.get('form_state')
            elif kwargs.get('constraint'):
                self.form_state = kwargs.get('constraint').get('form_state')

        if self.form_state is not None:
            if kwargs.get('initial') and (c := kwargs.get('initial').get('constraint')):
                access = c.pop('wf_access')
                form_constraint = c.pop('form_constraint')  # remove unnecessary kwargs
                formset_constraint = c.pop('formset_constraint')  # remove unnecessary kwargs
                request = c.pop('request')  # remove unnecessary kwargs
                flow_state_name = kwargs.pop('form_state_name', None)
            elif kwargs.get('constraint'):
                access = kwargs.get('constraint').get('wf_access')
                form_constraint = kwargs.get('constraint').get('form_constraint')
                formset_constraint = kwargs.get('constraint').get('formset_constraint')
                request = kwargs.get('constraint').get('request')  # remove unnecessary kwargs
                flow_state_name = kwargs.get('constraint').get('form_state_name')
                kwargs.pop('constraint')  # remove unnecessary kwargs

            if request and not request.user.is_superuser and form_constraint:
                for item in form_constraint[self.form_state]:
                    if not isinstance(item, dict):
                        item = form_constraint[self.form_state]
                    if item.get('group') in request.user.groups.values_list('name', flat=True) or FlowAdminGroup.is_admin_of_group_cached(request.user, item.get('group'), flow_state_name):
                        form_constraint_read = item.get('read')  # form_constraint[self.form_state].get('read')
                        form_constraint_hide = item.get('hide')  # orm_constraint[self.form_state].get('hide')
            if request and not request.user.is_superuser and formset_constraint:
                for item in formset_constraint[self.form_state]:
                    if not isinstance(item, dict):
                        item = formset_constraint[self.form_state]
                    if item.get('group') in request.user.groups.values_list('name', flat=True) or FlowAdminGroup.is_admin_of_group_cached(request.user, item.get('group'), flow_state_name):
                        formset_constraint_read = item.get('read')  # formset_constraint[self.form_state][0].get('read')
                        formset_constraint_hide = item.get('hide')  # formset_constraint[self.form_state][0].get('hide')

        super(FactorItemModelForm, self).__init__(*args, **kwargs)

        self.fields['quantity'].widget.attrs['onkeyup'] = 'check_quantity(event)'
        self.fields['price'].widget.attrs['onkeyup'] = 'check_price(event)'
        self.fields['price'].widget.attrs['class'] += ' comma-seperator'
        self.fields['is_bazar'].widget.attrs['class'] = 'checkbox_is_bazar'
        if self.fields['is_bazar']:
            self.make_disable(['supply_locations'])
        if self.instance:
            self.fields['supply_locations'].queryset = Order.objects.filter(item_id=self.instance.goods_code)

        self.make_hidden(form_constraint_hide or [])
        self.make_hidden(formset_constraint_hide or [])
        self.make_disable(form_constraint_read or [])
        self.make_disable(formset_constraint_read or [])
        if not access and not internal_call:
            self.make_disable(self.fields)

        self.make_enable(['supply_location'])


factor_item_fields = ['factor', 'qi', 'index', 'quantity', 'delivery_time', 'custom_price', 'goods_code', 'price',
                      'part_number_show', 'supply_location', 'supply_locations', 'is_bazar', 'reserve_count',
                      'discount_per_item',
                      ]

FactorItemFormset = inlineformset_factory(
    Factor,
    FactorItem,
    form=FactorItemModelForm,
    extra=0,
    fields=factor_item_fields,
)


class DeliveryForm(CustomBaseModelForm):

    class Meta:
        model = Delivery
        exclude = ['group', 'delivery_date', 'tracking_number']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


from collections import namedtuple
from django import forms
from django.core.exceptions import FieldDoesNotExist


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"class": "file-input"}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single = super().clean
        if isinstance(data, (list, tuple)):
            return [single(d, initial) for d in data]
        return single(data, initial)


class FormMX(forms.ModelForm):
    file_model = File  # مدل File (generic FK)
    file_groups_2 = None  # تعداد اسلات‌های فایل
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
        only = set(self.only_show)
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
        only = set(self.only_show)
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
        return {}

    def _current_customer_id(self):
        inst = self.instance
        if not inst or inst.pk is None:
            return None
        return getattr(inst, "customer_party_id", None)  # یا inst.q.customer_id و ...

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
        only = set(self.only_show)
        names = self.field_layout or list(self.fields.keys())
        for name in names:
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


DisplayField = namedtuple("DisplayField", ["name", "value", "kind", "label"])
DisplayField.__new__.__defaults__ = (None,)     # label اختیاری
# ─── فیلدهای مجاز Factor به ازای هر گروه ────────────────────────────────────
# "app_name.code_name"
FACTOR_FIELDS_BY_PERMISSION = {
    "factor.cp_factor_sales": {
        0: {
            "edit": [
                "customer_party_id", "payment_method", "sale_type", "address", "delivery_time", "description",
                "deliver_type", "deliver_method", "self_discount", "is_official", "official_value", "currency_ref",
                "to_be_collected", "cancel", "require_official_factor_with_delivery", "need_factor_document", "file_2",
                "currency_amount",

            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price",
            ],
            "show": ["delivery_time", "q", "created_date", "need_financial_approval", "wh_user", "checker",
                     "accounting_confirm", "file_1", "file_3", "file_4"]
        },
        1: {
            "edit": [
                "customer_party_id", "payment_method", "sale_type", "address", "delivery_time", "description",
                "deliver_type", "deliver_method", "self_discount", "is_official", "official_value", "currency_ref",
                "to_be_collected", "cancel", "require_official_factor_with_delivery", "need_factor_document", "file_2",

            ],
            "hidden": [
                 "addition", "tax", "duty", "total_price",
            ],
            "show": ["delivery_time", "q", "created_date", "need_financial_approval", "wh_user", "checker",
                     "accounting_confirm", "file_1", "file_3", "file_4"]
        },
        2: {
            "edit": [
                "address", "delivery_time", "deliver_type", "deliver_method",
                "sale_type", "self_discount", "description", "is_official", "official_value", "accounting_confirm", 'sales_admin_confirm'
            ],
            "hidden": [
                "q", "total_forms", "initial_forms", "min_num_forms", "max_num_forms"
            ]
        },
    },
    "factor.cp_factor_wh": {},
    "factor.cp_factor_accounting": {},
    "factor.cp_factor_admin": {},
    "factor.cp_factor_superuser": {},
}

# ─── فیلدهای مجاز FactorItem به ازای هر گروه ─────────────────────────────────

FACTOR_ITEM_FIELDS_BY_PERMISSION = {
    "factor.cp_factor_item_sales": {
        0: {
            "edit": [
                "goods_code", "part_number_show", "quantity", "price", "discount_per_item",
            ],
            "hidden": [
                "qi", "factor"
            ],
            "show": [
                "quantity"
            ]
        },
        1: {
            "edit": [
                "goods_code", "part_number_show", "quantity", "price", "discount_per_item",
            ],
            "hidden": [
                "qi", "factor"
            ]
        },
        2: {
            "edit": [
                "goods_code","is_deleted", "part_number_show", "quantity", "price", "discount_per_item",
            ],
            "hidden": [
                "qi", "factor", "total_forms", "initial_forms", "min_num_forms", "max_num_forms"
            ]
        },
    },
    "cp_factor_item_sales_admin": {
        0: {
            "edit": [
                "goods_code", "part_number_show", "quantity", "price", "discount_per_item",
            ],
            "hidden": [
                "qi", "factor"
            ]
        },
    },
    "cp_factor_item_z": {
        1: {
            "edit": [
                "goods_code", "part_number_show", "quantity", "price", "discount_per_item",
            ],
            "hidden": [
                "qi", "factor"
            ]
        },
    },
        1: {
            "edit": [
                "goods_code", "part_number_show", "quantity", "price", "discount_per_item",
            ],
            "hidden": [
                "q"
            ]
        },
    }


# ─── فرم Factor ───────────────────────────────────────────────────────────────


class FactorEditForm(FormMX, CustomBaseModelForm):
    has_comment = True
    # ── پیکربندی فایل ──
    file_model = File  # مدل File (generic FK)
    file_groups_2 = 4  # تعداد اسلات‌های فایل
    file_labels = {1: "اسناد مالی", 2: "اسناد انبار", 3: "اسناد تحویل", 4: "فاکتور رسمی"}
    file_group_field = "group"  # فیلدی در File که شماره‌ی گروه را نگه می‌دارد (توصیه‌شده)
    file_file_field = "file"  # نام FileField در مدل File
    file_field_prefix = "file_"
    field_layout = [
        "customer_party_id", "address", "delivery_time",  "sepidar_number", "sepidar_id", "sepidar_inventory_delivery_number",
        "sepidar_inventory_delivery_id", "sepidar_voucher_number", "sepidar_voucher_id", "fiscalyearref", "factor_self",
        "self_discount", "official_value", "wh_user", "deliver_type", "sale_type", "need_financial_approval",
        "collecting_start_time", "collecting_end_time",
        "official_factor_send_with_this_factor", "official_factor_for_this_factor",
        "checker", "packing_json", "customer_request", "currency_ref",
        "deliver_method", "accounting_confirm", "description",
        "rate", "total_price", "tax", "final_price", "addition", "tax", "duty", "q", "currency_amount"
        # checkbox section
        "is_official", "cancel", "deliver_to_customer", "sales_admin_confirm", "final_check", "force_factor",
        "require_official_factor_with_delivery", "to_be_collected", "need_factor_document",
        # file section
        "file_1",  # اسناد مالی
        "file_2",  # اسناد انبار
        "file_3",  # اسناد تحویل
        "file_4",  # فاکتور رسمی
    ]
    select2_url_name = "factor:select2-search"  # نام URL ویوی سرچ AJAX
    select2_fields = {
        "currency_ref": {},  # لوکال
        "sale_type": {},  # لوکال
        "wh_user": {"ajax": "wh_user", "min_input": 0, "placeholder": "انتخاب کارشناس انبار"},
        "checker": {"ajax": "checker", "min_input": 0, "placeholder": "انتخاب کارشناس مالی"},  # لوکال M2M
        "address": {"ajax": "address", "placeholder": "جستجوی آدرس", "min_input": 0},
        "customer_party_id": {"ajax": "customer_party_id", "min_input": 2, "placeholder": "انتخاب مشتری"},
    }  # {field: {"ajax": key, "placeholder": str, "min_input": int}}

    class Meta:
        model = Factor
        fields = "__all__"
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "official_factor_send_with_this_factor": forms.TextInput(),
            "official_factor_for_this_factor": forms.TextInput(),
            "collecting_start_time": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "collecting_end_time": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
        }

    def __init__(self, *args, allowed_fields=None, allowed_hidden=None, only_show=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.only_show = list(only_show or [])
        self._add_file_fields()

        self._apply_select2()
        self.make_optional(['checker'])

        # ========= remove field
        if allowed_fields is not None or allowed_hidden is not None:
            keep = set(allowed_fields or []) | set(allowed_hidden or [])
            for name in list(self.fields):
                if name not in keep:
                    self.fields.pop(name)

        # ========= hide field
        if allowed_hidden is not None:
            for field_name in list(self.fields):
                if field_name in allowed_hidden:
                    self.fields[field_name].widget = self.fields[field_name].hidden_widget()

        for name in self.only_show:  # only_show نباید در فرم باشد (دفاعی)
            self.fields.pop(name, None)




# ─── فرم FactorItem ───────────────────────────────────────────────────────────
import json
class FactorItemForm(CustomBaseModelForm):
    field_layout = []
    supply_locations = forms.CharField(
        required=False, widget=forms.HiddenInput
    )
    class Meta:
        model = FactorItem
        fields = "__all__"
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "quantity": forms.TextInput(attrs={"inputmode": "decimal", "class": " js-thousands"}),
            "price": forms.TextInput(attrs={"inputmode": "decimal", "class": " js-thousands"}),
            "discount_per_item": forms.TextInput(attrs={"inputmode": "decimal", "class": " js-thousands"}),
        }

    def __init__(self, *args, allowed_fields=None, allowed_hidden=None, only_show=None, **kwargs):
        super().__init__(*args, **kwargs)

        """prepare fields default value and widget customization before permission section"""

        # self.fields['quantity'].widget.attrs['class'] = self.fields['quantity'].widget.attrs.get('class', '')
        self.fields['price'].widget.attrs['onkeyup'] = "factor_calculate_price(this)"
        self.fields['discount_per_item'].widget.attrs['onkeyup'] = "factor_calculate_price(this)"
        self.make_required(['quantity', 'price', 'discount_per_item', 'goods_code', 'part_number_show'])

        self.fields['quantity'].widget.attrs['required'] = 'required'
        self.fields['price'].widget.attrs['required'] = 'required'
        self.fields['discount_per_item'].widget.attrs['required'] = 'required'
        self.fields['goods_code'].widget.attrs['required'] = 'required'
        self.fields['part_number_show'].widget.attrs['required'] = 'required'

        for f in self.fields:
            self.fields[f].widget.attrs['class'] = self.fields[f].widget.attrs.get('class', '') + " p-5px"

        """permission section: del and hiddel fields"""
        if allowed_fields is not None:
            for field_name in list(self.fields):
                if field_name not in allowed_fields:
                    del self.fields[field_name]

        if allowed_hidden is not None:
            for field_name in list(self.fields):
                if field_name in allowed_hidden:
                    self.fields[field_name].widget = self.fields[field_name].hidden_widget()

    def clean_supply_locations(self):
        raw = self.cleaned_data.get('supply_locations') or '[]'
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise forms.ValidationError("داده‌ی محل تامین معتبر نیست")
        # اعتبارسنجی اولیه — مجموع باید با quantity برابر باشد و غیره
        return data




from django.forms.models import BaseInlineFormSet
from django.db.models import Prefetch

class FactorItemInlineFormSetBase(BaseInlineFormSet):
    """
    در GET، آیتم‌ها را با prefetch روی محل تامین‌ها لود می‌کند و .supply می‌چسباند.
    در POST از این کار صرف نظر می‌کند چون داده‌ی فرم در حال validate شدن است.
    """
    supply_locations = forms.CharField(
        required=False, widget=forms.HiddenInput
    )
    @timer
    def get_queryset(self):
        print('get_queryset ...')
        if not hasattr(self, "_queryset"):
            if self.instance.pk is None:
                # فاکتور هنوز ساخته نشده — هیچ آیتمی نیست
                self._queryset = []
                return self._queryset

            qs = (
                self.model._default_manager
                .filter(**{self.fk.name: self.instance})
                .order_by("pk")
            )

            if not self.is_bound:  # فقط GET
                qs = qs.prefetch_related(
                    Prefetch(
                        "factoritemsupplylocation_set",
                        queryset=FactorItemSupplyLocation.objects.select_related(
                            "wh_reserve", "order", "order_bazar",
                        ),
                    )
                )
                items = list(qs)
                attach_supply(items)            # تابعی که قبلاً نوشتیم
                self._queryset = items
            else:
                self._queryset = list(qs)

        return self._queryset