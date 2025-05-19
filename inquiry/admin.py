from django.contrib import admin

from core.admin import BaseJsonFieldAdmin
from .models import PriceSettings, PriceInquiryResult, PriceInquiryFile, Supplier, InquiryResultVariant, AllowedInquiry

# Register your models here.

admin.site.register([PriceInquiryFile,PriceInquiryResult, Supplier, InquiryResultVariant, AllowedInquiry])


@admin.register(PriceSettings)
class PriceSettingsAdmin(BaseJsonFieldAdmin):
    pass