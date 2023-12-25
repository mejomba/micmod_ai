from django.contrib import admin

from .models import PriceSettings,PriceInquiryResult,PriceInquiryFile
# Register your models here.

admin.site.register([PriceSettings,PriceInquiryFile,PriceInquiryResult])