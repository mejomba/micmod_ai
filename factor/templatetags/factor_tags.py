from django import template

from extra_data import models
register = template.Library()


@register.inclusion_tag('factor/partial/supply_locations.html')
def supply_locations(item: "models.Item", prefix, counter, factor_item=None):
    context = dict()
    if not isinstance(item, models.Item):
        item = models.Item.objects.filter(sku=item).first()
    # if factor_item:
    #     factor_item.quantity
    context['locations'] = item.supply_locations_ if item else ['', '']
    context['prefix'] = prefix
    context['counter'] = counter
    context['factor_item'] = factor_item
    return context
