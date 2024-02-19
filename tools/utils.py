import math
from typing import List, Dict
import pandas
import pytz
from dateutil.relativedelta import relativedelta
# from django.contrib.auth import get_user_model
# from django.contrib.contenttypes.models import ContentType
# from django.db.models import Q,Model
# from django.db import connection

from _keenthemes.settings import TIME_ZONE
from . import myjalali
import datetime
# from workflow.models import FlowAdminGroup, WorkFlow
from forbiddenfruit import curse


def c_get(obj, attr_name, default_value=None):
    try:
        return getattr(obj, attr_name, default_value)
    except Exception as e:
        show_error(e, __file__)
        return default_value


curse(object, "c_get", c_get)

def get_tuple_value_list(m_list:List[dict], key):
    return [(item.get(key), item.get(key)) for item in m_list]


def get_value_list(m_list:List[dict], key):
    return [item.get(key) for item in m_list]


def is_ajax(request):
    return request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'


def read_excel_data(file,header_row=1) -> List[Dict]:
    wb = pandas.read_excel(file, header=header_row)
    header = wb.columns.ravel()
    # wb = pandas.read_excel(file, usecols=header)
    wb = pandas.read_excel(file, header=header_row)
    datas = wb.to_dict(orient='records')
    for data in datas:
        for key in data.keys():
            if isinstance(data[key],float) and math.isnan(data[key]):
                data[key] = None
    return datas


def elapsed_time(m_datetime):
    delta = datetime.datetime.now(tz=pytz.timezone(TIME_ZONE)) - m_datetime
    relative_delta = relativedelta(datetime.datetime.now(tz=pytz.timezone(TIME_ZONE)), m_datetime)
    m_str = ""
    if delta.seconds < 60:
        return f"تقریبا هم اکنون"
    elif delta.seconds < 2592000:  # day&hour&minute
        m_str += f'{relative_delta.days} روز' if relative_delta.days else ''
        m_str += " و " if m_str else ""
        m_str += f'{relative_delta.hours} ساعت' if relative_delta.hours else ''
        m_str += " و " if m_str and relative_delta.hours else ""
        m_str += f'{relative_delta.minutes} دقیقه' if relative_delta.minutes else ''
    else:# year&month&day
        m_str += f'{relative_delta.years} سال' if relative_delta.years else ''
        m_str += " و " if m_str else ""
        m_str += f'{relative_delta.months} ماه' if relative_delta.months else ''
        m_str += " و " if m_str and relative_delta.months else ""
        m_str += f'{relative_delta.days} روز' if relative_delta.days else ''
    return f'{m_str} قبل'


def to_persian_number(mystr):
    number = {
        "0": "۰",
        "1": "۱",
        "2": "۲",
        "3": "۳",
        "4": "۴",
        "5": "۵",
        "6": "۶",
        "7": "۷",
        "8": "۸",
        "9": "۹",
    }

    for k, v in number.items():
        mystr = mystr.replace(k, v)

    return mystr


def to_jalali_date(time):
    try:
        jtime = myjalali.Gregorian(time).persian_tuple()
        jtime_list = list(jtime)
        output = '{}/{}/{}'.format(jtime_list[0], jtime_list[1], jtime_list[2])
        return output
    except Exception as e:
        print('error ', __file__, e.__traceback__.tb_lineno, e)
        return '1000/01/01'

#
# def get_target_user_from_group(group, level=1):
#     print('group: ', group)
#     qs = get_user_model().objects.filter(pk=-1)
#     if level > 1:
#         qs |= group.user_set.all()
#         print(qs)
#     for g in FlowAdminGroup.objects.filter(group_rel=group):
#         for gc in g.group_child.all():
#             qs |= get_target_user_from_group(gc, level+1)
#     print('qs before return ', qs)
#     return qs
# # from tools.utils import get_target_users
# # from accounts.models import User
# # x = User.objects.get(username='u2')
# # get_target_users(x)
#
# def get_target_users(user):
#     user_qs = get_user_model().objects.filter(id=user.id)
#     for main_user_group in user.groups.all():
#         user_qs |= get_target_user_from_group(main_user_group)
#     print('user_list  > ', user_qs)
#     return user_qs
#
#
# def get_target_wf(user):
#     user_list = get_target_users(user)
#     wf = WorkFlow.objects.filter(id=-1)
#     for user in user_list:
#         wf |= WorkFlow.objects.filter(
#             Q(creator_user=user) |
#             Q(editor_user=user) |
#             Q(from_user=user) |
#             Q(to_user=user)
#         )
#     return wf
#
#
# def get_access_object(user, model):
#     content_type = ContentType.objects.filter(model=model._meta.model_name, app_label=model._meta.app_label).first()
#
#     wfs = get_target_wf(user)
#     object_id_from_flow = wfs.filter(content_type=content_type).values_list('object_id', flat=True)
#
#     user_list = get_target_users(user)
#     objects_from_user = model.objects.filter(
#         Q(creator_user__in=user_list) |
#         Q(editor_user__in=user_list)
#     )
#     objects_from_flow = model.objects.filter(pk__in=object_id_from_flow)
#     return objects_from_user | objects_from_flow


def show_error(e, file):
    print("error: ", file, e.__traceback__.tb_lineno, e)


