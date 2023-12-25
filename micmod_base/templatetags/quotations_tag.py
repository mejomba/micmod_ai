from django import template
from django.template.defaultfilters import stringfilter


import translator
from micmod_base.models import Quotation
from sepidar.models import Dl

register = template.Library()

@register.filter(is_safe=True)
@stringfilter
def verbose(obj, lang='fa'):
    return translator.get_text(obj.verbose_name,lang)


@register.filter(is_safe=True)
@stringfilter
def verbose(value, lang='fa'):
    return translator.get_text(value,lang)


@register.simple_tag
def get_customer():
    print('dddd')
    return "aaa"
    # customer =  Dl.get_list(customer_id)
    # if len(customer > 0):
    #     customer = customer[0]
    #     return customer