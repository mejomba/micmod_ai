from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from micmod_base.models import QuotationItem
from order.models import OrderItem


def factor_order_item(request, sku, quantity):
    items = get_object_or_404(QuotationItem, goods_code=sku)

    for item in items.goods_code:
        order_item = OrderItem.objects.create(order__title=item)



