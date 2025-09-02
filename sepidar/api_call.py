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
        "v1": {
            'login': f'{protocol}://{host}:{port}/api_log/token/',
            'stock_quantity': f'{protocol}://{host}:{port}/sepidar_api/itemstocksummary/',
            'all_items': f'{protocol}://{host}:{port}/sepidar_api/item/?structure_name=top_x_item',
            'receipt_item': f'{protocol}://{host}:{port}/sepidar_api/inventoryreceiptitem/',
            'receipt': f'{protocol}://{host}:{port}/sepidar_api/inventoryreceipt/',
            'invoice': f'{protocol}://{host}:{port}/api2/sepidar_api-invoice/',
        },
        "v2": {
            'login': f'{protocol}://{host}:{port}/api_log/token/',
            'stock_quantity': f'{protocol}://{host}:{port}/api2/itemstocksummary/',
            'all_items': f'{protocol}://{host}:{port}/sepidar_api/item/?structure_name=top_x_item',
            'receipt_item': f'{protocol}://{host}:{port}/api2/inventoryreceiptitem/',
            'receipt': f'{protocol}://{host}:{port}/api2/inventoryreceipt/',
            'invoice': f'{protocol}://{host}:{port}/api2/sepidar_api-invoice/',
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
        url = cls.endpoints.get(settings.SEPIDAR_CUSTOM_API_VERSION).get('login')
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
        endpoint = cls.endpoints.get(settings.SEPIDAR_CUSTOM_API_VERSION).get('stock_quantity')
        endpoint += f'?itemref={itemref[0]}&fiscalyearref__title={str(year)}'
        res = requests.get(endpoint, headers=cls.headers)
        out = dict()
        if res.ok:
            response = res.json()
            if settings.SEPIDAR_CUSTOM_API_VERSION == 'v1':
                r = {item.get('stockref_str'): item.get('quantity') for item in response.get('results') if float(item.get('quantity')) > 0}
            else:
                r = {(item.get('fk_strs').get('stockref'), item.get('stockref')): item.get('quantity') for item in response.get('results') if
                     float(item.get('quantity')) > 0}
            out['res'] = r

        return out

    @classmethod
    def get_all_items(cls, page=0):
        cls.setup()
        endpoint = cls.endpoints.get(settings.SEPIDAR_CUSTOM_API_VERSION).get('all_items')
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
        endpoint = cls.endpoints.get(settings.SEPIDAR_CUSTOM_API_VERSION).get('receipt_item')
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
        endpoint = cls.endpoints.get(settings.SEPIDAR_CUSTOM_API_VERSION).get('receipt')
        endpoint += f'?inventoryreceiptid={pk}'
        res = requests.get(endpoint, headers=cls.headers)
        out = dict()
        if res.ok:
            response = res.json()
            result = response.get('results')
            if result:
                out = result[0]
        return out

    @classmethod
    def factor_to_sepidar(cls, obj):
        cls.setup()
        endpoint = cls.endpoints.get(settings.SEPIDAR_CUSTOM_API_VERSION).get('invoice')
        x = {
            "invoiceid": 71115,
            "invoice_items": [
                {
                    "invoiceitemid": 283253,
                    "rowid": 1,
                    "tracingref": null,
                    "quantity": 1000.0,
                    "secondaryquantity": null,
                    "fee": 126000.0,
                    "price": 126000000.0,
                    "priceinbasecurrency": 126000000.0,
                    "discount": 0.0,
                    "discountinbasecurrency": 0.0,
                    "priceinfodiscountrate": 0.0,
                    "customerdiscountrate": 0.0,
                    "addition": 0.0,
                    "additioninbasecurrency": 0.0,
                    "tax": 0.0,
                    "taxinbasecurrency": 0.0,
                    "duty": 0.0,
                    "dutyinbasecurrency": 0.0,
                    "netpriceinbasecurrency": 126000000.0,
                    "rate": 1.0,
                    "description": null,
                    "description_en": null,
                    "priceinfopricediscount": 0.0,
                    "priceinfopercentdiscount": 0.0,
                    "customerdiscount": 0.0,
                    "productpackquantity": null,
                    "aggregateamountdiscountrate": 0.0,
                    "aggregateamountpricediscount": 0.0,
                    "aggregateamountpercentdiscount": 0.0,
                    "orderitemref": null,
                    "additionfactor_vateffective": 0.0,
                    "additionfactorinbasecurrency_vateffective": 0.0,
                    "additionfactor_vatineffective": 0.0,
                    "additionfactorinbasecurrency_vatineffective": 0.0,
                    "invoiceref": 71115,
                    "itemref": 7588,
                    "stockref": 24,
                    "quotationitemref": null,
                    "discountinvoiceitemref": null,
                    "productpackref": null,
                    "discountitemgroupref": null,
                }
            ],
            "customerrealname": "MICMOD SHOP",
            "customerrealname_en": "MICMOD SHOP",
            "partyaddressref": null,
            "number": 2223,
            "date": "2025-08-27T03:30:00+03:30",
            "currencyref": 1,
            "slref": 420,
            "deliverylocationref": 1,
            "state": 1,
            "price": 178500000.0,
            "priceinbasecurrency": 178500000.0,
            "discount": 0.0,
            "discountinbasecurrency": 0.0,
            "addition": 0.0,
            "additioninbasecurrency": 0.0,
            "tax": 0.0,
            "taxinbasecurrency": 0.0,
            "duty": 0.0,
            "dutyinbasecurrency": 0.0,
            "netpriceinbasecurrency": 178500000.0,
            "rate": 1.0,
            "version": 2,
            "creator": 30,
            "creationdate": "2025-08-27T14:31:11+03:30",
            "lastmodifier": 30,
            "lastmodificationdate": "2025-08-27T14:31:14+03:30",
            "fiscalyearref": 46,
            "voucherref": 243376,
            "baseoninventorydelivery": false,
            "orderref": null,
            "shouldcontrolcustomercredit": true,
            "guid": null,
            "additionfactor_vateffective": 0.0,
            "additionfactorinbasecurrency_vateffective": 0.0,
            "additionfactor_vatineffective": 0.0,
            "additionfactorinbasecurrency_vatineffective": 0.0,
            "agreementref": null,
            "quotationref": null,
            "customerpartyref": 3391,
            "saletyperef": 34,
        }
