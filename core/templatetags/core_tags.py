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
    if getattr(field.field,'queryset',None) and field.field.queryset.model.auto_complete:
        model = field.field.queryset.model
        objs = model.objects.all()
        for obj in objs:
            m_item = getattr(obj, model.auto_complete, None)
            if m_item:
                m_list.append(m_item)
    # if source_string:
    #     sources = source_string.split(".")
    #     if len(sources) == 3:
    #         model = apps.get_model(sources[0], sources[1])
    #         objs = model.objects.all()
    #         for obj in objs:
    #             m_list.append(getattr(obj, sources[2]))
    return m_list

