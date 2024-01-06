import json

from django.utils.safestring import mark_safe
from django import template
from _keenthemes.libs.theme import KTTheme
from django.conf import settings
from pprint import pprint
from django.apps import apps
register = template.Library()

# Register tags as an adapter for the Theme class usage in the HTML template

@register.simple_tag
def get_object_count(user, count_str):
    app_model, q = count_str.split(':')
    app, model = app_model.split(".")
    model_ = apps.get_model(app, model)
    return len(model_.objects.get_access_object(user, q=q))

