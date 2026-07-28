import datetime
import json
import re

from django.db.models import Q
from django.urls import reverse
from django.utils.safestring import mark_safe
from django import template
from _keenthemes.libs.theme import KTTheme
from django.conf import settings
from pprint import pprint
from django.apps import apps
from django.apps import apps

from core.models import PinUrl
from guides.models import Guides
from tools.utils import show_error

register = template.Library()
import ast
from django.contrib.humanize.templatetags.humanize import intcomma,number_format
from tools.myjalali import JalalyDate
import re
from django.core.cache import cache

# Register tags as an adapter for the Theme class usage in the HTML template

@register.filter
def c_add(m_str, value):
    try:
        m_str = m_str or ''
        value = value or ''
        if value and (isinstance(value,datetime.date) or isinstance(value,datetime.datetime)):
            value = JalalyDate(value).get_persian_date_time('{y}/{m}/{d}')
        return f'{m_str}{value}'
    except:
        return m_str


@register.filter
def c_get(obj, attr_name, default_value=None):
    try:
        return getattr(obj, attr_name, default_value)
    except Exception as e:
        show_error(e, __file__)
        return default_value


@register.filter
def v_add(value1, value2):
    try:
        return value1 + value2
    except:
        return ''

@register.filter
def v_subtract(value1, value2):
    try:
        return value1 - value2
    except:
        return ''


@register.filter
def v_multiply(value1, value2):
    try:
        return value1 * value2
    except:
        return ''


@register.filter
def v_divide(value1, value2):
    try:
        return value1 / value2
    except:
        return ''


@register.filter
def percentage_format(value,digits=None,use_l10n=True):
    try:
        value = round(100 * value, 2)
        if not digits:
            if round(value,0) == value:
                digits = 0
            elif round(value, 1) == value:
                digits = 1
            else:
                digits = 2
        return f'%{number_format(value=round(value,2),decimal_pos=digits,use_l10n=use_l10n,force_grouping=True)}'
    except:
        return ''

@register.filter
def default(value, m_default):
    try:
        return value or m_default
    except:
        ...

@register.simple_tag
def check_is_digits(value):
    if isinstance(value, str):
        chars = re.findall('\w', value)
        if chars:
            return ''
        else:
            return 'persian-digit'
    else:
        return 'persian-digit'

@register.filter
def humanized_format(value, digits=None, use_l10n=True):
    try:
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
            for k in range(digits):
                if round(value, k) == value:
                    digits = k
                    break
        value = number_format(value=value,decimal_pos=digits,use_l10n=use_l10n,force_grouping=True)
        return value
    except:
        return None

@register.simple_tag
def get_object_count(user, count_str):
    app_model, q = count_str.split(':')
    app, model = app_model.split(".")
    cache_key = f'{count_str}__{user.pk}'
    data = cache.get(cache_key)
    if data:
        return data
    else:
        model_ = apps.get_model(app, model)
        function = getattr(model_, q, None)
        if function:
            data = function(user)
            cache.set(cache_key, data, 300)
            return data


@register.simple_tag
def get_list(field):
    m_list = []
    objs = field.subwidgets
    selected_str = ''
    try:
        for obj in objs:
            value = obj.data['value'] if isinstance(obj.data['value'],str) else obj.data['value'].value
            m_list.append(
                (value,
                 obj.data['label'],
                 'selected' if obj.data['selected'] else ''))
            if obj.data['selected']:
                selected_str = obj.data['label'] if obj.data['label'] != '---------' else ''
        return {'list': m_list, 'selected_str': selected_str}
    except Exception as e:
        return {'list': m_list, 'selected_str': selected_str}

@register.filter
def get_base_model(field):
    if getattr(field,'field',None) and getattr(field.field,'queryset',None) is not None:
        return re.findall("'[\d\w\.]+'",str(field.field.queryset.model))[0][1:-1]
@register.simple_tag
def get_attrs_str(field):
    m_str = ""
    for attr, value in field.field.widget.attrs.items():
        if attr != "class":
            m_str += f""" {attr}="{value}" """
    return mark_safe(m_str)

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
def show_field_value(field):
    ...
    
    
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


@register.filter
def reminder(number, x):
    try:
        return number / int(x)
    except Exception as e:
        return 0


