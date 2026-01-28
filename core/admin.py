from django.contrib import admin
from django.db import models
from django_json_widget.widgets import JSONEditorWidget

from core.models import PinUrl


class BaseJsonFieldAdmin(admin.ModelAdmin):
    def formfield_for_dbfield(self, db_field, **kwargs):
        if isinstance(db_field, models.JSONField):
            return db_field.formfield(widget=JSONEditorWidget)
        return super().formfield_for_dbfield(db_field, **kwargs)

@admin.register(PinUrl)
class PinAdmin(admin.ModelAdmin):
    pass
