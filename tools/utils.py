import math
from typing import List, Dict
import pandas
import pytz
from dateutil.relativedelta import relativedelta
import time

from _keenthemes.settings import TIME_ZONE
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

