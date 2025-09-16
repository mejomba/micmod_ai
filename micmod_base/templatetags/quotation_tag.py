from django import template

from extra_data.models import Item
from sepidar.models import Dl
from micmod_base.base import *

register = template.Library()

@register.simple_tag
def get_customer(customer_id):
    from extra_data.models import Customer
    if customer_id:
        customer = Customer.get_list(customer_id)
        if len(customer) > 0:
            customer = customer[0]
            return customer
    # if customer_id:
        # customer = Dl.get_list(customer_id)
        # if len(customer) > 0:
            # customer = customer[0]
            # return customer

    # if customer_id:
    #     customer = Dl.get_list(customer_id)
    #     if len(customer) > 0:
    #         customer = customer[0]
            # return customer

@register.simple_tag
def get_item(item_id):
    if item_id:
        item = Item.get_list(item_id)
        if len(item) > 0:
            item = item[0]
            return item
        return None
@register.simple_tag
def get_customer_from_pg(customer_id):
    from extra_data.models import Customer
    if customer_id:
        customer = Customer.get_list(customer_id)
        if len(customer) > 0:
            customer = customer[0]
            return customer

@register.simple_tag
def get_price_method(value):
    return value
    if not value:
        return ""
    price_method = dict(PriceMethod)
    return price_method[value]

@register.simple_tag
def get_delivery_time(value):
    if not value:
        return ""
    delivery_time = dict(DeliveryTime)
    return delivery_time[value]

@register.simple_tag
def get_payment_method(value):
    if not value:
        return ""
    payment_method = dict(PaymentMethod)
    return payment_method[value]

@register.simple_tag
def get_customer_grade(value):
    if not value:
        return ""
    customer_grade = dict(CustomerGrade)
    return customer_grade[value]

@register.simple_tag
def get_market_grade(value):
    if not value:
        return ""
    market_grade = dict(MarketGrade)
    return market_grade[value]

@register.simple_tag
def get_status(value):
    if not value:
        return ""
    status = dict(Status)
    return status[value]
