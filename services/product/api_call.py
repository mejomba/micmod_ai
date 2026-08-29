from typing import Optional
import jdatetime
import requests
from django.conf import settings


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class SepidarDataFactory(metaclass=SingletonMeta):
    def __init__(self):
        pass

    @classmethod
    def some_obj_data(cls, obj, request=None):
        """ implement data function for obj's """
        pass


class ProductResponseManager(metaclass=SingletonMeta):
    def __init__(self):
        pass

    @staticmethod
    def products(res):
        return res.json().get('products')[0]

    @staticmethod
    def products_map(res, data=None):
        out = dict()
        for p in res.json().get('products'):
            out[p['sepidar_sku'][0]] = p['id']

        return out


    @staticmethod
    def product_image_and_datasheet(res):
        """ implement change on api response """
        images = []
        datasheets = []
        out = dict()
        if res.ok:
            products = res.json().get('products')
            for p in products:
                images = [i.get('url') for i in p.get('images')]
                datasheets = [d.get('url') for d in p.get('data_sheet')]

            out['images'] = images
            out['datasheets'] = datasheets
        return out


class ProductApiCall:
    data = SepidarDataFactory()
    response_manager = ProductResponseManager()
    protocol = settings.PRODUCT_API_PROTOCOL  # http
    host = settings.PRODUCT_API_HOST  # '192.168.1.73'
    port = settings.PRODUCT_API_PORT  # '1010'
    token = ''
    headers = {}
    endpoints = {
        "v1": {
            'login': f'{protocol}://{host}:{port}/api2/token/',
            'products': f'{protocol}://{host}:{port}/products/',
        },
    }

    @classmethod
    def setup(cls):
        cls.set_token()
        cls.set_header()

    @classmethod
    def get_token(cls):
        res = cls.login()
        return res.get('access')

    @classmethod
    def set_token(cls):
        from django.core.cache import cache
        cls.token = cache.get('product_jwt_access_token')
        if cls.token:
            return
        else:
            cls.token = cls.get_token()
            cache.set('product_jwt_access_token', cls.token, timeout=9000)

    @classmethod
    def get_header(cls):
        headers = {
            "Authorization": f"Bearer {cls.token}"
        }
        return headers

    @classmethod
    def set_header(cls):
        cls.headers = cls.get_header()

    @classmethod
    def login(cls, username='mr.aminzadeh', password='@Mm123456'):
        url = cls.endpoints.get(settings.PRODUCT_API_VERSION).get('login')
        data = {'username': username, 'password': password}
        res = requests.post(url, data=data)
        if res.ok:
            res = res.json()
            return res
        else:
            return {}

    @classmethod
    def get_product_by_skus(cls, skus, response_function, *args, **kwargs):
        """
        if skus=number return single item response
        if skus=number,number return 2*item response
        """
        cls.setup()
        endpoint = cls.endpoints.get(settings.PRODUCT_API_VERSION).get('products')
        endpoint += f'?sepidar_skus={skus}'
        res = requests.get(endpoint, headers=cls.headers)
        res = getattr(cls.response_manager, (response_function or 'products'))(res)
        return res

        if res.ok:
            response = res.json()
            out = response.get('images')

        return out
