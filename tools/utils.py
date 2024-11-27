import math
import uuid
from typing import List, Dict
import pandas
import pytz
from ajax_datatable.utils import parse_date
from dateutil.relativedelta import relativedelta
import time

from django.db import models
from django.db.models import Q

from _keenthemes.settings import TIME_ZONE
# from factor.forms import FactorModelForm, FactorItemModelForm
# from factor.models import Factor, FactorItem
# from micmod_base.models import Quotation
# from order.models import Order
from . import myjalali
import datetime
# from workflow.models import FlowAdminGroup, WorkFlow
from forbiddenfruit import curse


def c_get(obj, attrs_str, default_value=None):
    try:
        attrs = attrs_str.split('.')
        for attr in attrs:
            obj = getattr(obj, attr, None)
            if not obj:
                return default_value
        return obj if obj else default_value
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
    if not m_datetime:
        return None
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


def diff_time(first_time, second_time):
    first_time , second_time = second_time, first_time
    if not first_time and not second_time:
        return None
    delta = first_time - second_time
    relative_delta = relativedelta(first_time, second_time)
    m_str = ""
    if delta.seconds < 60:
        return f'بلافاصله'
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
    return f'{m_str} '


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


def show_error(e, file):
    print("error: ", file, e.__traceback__.tb_lineno, e)


python_model_type_map = [
('binarry', 'binaryfield'),
('boolean', 'booleanfield'),
('boolean', 'nullbooleanfield'),
('datetime', 'datefield'),
('datetime', 'timefield'),
('datetime', 'datetimefield'),
('datetime', 'durationfield'),
('int', 'autofield'),
('int', 'bigintegerfield'),
('float', 'decimalfield'),
('float', 'floatfield'),
('int', 'integerfield'),
('int', 'positiveintegerfield'),
('int', 'positivesmallintegerfield'),
('int', 'options.smallintegerfield'),
('str', 'charfield'),
('str', 'textfield'),
('str', 'commaseparatedintegerfield'),
('str', 'emailfield'),
('str', 'filefield'),
('int', 'bigautofield'),
]


def map_model_to_python_type(field):
    type_str = repr(field).lower()
    for key, value in python_model_type_map:
        if type_str.__contains__(value):
            return key


def progress_value(start_date, end_date, total_hour=72):
    try:
        time_delta = end_date - start_date
        hours, _ = divmod(time_delta.seconds, 3600)
        result = ((time_delta.days * 24 + hours) / total_hour) * 100
        if result > 100:
            result = 100
        return int(result)
    except Exception as e:
        return 0


def timer(f):
    def inner(*args, **kwargs):
        print(f.__name__, '___start')
        t1 = time.time()
        r = f(*args, **kwargs)
        t2 = time.time()
        print(f.__name__, t2 - t1)
        return r
    return inner


def round_price(x):
    return x
    if x and x / 100_000 > 1:
        # round 3 digit
        x = x / 1000
        x = int(x) * 1000
    elif x and x / 10_000 > 1:
        # round 2 digit
        x = x / 100
        x = int(x) * 100
    elif x and x / 1_000 > 1:
        # round 1 digit
        x = x / 10
        x = int(x) * 10
    return x


def round_rial(x, currency_ref=None):
    if currency_ref == 'RIAL':
        if x >= 1000_000:
            x = int(x)
            if x % 100 == 0:
                return x
            else:
                x = x / 1000
                x = (int(x) + 1) * 1000
        elif x <= 999999 or x > 10000:
            x = int(x)
            if x % 10 == 0:
                return x
            else:
                x = x / 10
                x = (int(x) + 1) * 10
        elif x <= 9999 or x > 100:
            x = int(x)
            if x % 10 == 0:
                return x
            else:
                x = x / 10
                x = (int(x) + 1) * 10
        elif (x / 10) > 1:
            x = int(x)
    return x


