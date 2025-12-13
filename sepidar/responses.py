class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class SepidarResponseManager(metaclass=SingletonMeta):
    def __init__(self):
        self.not_allow_keys = ['meta_datas', 'blank_objects', 'fk_strs', '__str__', '__len__', 'navigation_instances',
                               'navigation_instances_by_user', 'past_post_res']

    def clean_dict(self, data, not_allow_keys=None):
        if not_allow_keys:
            self.not_allow_keys = not_allow_keys

        if isinstance(data, dict):
            result = {}
            for k, v in data.items():

                # رد کردن کلیدهای ممنوع
                if k in self.not_allow_keys:
                    continue

                # اگر مقدار primitive باشد → نگه داریم
                if not isinstance(v, (dict, list)):
                    result[k] = v

                # اگر dict باشد → بازگشتی پاکسازی کنیم
                elif isinstance(v, dict):
                    cleaned = self.clean_dict(v, not_allow_keys)
                    if cleaned:  # فقط اگر چیزی باقی ماند
                        result[k] = cleaned

                # اگر list باشد → بازگشتی روی هر آیتم
                elif isinstance(v, list):
                    cleaned_list = []
                    for item in v:
                        if isinstance(item, (dict, list)):
                            cleaned_item = self.clean_dict(item, not_allow_keys)
                            if cleaned_item:
                                cleaned_list.append(cleaned_item)
                    if cleaned_list:
                        result[k] = cleaned_list

            return result

        return data

    def response_validation(self, res):
        if res.ok:
            return res

        return {"status_code": res.status_code,
                "message": "error",
                "technical_message": res.text,
                "reason": res.reason,
                "url": res.url}

    @staticmethod
    def supplier_default_response(res):
        res = [{'partyid': x.get('partyid'), 'name': x.get('name').replace('ي', 'ی').replace('ك', 'ک'), 'dlref': x.get('dlref'),
                'maximumcredit': x.get('maximumcredit'), 'type': x.get('type')}
               for x in res.json().get('results')]
        return res

    @staticmethod
    def create_supplier_response(res):
        x = res.json()
        res = [{'partyid': x.get('partyid'), 'name': x.get('name').replace('ي', 'ی').replace('ك', 'ک'),
                'dlref': x.get('dlref'),
                'maximumcredit': x.get('maximumcredit'), 'type': x.get('type')}
               ]
        return res