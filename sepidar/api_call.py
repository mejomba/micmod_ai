from typing import Optional
import jdatetime
import requests
from django.conf import settings


class SepidarApiCall:
    protocol = settings.SEPIDAR_CUSTOM_API_PROTOCOL  # http
    host = settings.SEPIDAR_CUSTOM_API_HOST  # '192.168.1.80'
    port = settings.SEPIDAR_CUSTOM_API_PORT  # '3030'
    token = ''
    headers = {}
    endpoints = {
        'login': f'{protocol}://{host}:{port}/api_log/token/',
        'stock_quantity': f'{protocol}://{host}:{port}/sepidar_api/itemstocksummary/',
        'all_items': f'{protocol}://{host}:{port}/sepidar_api/item/?structure_name=top_x_item',
        'receipt_item': f'{protocol}://{host}:{port}/sepidar_api/inventoryreceiptitem/',
        'receipt': f'{protocol}://{host}:{port}/sepidar_api/inventoryreceipt/',
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
        cls.token = cls.get_token()

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
    def login(cls, username='ali', password='123456'):
        url = cls.endpoints.get('login')
        data = {'username': username, 'password': password}
        res = requests.post(url, data=data)
        if res.ok:
            res = res.json()
            return res
        else:
            return {}

    @classmethod
    def get_stock_quantity(cls, itemref, year: Optional[str] = None, *args, **kwargs):
        cls.setup()
        if year is None:
            year = jdatetime.date.today().year
        endpoint = cls.endpoints.get('stock_quantity')
        endpoint += f'?itemref={itemref[0]}&fiscalyearref__title={str(year)}'
        res = requests.get(endpoint, headers=cls.headers)
        out = dict()
        if res.ok:
            response = res.json()
            r = {item.get('stockref_str'): item.get('quantity') for item in response.get('results') if float(item.get('quantity')) > 0}
            out['res'] = r

        return out

    @classmethod
    def get_all_items(cls, page=0):
        cls.setup()
        endpoint = cls.endpoints.get('all_items')
        if page:
            endpoint = endpoint + f'?page={page}'
        res = requests.get(endpoint, headers=cls.headers)
        out = dict()
        if res.ok:
            response = res.json()
            return response
        return None

    @classmethod
    def create_dl(cls):
        pass

    @classmethod
    def get_receipt_item(cls, item_ref):
        cls.setup()
        endpoint = cls.endpoints.get('receipt_item')
        endpoint += f'?itemref={item_ref}'
        res = requests.get(endpoint, headers=cls.headers)
        out = dict()
        if res.ok:
            response = res.json()
            result = response.get('results')
            if result:
                out = result[0]
        return out

    @classmethod
    def get_receipt(cls, pk):
        cls.setup()
        endpoint = cls.endpoints.get('receipt')
        endpoint += f'?inventoryreceiptid={pk}'
        res = requests.get(endpoint, headers=cls.headers)
        out = dict()
        if res.ok:
            response = res.json()
            result = response.get('results')
            if result:
                out = result[0]
        return out
