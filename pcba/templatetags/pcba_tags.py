# templatetags/custom_filters.py
from django import template

register = template.Library()

@register.filter
def get_part_number_list(instance, contract_id):
    return instance.part_number_list(contract_id)
