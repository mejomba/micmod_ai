from django.contrib import admin

from core.admin import BaseJsonFieldAdmin
from .models import ItemWeight,Item, HS, PurchaseGroup, SaleGroup, Customer, WH

admin.site.register([ItemWeight, HS,PurchaseGroup, SaleGroup, Customer])


class WHAdmin(admin.ModelAdmin):
    list_display = ['id', 'backend_name', 'front_name', 'creator_user', 'editor_user']


admin.site.register(WH, WHAdmin)


@admin.register(Item)
class PriceSettingsAdmin(BaseJsonFieldAdmin):
    pass
