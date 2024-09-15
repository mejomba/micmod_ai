from django.contrib import admin
from django.contrib.auth.models import Permission

from . import models
from django.contrib.auth.admin import UserAdmin

from django.utils.translation import gettext_lazy as _

from .extra_models import Profile
from .forms import ManageFormFieldAdminForm
# admin.site.register(models.Role)


class AdminUser(UserAdmin):
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "email",
                                         "sepidar_code", "phone", "customer_code",
                                         "telegram_code",)}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "is_customer",
                    "is_bi_user",
                    "groups",
                    "user_permissions",
                    "head",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    list_display = ("username", "email", "first_name", "last_name", "is_staff", "is_superuser", 'head', 'groups_list')

    @staticmethod
    def groups_list(obj):
        return " + ".join([g.name for g in obj.groups.all()])


admin.site.register(models.User, AdminUser)
admin.site.register([Profile, Permission])
# admin.site.register(models.User)


@admin.register(models.ManageFormField)
class ManageFormFieldAdmin(admin.ModelAdmin):
    form = ManageFormFieldAdminForm
    list_display = ['title', 'content_type', 'fields_name', 'allowed_groups_name', 'action']

    # add_form_template = 'add_field_manage_admin.html'

    @staticmethod
    def allowed_groups_name(obj):
        return ", ".join([g.name for g in obj.allowed_groups.all()])
