from django.contrib import admin
from .models import ItemWeight,Item, HS, PurchaseGroup, SaleGroup

# Register your models here.

admin.site.register([ItemWeight,Item, HS,PurchaseGroup, SaleGroup])
