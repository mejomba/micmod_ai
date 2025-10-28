from django import template

from order import models
register = template.Library()


@register.simple_tag
def total_supply(factor_item):
    s = sum([x.quantity for x in factor_item.supply_locations.order_base_items.all()])
    quantity = factor_item.quantity
    status = True if s == quantity else False
    return s, quantity, status


@register.simple_tag
def get_order_pair(order_rel, main_order_pk):
    order_pair = order_rel.order_rel_items.get(order_base=main_order_pk)
    return order_pair


@register.inclusion_tag('order/partial/other_available_orders.html')
def other_available_orders(main_order: "models.Order"):
    item = main_order.item
    illegal_order_ids = list(map(lambda x: x.pk, filter(lambda x: x.remaining_quantity <= 0, main_order.order_m2m.all()))) if main_order.pk else []
    illegal_order_ids.append(main_order.pk)
    other_orders = main_order.__class__.objects.filter(item=item).exclude(pk__in=illegal_order_ids)
    context = dict()

    context['other_orders'] = other_orders
    return context