@register.simple_tag
def appearance_or_real_part_number(item, customer):
    try:
        customer_factor_item = item.factor_goods_code.filter(qi__quotation__customer_party_id=customer).first()
        if customer_factor_item:
            return customer_factor_item.part_number_show
        else:
            return item.part_number
    except Exception as e:
        print(e)


def appearance_or_real_part_number_(item, customer):
    try:
        l = [("", "--------", "selected")]
        for i in item.factor_goods_code.filter(qi__quotation__customer_party_id=customer):
            l.append((i.pk, item.part_number_show, ''))
        return {'list': l}
    except Exception as e:
        ...

@register.filter
def filter_queryset(queryset, filter_str):
    try:
        import ast
        filter_dict = ast.literal_eval(filter_str)
        x = queryset.filter(**filter_dict)
        return x
    except Exception as e:
        show_error(e, __file__)


@register.filter
def max_(a, b):
    return max([a, int(b)])


@register.filter
def abs_(a):
    return abs(a)


@register.inclusion_tag('core/partial/table_responsive.html')
def table_responsive(objs, fields=None, title=None):
    rows = dict()
    fields_pair = fields.split(',') if fields else None
    fields_pair_list = list(map(lambda x: x.split('|'), fields_pair))
    if fields:
        for idx, obj in enumerate(objs):
            if rows.get(idx) is None:
                rows[idx] = []

            for field in obj._meta.get_fields():
                for field_pair in fields_pair_list:
                    if field.name in field_pair:
                        rows[idx] = {field.name: getattr(obj, field.name)}
                        break
                # rows[idx] = {field.name: getattr(obj, field.name) for field in obj._meta.get_fields() if field.name in fields_[0]}
            rows[idx].update({'action_': mark_safe(f"""
                                            <span>
                                            <a href="#" target="_blank" class="me-3 edit-packing-item tooltip_" data-url="{reverse('order:packingitem.update', kwargs={'pk': obj.pk})}" data-bs-toggle="modal" data-bs-target="#id_kt_empty_modal_lg">
                                                <span class="tooltiptext">ویرایش</span>
                                                <i class="ki-duotone ki-pencil fs-2 text-info">
                                                    <span class="path1"></span>
                                                    <span class="path2"></span>
                                                </i>
                                            </a>
                                            <a href="#" target="_blank" class="me-3 delete-packing-item text-danger tooltip_" data-url="{reverse('core:delete.confirm')}?model={ obj._meta.model_name}&object_id={ obj.pk }&app_label={ obj._meta.app_label }" data-bs-toggle="modal" data-bs-target="#id_kt_empty_modal_sm">
                                                <span class="tooltiptext">حذف</span>
                                                <i class="ki-duotone ki-trash fs-2 text-danger">
                                                    <span class="path1"></span>
                                                    <span class="path2"></span>
                                                    <span class="path3"></span>
                                                    <span class="path4"></span>
                                                    <span class="path5"></span>
                                                </i>
                                            </a>
                                            <a class="mx-4 tooltip_ cursor-pointer"
                                                data-bs-toggle="modal"
                                                data-bs-target="#id_kt_empty_modal_lg"
                                                data-model_name="{ obj._meta.model_name }"
                                                data-object_id="{ obj.pk }"
                                                data-app_name="{ obj._meta.app_label }"
                                                name="name_change_log">
                                                <span class="tooltiptext">تاریخچه تغییرات</span>
                                                <i class="ki-duotone ki-book-open fs-2 text-primary">
                                                 <span class="path1"></span>
                                                 <span class="path2"></span>
                                                 <span class="path3"></span>
                                                 <span class="path4"></span>
                                                </i>
                                            </a>
                                        </span>""")})

        context = dict()
        context['rows'] = rows
        context['title'] = title
        return context


@register.filter
def typename(obj):
    return type(obj).__name__.lower()


@register.simple_tag()
def guide_for_each_model(section_id, user):
    guide = Guides.objects.filter(
        Q(section_id=section_id) &
        (Q(team=user.base_group) if user else Q())
    ).first()
    return guide.id if guide else None


@register.simple_tag()
def user_pins(request):
    user = request.user

    pins = PinUrl.objects.filter(user=user, is_active=True)
    # pin_data = [(pin.id, pin.pin_url.url, pin.pin_url.title) for pin in pins]
    return pins
