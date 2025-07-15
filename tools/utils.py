import math
from typing import List, Dict
import pandas
import pytz
from ajax_datatable.utils import parse_date
from dateutil.relativedelta import relativedelta
import time
from django.db import models
from django.db.models import Q
from django.utils.timezone import make_aware
from _keenthemes.settings import TIME_ZONE
from . import myjalali
import datetime
from forbiddenfruit import curse
from requests.structures import LookupDict
import urllib.parse
import pandas as pd
from io import BytesIO


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

    if relative_delta.years:
        m_str += f'{relative_delta.years} سال' if relative_delta.years else ''
        m_str += ' و '
        m_str += f'{relative_delta.months} ماه' if relative_delta.months else ''
        m_str += ' و '
        m_str += f'{relative_delta.days} روز' if relative_delta.days else ''
    elif relative_delta.months:
        m_str += f'{relative_delta.months} ماه' if relative_delta.months else ''
        m_str += ' و '
        m_str += f'{relative_delta.days} روز' if relative_delta.days else ''
        m_str += ' و '
        m_str += f'{relative_delta.hours} ساعت' if relative_delta.hours else ''
    elif relative_delta.days:
        m_str += f'{relative_delta.days} روز' if relative_delta.days else ''
        m_str += ' و '
        m_str += f'{relative_delta.hours} ساعت' if relative_delta.hours else ''
        m_str += ' و '
        m_str += f'{relative_delta.minutes} دقیقه' if relative_delta.minutes else ''
    elif relative_delta.hours:
        m_str += f'{relative_delta.hours} ساعت' if relative_delta.hours else ''
        m_str += ' و '
        m_str += f'{relative_delta.minutes} دقیقه' if relative_delta.minutes else ''
    elif relative_delta.minutes:
        m_str += f'{relative_delta.minutes} دقیقه' if relative_delta.minutes else ''
        m_str += ' و '
        m_str += f'{relative_delta.seconds} ثانیه' if relative_delta.seconds else ''
    elif relative_delta.seconds:
        return f"تقریبا هم اکنون"

    # if delta.seconds < 60:
    #     return f"تقریبا هم اکنون"
    # else:

    # if delta.seconds < 2592000:  # day&hour&minute
    #     m_str += f'{relative_delta.days} روز' if relative_delta.days else ''
    #     m_str += " و " if m_str else ""
    #     m_str += f'{relative_delta.hours} ساعت' if relative_delta.hours else ''
    #     m_str += " و " if m_str and relative_delta.hours else ""
    #     m_str += f'{relative_delta.minutes} دقیقه' if relative_delta.minutes else ''
    # else:# year&month&day
    #     m_str += f'{relative_delta.years} سال' if relative_delta.years else ''
    #     m_str += " و " if m_str else ""
    #     m_str += f'{relative_delta.months} ماه' if relative_delta.months else ''
    #     m_str += " و " if m_str and relative_delta.months else ""
    #     m_str += f'{relative_delta.days} روز' if relative_delta.days else ''
    return f'{m_str} قبل'


def diff_time(first_time, second_time):
    first_time, second_time = second_time, first_time
    first_time = make_aware(first_time)
    if not first_time and not second_time:
        return None
    delta = first_time - second_time
    relative_delta = relativedelta(first_time, second_time)
    m_str = ""
    if relative_delta.years:
        m_str += f'{relative_delta.years} سال' if relative_delta.years else ''
        m_str += ' و '
        m_str += f'{relative_delta.months} ماه' if relative_delta.months else ''
        m_str += ' و '
        m_str += f'{relative_delta.days} روز' if relative_delta.days else ''
    elif relative_delta.months:
        m_str += f'{relative_delta.months} ماه' if relative_delta.months else ''
        m_str += ' و '
        m_str += f'{relative_delta.days} روز' if relative_delta.days else ''
        m_str += ' و '
        m_str += f'{relative_delta.hours} ساعت' if relative_delta.hours else ''
    elif relative_delta.days:
        m_str += f'{relative_delta.days} روز' if relative_delta.days else ''
        m_str += ' و '
        m_str += f'{relative_delta.hours} ساعت' if relative_delta.hours else ''
        m_str += ' و '
        m_str += f'{relative_delta.minutes} دقیقه' if relative_delta.minutes else ''
    elif relative_delta.hours:
        m_str += f'{relative_delta.hours} ساعت' if relative_delta.hours else ''
        m_str += ' و '
        m_str += f'{relative_delta.minutes} دقیقه' if relative_delta.minutes else ''
    elif relative_delta.minutes:
        m_str += f'{relative_delta.minutes} دقیقه' if relative_delta.minutes else ''
        m_str += ' و '
        m_str += f'{relative_delta.seconds} ثانیه' if relative_delta.seconds else ''
    elif relative_delta.seconds:
        return f"تقریبا هم اکنون"

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
        if time:
            jtime = myjalali.Gregorian(time).persian_tuple()
            # jtime_list = list(jtime)
            output = '{}-{}-{}'.format(jtime[0], jtime[1], jtime[2])
            return output
        return '1000-01-01'
    except Exception as e:
        print('error ', __file__, e.__traceback__.tb_lineno, e)
        return '1000-01-01'


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


