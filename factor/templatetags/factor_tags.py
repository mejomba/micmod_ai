from django import template

from extra_data import models
register = template.Library()


@register.inclusion_tag('factor/partial/supply_locations.html')
def supply_locations(item: "models.Item") -> None:
    context = {}
    item.supply_locations
    return context
