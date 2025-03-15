from django.contrib import admin

from order.models import Order, OrderOrder, OrderPayment, OrderPaymentItem, Packing, PackingItem, GIO, GIOItem, ACNT

# Register your models here.
admin.site.register([Order, OrderOrder, OrderPayment, OrderPaymentItem, PackingItem, Packing, GIO, GIOItem])


class ACNTAdmin(admin.ModelAdmin):
    readonly_fields = ('last_work_flow',)  # فیلدهای فقط خواندنی


admin.site.register(ACNT, ACNTAdmin)
