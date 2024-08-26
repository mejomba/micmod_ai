from django import template

from extra_data import models
register = template.Library()


@register.inclusion_tag('factor/partial/supply_locations.html')
def supply_locations(item: "models.Item", prefix, counter):
    context = dict()
    if not isinstance(item, models.Item):
        item = models.Item.objects.filter(sku=item).first()
    context['locations'] = item.supply_locations if item else []
    context['prefix'] = prefix
    context['counter'] = counter
    return context
