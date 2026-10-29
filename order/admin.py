from django.contrib import admin

from order.models import Order, OrderOrder, OrderPayment, OrderPaymentItem, Packing, PackingItem, GIO, GIOItem, ACNT, PackingSepidarTransfer, PackingSepidarTransferItem

# Register your models here.
admin.site.register([Order, OrderOrder, OrderPayment, OrderPaymentItem, PackingItem, Packing, GIO, GIOItem])


class ACNTAdmin(admin.ModelAdmin):
    readonly_fields = ('last_work_flow',)  # فیلدهای فقط خواندنی


admin.site.register(ACNT, ACNTAdmin)


class PackingSepidarTransferItemInline(admin.TabularInline):
    model = PackingSepidarTransferItem
    extra = 0
    can_delete = False
    readonly_fields = ('packing_item', 'item_ref', 'quantity')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PackingSepidarTransfer)
class PackingSepidarTransferAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'packing', 'transfer_type', 'source_stock_ref',
        'destination_stock_ref', 'status', 'delivery_number',
        'receipt_number', 'attempt_count', 'sent_at',
    )
    list_filter = ('status', 'transfer_type', 'destination_stock_ref')
    search_fields = ('packing__id', 'delivery_number', 'receipt_number')
    readonly_fields = (
        'packing', 'transfer_type', 'source_stock_ref', 'destination_stock_ref',
        'status', 'delivery_id', 'delivery_number', 'receipt_id',
        'receipt_number', 'attempt_count', 'sent_at', 'last_error',
        'request_payload', 'response_payload',
    )
    inlines = (PackingSepidarTransferItemInline,)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
