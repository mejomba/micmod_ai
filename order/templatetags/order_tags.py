from django import template

from order import models
register = template.Library()


@register.simple_tag
def total_supply(factor_item):
    s = sum([x.quantity for x in factor_item.supply_locations.order_base_items.all()])
    quantity = factor_item.quantity
    status = True if s == quantity else False
    return s, quantity, status