_senf = {
    "پزشکی": ("تجهیزات پزشکی", "پزشکی"),

    "کنترل رله و درب پارکینگ": ("کنترل رله و درب اتوماتیک", "کنترل رله و درب پارکینگ"),

    "مخابراتی": ("امنیتی", "مخابراتی"),

    "محافظ برق": ("محافظ برق", "تولید برد محافظ - تولید آژیر اعلام خطر", "محافظ", "تولید محافظ برق", "استابلایزر", ),

    "لوازم خانگی": ("لوازم خانگی", "هود-تستر", "لوازم و دستگاه های خانگی", "تولید نمایشگر وزن", "لوازم خانگی-جاروبرقی",
                    "برد الکترونیکی تهویه مطبوع و لوازم خانگی", "تولید بردهای الکترونیکی- لوازم خانگی","ترازو",
                    "تولید برد لوازم خانگی", "لوازم خانگی -پنکه", "تایمر اجاق گاز-لوازم خانگی", "تولید برد لوازم خانگی و نورپردازی",
                    "تولید لوازم خانگی", "تولید شومینه برقی", "لوازم خانگی ( پنکه)", "بردهای صنعتی، آسانسور، لوازم خانگی"),

    "طراح / مونتاژ / تعمیرکار": ("فروشنده", "طراح", "تجهیز قطار های بین شهری", "تولید بردهای الکترونیک", "شهرک صنعتی",
                                 "الکترونیک مخابرات", "الکترونیک-طراحی و ساخت", "طراح سیم کارتل","طراح / مونتاژ / تعمیرکار",
                                 "کنترل دور موتور", "الکترونیک و مخابرات", "روباتیک", "برد الکترونیکی", "قطعات سنسور",
                                 "پروژه ای-الان تایمر", "طراحی برد", "تجهیزات الکترونیکی", "انرژی", "مونتاژ کار و همکار",
                                 "تولید مدار الکترونیکی", "تعمیرکار", "لوازم الکتریکی", "فروشگاه", "فروش قطعات",
                                 "تامین کننده قطعات", "سیستم های اطلاع رسانی", "شخصی", "الکترونیک", "طراح / مونتاژ / تعمیر کار",
                                 "رباتیک" ,"مونتاژکار","مونتاژ کار"),

    "سوخت شده": ("سوخت شده", ),

    "روشنایی": ("روشنایی", "فلاشر ال ای دی", "فلاشر", "تولید روشنایی", "روشنایی دیجیتال", "روشنایی  دیجیتال", "روشنایی تبلیغاتی"),

    "ردیاب": ("ردیاب", "ترکر", "دزدگیر و ردیاب", "دزدگیر ردیاب"),

    "دزدگیر": ("دزدگیر", "دزدگیر-ریموت", "چشمی(دزدگیر)", "ریموت", "سنسور راه پله", "سنسور", "دزدگیر و ردیاب",
               "تولید دزگیر", "تولید سیستم های امنیتی", "UPS", "ریموت و تگ", "دستگاه کنترل از راه دور سیم کارتی",
               "دوربین مداربسته", "دزدگیر و چشمی", "کنترل", "چشمی", "حفاظتی", "سیستم های حفاظتی", "دزدگیر ردیاب",),

    "خودرو": ("خودرو", "خودرویی", "چراغ سقفی", "خودرو+محافظ", "هوشمند سازی خودرو", "خودرویی(چراغ خودرو)", "کلید سوخت",
              "خودرو-روشنایی", "لامپ های خودرویی", "بالابرخودرو",),

    "بازار": ("بازار", "بازار -فروشنده"),

    "اعلام حریق": ("اعلام حریق", "دتکتور", "اعلام و اطفای حریق", "آلارم"),

    "اتوماسیون صنعتی": ("اتوماسیون صنعتی", "نظامی", "plc", "تولید دستگاه کنترل فاز", "اتوماسیون - امنیتی",
                        "سیستم های تست و شارژ باتری های توان بالا", "اتوماسیون", "سنسور اندازه گیری", "ابزار دقیق", "سیستم های مانیتورینگ و اتوماسیون صنعتی",),

    "آسانسور": ("آسانسور", "آسانسوری", "درایو آسانسور", "تولیدکننده شاسی داخل کابین و خارج کابین آسانسور",
                "آژیر آسانسور", "بردهای صنعتی، آسانسور، لوازم خانگی",),

    "IOT": ("IOT", "شهر هوشمند", "کنتور", "اینترنت اشیا", "کنتور آب", "تولیدکننده کنتور های هوشمند آب", "ویرا تراشه"
            "تولید ست کنترل پمپ های آب خانگی", "تله متری", "سیستم های تله متری", "ماژول گیرنده های رادیویی",),

    "GPS": ("GPS", "GPS-دستکاه اندازه گیری گازوئیل"),
    "منبع تغذیه": ("منبع تغذیه",),

    "BMS": ("bms", "BMS", "گرمایشی", "تولید کلیدهای لمسی", "تولید ترموستات", "ترموستات", "آینه هوشمند",
            "تولید تجهیزات کنترلر دما و رطوبت خانگی و صنعتی", "تولید آینه های هوشمند", "BMS(قلاده هوشمند)",
            "شرکت آینه های هوشمند mirror smart tech", "محصولات هوشمند سازی استان اصفهان", "قفل هوشمند", "تهویه مطبوع",
            "هوشمند سازی", "ساعت دیجیتال"),
}

