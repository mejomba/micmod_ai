from django.contrib import admin

from order.models import Order, OrderOrder

# Register your models here.
admin.site.register([Order, OrderOrder])
