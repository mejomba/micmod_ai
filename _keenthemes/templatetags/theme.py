import json

from django.utils.safestring import mark_safe
from django import template
from _keenthemes.libs.theme import KTTheme
from django.conf import settings
from pprint import pprint

register = template.Library()

# Register tags as an adapter for the Theme class usage in the HTML template

@register.simple_tag
def includeFonts():
    return mark_safe(KTTheme.includeFonts())

@register.simple_tag
def includeFavicon():
    return mark_safe(KTTheme.includeFavicon())

@register.simple_tag
def getSvgIcon(path, classNames = 'svg-icon', folder = 'media/icons/'):
    return mark_safe(KTTheme.getSvgIcon(path, classNames, folder))

@register.simple_tag
def printHtmlClasses(scope):
    return mark_safe(KTTheme.printHtmlClasses(scope))

@register.simple_tag
def printHtmlAttributes(scope):
    return mark_safe(KTTheme.printHtmlAttributes(scope))

@register.simple_tag
def getGlobalAssets(type):
    return KTTheme.getGlobalAssets(type)

@register.simple_tag
def getCustomJs():
    return KTTheme.javascriptFiles

@register.simple_tag
def getCustomCss():
    return KTTheme.cssFiles

@register.simple_tag
def getVendors(type):
    return KTTheme.getVendors(type)

@register.simple_tag
def isRtlDirection():
    return KTTheme.isRtlDirection()

@register.simple_tag
def asset(path):
    return KTTheme.asset(path)

@register.simple_tag
def getModeDefault():
    return KTTheme.getModeDefault()

@register.simple_tag
def addHtmlAttribute(scope, name, value):
    KTTheme.addHtmlAttribute(scope, name, value)
    return ''

@register.simple_tag
def path_has_key(req_path, search_key, class_):
    if not search_key:
        return ""
    if search_key.endswith("/"):
        if req_path.endswith(search_key):
            return f" {class_} "
        else:
            return ""
    if req_path.__contains__(search_key):
        return f" {class_} "
    else:
        return ""

@register.simple_tag
def get_menus():
    return json.load(open('_templates/layout/partials/sidebar-layout/sidebar/_menu.json','r', encoding="utf8"))


@register.simple_tag
def get_bi_menus(user):
    from dashboards.models import BIReport
    reports = BIReport.objects.filter(user_list=user)
    menus = []
    m = []
    for report in reports:
        sub_menu = {
                "permission": {
                    "permissions": [
                        ""
                    ],
                    "groups": [
                        "base_user"
                    ]
                },
                "title": f"{report.name}",
                "path_key": "dashboard",
                "icon": "",
                "direct_link": f"/dashboards/bi?report_url={report.url}",
                "link": ""
            }
        m.append(sub_menu)
    menu = {
        "title": "Dashboard",
        "section": "False",
        "icon": "element-11",
        "path_key": "dashboard",
        "permission": {
            "permissions": [
                ""
            ],
            "groups": [
                "base_user"
            ]
        },
        "menus": m
    }

    menus.append(menu)
    return menus


@register.simple_tag
def addHtmlAttributes(scope, attributes):
    KTTheme.addHtmlAttributes(scope, attributes)
    return ''

@register.simple_tag
def addHtmlClass(scope, value):
    KTTheme.addHtmlClass(scope, value)
    return ''

@register.simple_tag
def getHtmlAttribute(scope, attribute):
    return KTTheme.htmlAttributes[scope][attribute]

@register.simple_tag
def getIcon(name, class_name='', type=''):
    return mark_safe(KTTheme.getIcon(name, class_name, type))