senf_map = LookupDict(name='valid_senf')


def senf_init():
    for senf, titles in _senf.items():
        for title in titles:
            setattr(senf_map, title, senf)
            if not title.startswith(('\\', '/')):
                setattr(senf_map, title.upper(), senf)

    def doc(senf):
        names = ', '.join('``%s``' % n for n in _senf[senf])
        return '* %d: %s' % (senf, names)

    global __doc__
    __doc__ = (__doc__ + '\n' +
               '\n'.join(doc(senf) for senf in sorted(_senf))
               if __doc__ is not None else None)


def export_to_excel(objects, config_json):

    selected_fields = config_json.get('selected_fields', [])
    selected_labels = config_json.get('selected_labels', [])
    # header = config_json.get('header', [])
    # footer = config_json.get('footer', [])

    data = []

    # header = {
    #     'selected_fields': ['quotation__customer_party_id', 'quotation__created_date'],
    #     'selected_labels': ['مشتری', 'تاریخ ایجاد']
    # }
    #
    # row = dict()
    # for f, l in zip(header.get('selected_fields'), header.get('selected_labels')):
    #     if '__' in f:
    #         f_list = f.split('__')
    #         value = reduce_getattr(getattr, f_list, objects[0])
    #         if isinstance(value, datetime.datetime) and value.tzinfo is not None:
    #             value = to_jalali_date(value.replace(tzinfo=None))
    #         row[l] = value


    for obj in objects:
        row = {}
        for field, label in zip(selected_fields, selected_labels):
            value = getattr(obj, field, None) if not isinstance(obj, dict) else obj.get(field)
            if isinstance(value, datetime.datetime) and value.tzinfo is not None:
                value = to_jalali_date(value.replace(tzinfo=None))
            row[label] = value
        data.append(row)

    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    return output


def generate_powerbi_filter(filters):
    parts = []
    for f in filters:
        dim = f["dim"]
        field = f["field"]
        value = f["field_value"]

        # اگر مقدار رشته‌ای باشه، در کوتیشن قرار بگیره و انکد بشه
        encoded_value = value if isinstance(value, int) else urllib.parse.quote(f"'{value}'")
        parts.append(f"{dim}/{field} eq {encoded_value}")
    return "&filter=" + " and ".join(parts)


_initial_missing = object()
def reduce_getattr(function, sequence, initial=_initial_missing):

    it = iter(sequence)

    if initial is _initial_missing:
        try:
            value = next(it)
        except StopIteration:
            raise TypeError(
                "reduce() of empty iterable with no initial value") from None
    else:
        value = initial

    for element in it:
        value = function(value, element, None)
        if value is None:
            break

    return value
