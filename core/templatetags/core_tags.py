import datetime
import json

from django.utils.safestring import mark_safe
from django import template
from _keenthemes.libs.theme import KTTheme
from django.conf import settings
from pprint import pprint
from django.apps import apps
from django.apps import apps
register = template.Library()
import ast
from django.contrib.humanize.templatetags.humanize import intcomma,number_format
from tools.myjalali import JalalyDate

# Register tags as an adapter for the Theme class usage in the HTML template

@register.filter
def humanized_format(value, digits=None, use_l10n=True):
    if value and isinstance(value, datetime.date):
        if not digits:
            digits = "{y}/{m}/{d} \n{H}:{M}"
        return JalalyDate(value).get_persian_date_time(digits)
    if value and isinstance(value, datetime.datetime):
        if not digits:
            digits = "{y}/{m}/{d} \n{H}:{M}"
        return JalalyDate(value).get_persian_date_time(digits)
    try:
        value = float(value)
    except:
        return value
    if not digits or isinstance(digits, str):
        value_ = abs(value)
        if value_ < 100:
            digits = 4
        elif value_ < 1000:
            digits = 2
        else:
            digits = 0
        if int(value) == value:
            digits = 0
    value = number_format(value=value,decimal_pos=digits,use_l10n=use_l10n,force_grouping=True)
    return value

@register.simple_tag
def get_object_count(user, count_str):
    app_model, q = count_str.split(':')
    app, model = app_model.split(".")
    model_ = apps.get_model(app, model)
    return len(model_.objects.get_access_object(user, q=q))

@register.simple_tag
def get_list(field):
    m_list = []
    objs = field.subwidgets
    selected_str = ''
    for obj in objs:
        value = obj.data['value'] if isinstance(obj.data['value'],str) else obj.data['value'].value
        m_list.append(
            (value,
             obj.data['label'],
             'selected' if obj.data['selected'] else ''))
        if obj.data['selected']:
            selected_str = obj.data['label'] if obj.data['label'] != '---------' else ''
    return {'list': m_list, 'selected_str': selected_str}

@register.simple_tag
def get_attrs_str(field):
    m_str = ""
    for attr, value in field.field.widget.attrs.items():
        if attr != "class":
            m_str += f" {attr} = {value}"
    return m_str

@register.simple_tag
def replace(m_str, old_str, new_str):
    if m_str and old_str:
        return m_str.replace(old_str, new_str)
    else:
        return m_str

@register.simple_tag
def contains(m_str, search):
    if m_str and search:
        return "m_str".__contains__(search)
    else:
        return False

@register.simple_tag
def call_function(obj, function_name, *args, kwargs=None):
    function = getattr(obj, function_name, None)
    if function:
        if isinstance(kwargs, str):
            kwargs = ast.literal_eval(kwargs)
        if kwargs:
            return function(*args, **kwargs)
        else:
            return function(*args)