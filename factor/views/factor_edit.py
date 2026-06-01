from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.edit import UpdateView
from django.urls import reverse_lazy
from django.core.exceptions import PermissionDenied
from django.forms import inlineformset_factory
from django.db import transaction

from ..models import Factor, FactorItem


# ─── فیلدهای مجاز Factor به ازای هر گروه ────────────────────────────────────

FACTOR_FIELDS_BY_GROUP = {
    "sales": {
        1: {"edit": [
                "address",
                "delivery_time",
                "description",
                "deliver_type",

                "sale_type",
                "self_discount",
                "factor_self",
            ],
            "read": [
                "deliver_method",
            ]
        },
    },
    "wh": [
        "wh_user",
        "to_be_collected",
        "collecting_start_time",
        "collecting_end_time",
        "final_check",
        "deliver_to_customer",
        "packing_json",
    ],
    "accounting": [
        "accounting_confirm",
        "need_financial_approval",
        "is_official",
        "official_value",
    ],
    "office": [
        "address",
        "delivery_time",
        "description",
        "deliver_type",
        "deliver_method",
        "require_official_factor_with_delivery",
        "official_factor_send_with_this_factor",
        "official_factor_for_this_factor",
        "need_factor_document",
    ],
    "trade": [
        "delivery_time",
        "description",
        "deliver_type",
        "deliver_method",
        "sale_type",
    ],
    "bazar": [
        "delivery_time",
        "description",
        "deliver_type",
        "deliver_method",
    ],
    "superuser": [
        "address", "delivery_time", "description", "guid",
        "sepidar_number", "sepidar_id", "sepidar_inventory_delivery_number",
        "sepidar_inventory_delivery_id", "sepidar_voucher_number",
        "sepidar_voucher_id", "fiscalyearref", "factor_self", "self_discount",
        "is_official", "official_value", "cancel", "sale_type",
        "need_financial_approval", "wh_user", "to_be_collected",
        "collecting_start_time", "collecting_end_time", "final_check",
        "require_official_factor_with_delivery",
        "official_factor_send_with_this_factor",
        "official_factor_for_this_factor", "deliver_type", "deliver_to_customer",
        "need_factor_document", "checker", "packing_json", "deliver_method",
        "accounting_confirm", "force_factor", "sales_admin_confirm",
    ],
}

# ─── فیلدهای مجاز FactorItem به ازای هر گروه ─────────────────────────────────

FACTOR_ITEM_FIELDS_BY_GROUP = {
    "sales": [
        "factor"
        "goods_code",
        "part_number_show",
        "price",
        "quantity",
        "delivery_time",
        "discount_per_item",
        "description",
    ],
    "wh": [
        "supply_locations",
        "supply_location",
        "reserve_count",
        "quantity",
    ],
    "accounting": [
        "price",
        "custom_price",
        "discount_per_item",
    ],
    "office": [
        "goods_code",
        "part_number_show",
        "quantity",
        "delivery_time",
        "description",
    ],
    "trade": [
        "goods_code",
        "price",
        "quantity",
        "delivery_time",
        "supply_location",
        "description",
    ],
    "bazar": [
        "goods_code",
        "price",
        "quantity",
        "delivery_time",
        "description",
        "is_bazar",
    ],
    "superuser": [
        "goods_code", "part_number_show", "price", "index", "quantity",
        "delivery_time", "custom_price", "supply_locations", "supply_location",
        "reserve_count", "discount_per_item", "is_bazar",
        "customer_request_item", "description",
    ],
}


# ─── helper: گروه کاربر ───────────────────────────────────────────────────────

def _get_group_key(user):
    if user.is_superuser:
        return "superuser"
    return getattr(user, "base_group", None)


# ─── فرم Factor ───────────────────────────────────────────────────────────────

class FactorEditForm(forms.ModelForm):
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

    def __init__(self, *args, allowed_fields=None, **kwargs):
        super().__init__(*args, **kwargs)
        if allowed_fields is not None:
            for field_name in list(self.fields):
                if field_name not in allowed_fields:
                    del self.fields[field_name]


# ─── فرم FactorItem ───────────────────────────────────────────────────────────

class FactorItemForm(forms.ModelForm):
    class Meta:
        model = FactorItem
        fields = "__all__"
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, allowed_fields=None, **kwargs):
        super().__init__(*args, **kwargs)
        if allowed_fields is not None:
            for field_name in list(self.fields):
                if field_name not in allowed_fields:
                    del self.fields[field_name]


# ─── فابریک inline formset با فیلترینگ ───────────────────────────────────────

def get_factor_item_formset(user, *args, **kwargs):
    """
    یک inline formset برای FactorItem با فیلدهای محدودشده بر اساس گروه کاربر برمی‌گرداند.
    """
    group = _get_group_key(user)
    allowed = FACTOR_ITEM_FIELDS_BY_GROUP.get(group, [])

    # فیلدهایی که در فرم مجاز هستند + فیلد اجباری factor (مخفی)
    form_fields = allowed if allowed else ["quantity"]

    # یک فرم پویا با فیلدهای مجاز می‌سازیم
    class _FactorItemForm(FactorItemForm):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, allowed_fields=form_fields, **kwargs)

    FactorItemInlineFormset = inlineformset_factory(
        Factor,
        FactorItem,
        form=_FactorItemForm,
        extra=0,        # ردیف خالی اضافه نمی‌شود؛ در template با JS مدیریت کنید
        can_delete=True,
    )
    return FactorItemInlineFormset(*args, **kwargs)


# ─── View ─────────────────────────────────────────────────────────────────────

class FactorEditView(LoginRequiredMixin, UpdateView):
    """
    ویرایش فاکتور + ردیف‌های FactorItem به صورت inline.

    URL:
        path('factors/<int:pk>/edit/', FactorEditView.as_view(), name='factor_edit'),
    """

    model = Factor
    template_name = "sls/factor_edit.html"

    # ── helpers ──────────────────────────────────────────────────────────────

    def _get_factor_allowed_fields(self):
        group = _get_group_key(self.request.user)
        allowed = FACTOR_FIELDS_BY_GROUP.get(group, [])
        if not allowed:
            raise PermissionDenied("شما دسترسی لازم برای ویرایش این فاکتور را ندارید.")
        return allowed

    def _build_factor_form(self, **kwargs):
        allowed = self._get_factor_allowed_fields()
        return FactorEditForm(allowed_fields=allowed, **kwargs)

    def _build_item_formset(self, **kwargs):
        return get_factor_item_formset(self.request.user, **kwargs)

    # ── django UpdateView hooks ───────────────────────────────────────────────

    def get_form(self, form_class=None):
        return self._build_factor_form(**self.get_form_kwargs())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.method == "POST":
            context["item_formset"] = self._build_item_formset(
                data=self.request.POST,
                instance=self.object,
            )
        else:
            context["item_formset"] = self._build_item_formset(
                instance=self.object,
            )
        context["factor"] = self.object
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        item_formset = context["item_formset"]

        if not item_formset.is_valid():
            return self.form_invalid(form)

        with transaction.atomic():
            form.instance.editor_user = self.request.user
            self.object = form.save()

            items = item_formset.save(commit=False)
            for item in items:
                item.editor_user = self.request.user
                item.save()
            for deleted in item_formset.deleted_objects:
                deleted.delete()

        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("factor_edit", kwargs={"pk": self.object.pk})
