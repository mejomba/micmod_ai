from django.contrib import admin

from .models import PriceSettings, PriceInquiryResult, PriceInquiryFile, Supplier, InquiryResultVariant

# Register your models here.

admin.site.register([PriceSettings,PriceInquiryFile,PriceInquiryResult, Supplier, InquiryResultVariant])