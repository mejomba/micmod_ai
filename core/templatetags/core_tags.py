import json

from django.utils.safestring import mark_safe
from django import template
from _keenthemes.libs.theme import KTTheme
from django.conf import settings
from pprint import pprint
from django.apps import apps
from django.apps import apps
register = template.Library()

# Register tags as an adapter for the Theme class usage in the HTML template

@register.simple_tag
def get_object_count(user, count_str):
    app_model, q = count_str.split(':')
    app, model = app_model.split(".")
    model_ = apps.get_model(app, model)
    return len(model_.objects.get_access_object(user, q=q))

@register.simple_tag
def get_list(field):
    m_list = []
    # if field.widget_type == 'select' and getattr(field.field,'queryset',None):
    #     model = field.field.queryset.model
    #     if getattr(model,'auto_complete',None):
    #         objs = model.objects.all()
    #         for obj in objs:
    #             m_item = getattr(obj, model.auto_complete, None)
    #             if m_item:
    #                 m_list.append((m_item,m_item,''))
    #     else:
    #         objs = field.subwidgets
    #         for obj in objs:
    #             value = obj.data['value']
    #             m_list.append((value if value == '' else value.value,obj.data['label'],'selected' if obj.data['selected'] else ''))
    # elif getattr(field.field,'choices', None):
    #     objs = field.field.choices
    #     for obj in objs:
    #         m_list.append((obj[0], obj[1],''))
    objs = field.subwidgets
    selected_str = ''
    for obj in objs:
        value = obj.data['value'] if isinstance(obj.data['value'],str) else obj.data['value'].value
        m_list.append(
            (value,
             obj.data['label'],
             'selected' if obj.data['selected'] else ''))
        if obj.data['selected']:
            selected_str = obj.data['label']
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