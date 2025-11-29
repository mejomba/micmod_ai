class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class SepidarResponseManager(metaclass=SingletonMeta):
    def __init__(self):
        pass

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