def build_column_filter(column_name, column_obj, column_spec, search_value=None, global_filtering=None, not_search_value=None):
    search_filter = None

    # v4.0.2: we now accept multiple search values (to be ORed),
    # now implemented for text search: "aaa+bbb" --> Q("aaa") | Q("bbb")
    # TODO: check what happens with "choices"

    if column_obj.has_choices_available:

        choices = column_spec['choices']
        if choices and not global_filtering:
            # Since we're using choices (we provided a select box)
            # just use the selected key
            values = [search_value, ]
        else:
            values = column_obj.search_in_choices(search_value)

        search_filter = Q(**{column_obj.get_field_search_path() + '__in': values})

    elif isinstance(column_obj.model_field, (models.DateTimeField, models.DateField)):

        try:
            parsed_date = parse_date(search_value)
        except ValueError:
            # when the value entered so far is not a valid date,
            # let's clear the table content to give a feedback to the user
            parsed_date = datetime.date(1,1,1)
        date_range = [parsed_date.isoformat(), parsed_date.isoformat()]
        query_param_name = column_obj.get_field_search_path()
        if isinstance(column_obj.model_field, models.DateTimeField):
            search_filter = Q(**{query_param_name + '__date__range': date_range})
        else:
            search_filter = Q(**{query_param_name + '__range': date_range})


    # elif isinstance(column_obj.model_field, models.ManyToManyField):
    #     # query_param_name = column_obj.get_field_search_path()
    #     # search_filter = Q(**{query_param_name + '__in': [search_value, ]})
    #     raise Exception('Searching not supported for ManyToManyFields (yet)')
    #     pass
    else:
        query_param_name = column_obj.get_field_search_path()

        lookup_field = column_spec['lookup_field']
        # #search_filters |= Q(**{query_param_name + '__istartswith': search_value})
        # search_filter = Q(**{query_param_name + '__icontains': search_value})

        # See: "How do I do an OR filter in a Django query?"
        # https://stackoverflow.com/questions/739776/how-do-i-do-an-or-filter-in-a-django-query
        if type(search_value) == list:
            search_filter = Q()
            for item in search_value:
                search_filter |= Q(**{query_param_name + lookup_field: item})
        elif type(not_search_value) == list:
            search_filter = Q()
            for item in not_search_value:
                if item:
                    search_filter |= ~Q(**{query_param_name + lookup_field: item})
        else:
            search_filter = Q(**{query_param_name + lookup_field: search_value})

    return search_filter


# def generate_direct_factor(request, quotation: Quotation):
#     factor_data = {
#         'q': quotation,
#         'delivery_time': quotation.delivery_time,
#         'description': 'فاکتور مستقیم',
#         'guid': uuid.uuid4(),
#         'sepidar_number': quotation.sepidar_number,
#         'is_official': quotation.is_official,
#         'official_value': quotation.official_value,
#         'sale_type': quotation.sale_type,
#     }
#     factor_form = FactorModelForm(data=factor_data)
#     if factor_form.is_valid():
#         factor = factor_form.save()
#
#         for qi in quotation.quotation.all():
#             # generate order independent
#             data_base = {
#                 "order_title": "خودکار توسط سیستم",
#                 "status": "1",
#                 "item": qi.goods_code_fk,
#                 "production_lead_time": 5,  # self.qi.lead_time,
#                 "quantity": qi.quantity,
#                 "cancel": False,
#                 "is_over": False,
#                 "qi": qi,
#                 "creator_user": qi.extra_data.request.user,
#                 "editor_user": qi.extra_data.request.user,
#             }
#             order = Order.create_with_rel(data_base)
#             factor_item_data = {
#                 'factor': factor,
#                 'qi': qi,
#                 'goods_code': qi.goods_code_fk,
#                 'part_number_show': qi.goods_code_fk.part_number,
#                 'price': qi.price,
#                 'quantity': qi.quantity,
#                 'delivery_time': qi.delivery_time,
#                 'supply_locations': order,
#                 # 'supply_location': '',
#             }
#             factor_item_form = FactorItemModelForm(data=factor_item_data)
#             if factor_item_form.is_valid():
#                 factor_item = factor_item_form.save()
