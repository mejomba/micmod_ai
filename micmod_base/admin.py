from django.contrib import admin
from .models import Quotation,QuotationItem, Month, SaleType
from .base import Currency,CurrencyExchange
# Register your models here.

admin.site.register([Quotation, Currency,QuotationItem,CurrencyExchange, Month, SaleType])

