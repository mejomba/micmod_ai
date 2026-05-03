from django import template

from extra_data import models
register = template.Library()


@register.inclusion_tag('factor/partial/supply_locations.html')
def supply_locations(item: "models.Item", prefix, counter, factor_item=None, user=None):
    context = dict()
    if not isinstance(item, models.Item):
        item = models.Item.objects.filter(sku=item).first()
    # if factor_item:
    #     factor_item.quantity
    # context['locations'] = item.supply_locations_ if item else ['', '']
    context['prefix'] = prefix
    context['counter'] = counter
    context['factor_item'] = factor_item
    context['user'] = user
    return context


@register.simple_tag
def get_last_currency_amount(currency):
    from inquiry.models import CurrencyAmount
    currency_amount = CurrencyAmount.objects.filter(currency=currency.id).order_by('-id').first()
    open_rate = currency_amount.open_rate
    return int(open_rate)
