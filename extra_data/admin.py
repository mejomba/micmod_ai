from django.contrib import admin
from .models import ItemWeight,Item, HS, PurchaseGroup, SaleGroup, Customer, WH

# Register your models here.

admin.site.register([ItemWeight,Item, HS,PurchaseGroup, SaleGroup, Customer])


class WHAdmin(admin.ModelAdmin):
    list_display = ['id', 'backend_name', 'front_name', 'creator_user', 'editor_user']


admin.site.register(WH, WHAdmin)