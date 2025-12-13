from pprint import pprint
import json
not_allow_key = ['meta_datas', 'blank_objects', 'blank_objects', 'fk_strs', '__str__', '__len__', 'navigation_instances', 'navigation_instances_by_user', 'past_post_res']

x = '''{
    "debitcreditnoteid": 18945,
    "debitcreditnote_items": [
        {
            "debitcreditnoteitemid": 27829,
            "meta_datas": {
                "some_dict": {"key": "value"},
                "post_url": "/api2/sepidar_api-debitcreditnoteitem/27829/",
                "related_urls": null,
                "pk_field": "debitcreditnoteitemid"
            },
            "blank_objects": {},
            "fk_strs": {
                "debitcreditnoteref": "(number: 990)"
            },
            "__str__": ""
        },
        {
            "debitcreditnoteitemid": 27830,
            "rowid": 2,
            "meta_datas": {
                "version": {
                    "type": "int",
                    "verbose_name": "version",
                    "required": false,
                    "validators": [],
                    "field_type": "IntegerField",
                    "hidden": false,
                    "readonly": false
                }
            },
            "blank_objects": {},
            "fk_strs": {
                "debitcreditnoteref": "(number: 990)"
            },
            "__str__": ""
        }
    ],
    "number": 990,
    "date": "2025-12-01T16:30:43.512492+03:30",
    "meta_datas": {
        "creationdate": {
            "type": "date_time",
            "verbose_name": "creationdate",
            "required": false,
            "validators": [],
            "field_type": "DateTimeField",
            "hidden": false,
            "readonly": false
        },
        
        "post_url": "/api2/sepidar_api-debitcreditnote/18945/",
        "related_urls": null
    },
    "blank_objects": {
        "debitcreditnote_items": {
            "debitcreditnoteitemid": null,
            "rowid": null,
            "blank_objects": {},
            "fk_strs": {
                "debitcreditnoteref": null
            },
            "__str__": ""
        }
    },
    "fk_strs": {
        "currencyref": "يوان",
        "voucherref": null
    },
    "__str__": "(number: 990)"
}'''

x = json.loads(x)
d = dict()

def jafar(xi):
    if isinstance(xi, dict):
        for k, v in xi.items():
            if k not in not_allow_key and not isinstance(v, (list, dict)):
                d[k] = v
            else:
                if isinstance(v, (dict, list)):
                    jafar(v)
    elif isinstance(xi, list):
        for item in xi:
            jafar(item)


def clean_dict(data, not_allow_keys, out=None):
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():

            # رد کردن کلیدهای ممنوع
            if k in not_allow_keys:
                continue

            # اگر مقدار primitive باشد → نگه داریم
            if not isinstance(v, (dict, list)):
                result[k] = v

            # اگر dict باشد → بازگشتی پاکسازی کنیم
            elif isinstance(v, dict):
                cleaned = clean_dict(v, not_allow_keys)
                if cleaned:  # فقط اگر چیزی باقی ماند
                    result[k] = cleaned

            # اگر list باشد → بازگشتی روی هر آیتم
            elif isinstance(v, list):
                cleaned_list = []
                for item in v:
                    if isinstance(item, (dict, list)):
                        cleaned_item = clean_dict(item, not_allow_keys)
                        if cleaned_item:
                            cleaned_list.append(cleaned_item)
                if cleaned_list:
                    result[k] = cleaned_list

        return result

    return data


o = clean_dict(x, not_allow_key)

pprint(o)