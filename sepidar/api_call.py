import json
from typing import Optional, TypedDict, List
import jdatetime
import requests
from django.conf import settings
from django.utils import timezone
from .data import SepidarDataFactory
from .models import Dl
from .responses import SepidarResponseManager


class SupplierType(TypedDict):
    partyid: int
    name: str
    dlref: str | None
    maximumcredit: int | None


class SepidarApiCall:
    data = SepidarDataFactory()
    response_manager = SepidarResponseManager()
    protocol = settings.SEPIDAR_CUSTOM_API_PROTOCOL  # http
    host = settings.SEPIDAR_CUSTOM_API_HOST  # '192.168.1.80'
    port = settings.SEPIDAR_CUSTOM_API_PORT  # '3030'
    token = ''
    headers = {}
    const: dict = settings.SEPIDAR_CONST_DATA
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
            'stock_quantity_list': f'{protocol}://{host}:{port}/api2/functions/stock_quantity_list/', # دریافت موجودی تمام کالاها
            'all_items': f'{protocol}://{host}:{port}/sepidar_api/item/?structure_name=top_x_item',
            'receipt_item': f'{protocol}://{host}:{port}/api2/inventoryreceiptitem/',
            'receipt': f'{protocol}://{host}:{port}/api2/inventoryreceipt/',
            # 'invoice': f'{protocol}://{host}:{port}/api2/sepidar_api-invoice/',  # فاکتور فروش
            'invoice': f'{protocol}://{host}:{port}/api2/functions/invoice/',  # فاکتور فروش
            'voucher': f'{protocol}://{host}:{port}/api2/sepidar_api-voucher/',  # سند مالی
            'extra_data': f'{protocol}://{host}:{port}/api2/sepidar_api-extradata/',
            'inventory_delivery': f'{protocol}://{host}:{port}/api2/sepidar_api-inventorydelivery/',  # خروج از انبار
            'inventory_purchase_invoice': f'{protocol}://{host}:{port}/api2/sepidar_api-inventorypurchaseinvoice/',  # فاکتور خرید
            'gio': f'{protocol}://{host}:{port}/api2/functions/gio/',  # عملیات سپیدار در ازای gio
            'bazar_buy_factor': f'{protocol}://{host}:{port}/api2/functions/bazar_buy_factor/',  # فاکتور خرید بازار
            'party': f'{protocol}://{host}:{port}/api2/sepidar_api-party/',
            'bazar_supplier': f'{protocol}://{host}:{port}/api2/sepidar_api-party?isvendor=1',
            'packing': f'{protocol}://{host}:{port}/api2/functions/packing/',  #  خروج از انبار (انتقال بین انبار)
            'wh_receipt_from_bazar': f'{protocol}://{host}:{port}/api2/functions/wh_receipt_from_bazar/',  #  رسید انبار از فاکتور خرید بازار
            'debit_credit': f'{protocol}://{host}:{port}/api2/functions/debit_credit/',    # اعلامیه بدهکار بستانکار
            # 'wh_to_wh': f'{protocol}://{host}:{port}/api2/sepidar_api-inventorydelivery/',  #  خروج از انبار (انتقال بین انبار)
            'debit_credit_note': f'{protocol}://{host}:{port}/api2/sepidar_api-debitcreditnote/',  # اعلامیه بدهکار بستانکار
            'inventory_receipt': f'{protocol}://{host}:{port}/api2/sepidar_api-inventoryreceipt/',  # رسید انبار
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
        cls.token = cache.get_or_set('sepidar_jwt_access_token', cls.get_token(), timeout=9000)

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
    def get_stock_quantity_list(cls, itemref_list=None, year=None):
        cls.setup()
        endpoint = cls.endpoints.get(settings.SEPIDAR_CUSTOM_API_VERSION).get('stock_quantity_list')
        res = requests.get(endpoint, headers=cls.headers)
        if res.ok:
            return res.json()['data']
        else:
            return res.json()['errors']

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
                r = {item.get('stockref_str'): item.get('quantity') for item in response.get('results') if
                     float(item.get('quantity')) > 0}
            else:
                r = {(item.get('fk_strs').get('stockref'), item.get('stockref')): item.get('quantity') for item in
                     response.get('results') if
                     float(item.get('quantity')) > 0}
            out['res'] = r

        return out

    @classmethod
    def get_stock_item_pair_quantity(cls, itemref, stock, year: Optional[str] = None, *args, **kwargs):
        cls.setup()
        if year is None:
            year = jdatetime.date.today().year
        endpoint = cls.endpoints.get(settings.SEPIDAR_CUSTOM_API_VERSION).get('stock_quantity')
        endpoint += f'?itemref={itemref[0]}&fiscalyearref__title={str(year)}&stockref__stockid={stock}'
        res = requests.get(endpoint, headers=cls.headers)
        out = dict()
        if res.ok:
            response = res.json()
            return response

        return None

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
    def dl_to_sepidar(cls, request, customer):
        cls.setup()
        endpoint = cls.endpoints.get(settings.SEPIDAR_CUSTOM_API_VERSION).get('party')
        """
        type: [("1", "تلفن دفتر"), ("2", "تلفن همراه"), ("3", "منزل"), ("4", "سایر"), ("5", "دورنگار دفتر"),
         ("6", "دورنگار منزل "), ("7", "دورنگار سایر"),]

        """,
        phones = [
            {
                "ismain": 1,
                "type": 2, # تلفن همراه
                "phone": customer.phone,
                # "partyref": 10
            } if customer.phone else {},
        ]
        related_persons = []
        for customer_related in customer.customerexpert_set.all():
            related_persons.append(
                {
                    "ismain": customer_related.is_main,
                    "name": customer_related.name,
                    "post": customer_related.position,
                    "name_en": customer_related.name,
                    "post_en": customer_related.position,
                    "phone": customer_related.phone,
                    "email": None,
                    # "partyref": 10
                }
            )

        addresses = [
                {
                    "ismain": 1,
                    "type": 6,  # آدرس رسمی
                    "address": customer.address,
                    "zipcode": None,
                    "address_en":  customer.address,
                    "latitude": customer.lat,
                    "longitude": customer.long,
                    "title": None,
                    "guid": None,
                    # "partyref": 10,
                    "locationref": None
                }
            ]
        extradata = [
                {
                    "entitytypename": "SG.General.PartyManagement.Common.DsParty",
                    "entityref": 10,
                    "stringcolumn1": None,
                    "stringcolumn2": None,
                    "stringcolumn3": None,
                    "stringcolumn4": None,
                    "stringcolumn5": None,
                    "stringcolumn6": None,
                    "stringcolumn7": None,
                    "stringcolumn8": None,
                    "stringcolumn9": None,
                    "stringcolumn10": None,
                    "stringcolumn11": None,
                    "stringcolumn12": None,
                    "stringcolumn13": None,
                    "stringcolumn14": None,
                    "stringcolumn15": None,
                    "note": "some note for test",
                    "datecolumn1": None,
                    "datecolumn2": None,
                    "datecolumn3": None,
                    "datecolumn4": None,
                    "datecolumn5": None,
                    "integercolumn1": None,
                    "integercolumn2": None,
                    "integercolumn3": None,
                    "integercolumn4": None,
                    "integercolumn5": None,
                    "decimalcolumn1": None,
                    "decimalcolumn2": None,
                    "decimalcolumn3": None,
                    "decimalcolumn4": None,
                    "decimalcolumn5": None,
                    "decimalcolumn6": None,
                    "decimalcolumn7": None,
                    "decimalcolumn8": None,
                    "decimalcolumn9": None,
                    "decimalcolumn10": None,
                    "urlcolumn1": None,
                    "urlcolumn2": None,
                    "urlcolumn3": None,
                    "urlcolumn4": None,
                    "urlcolumn5": None
                }
            ]

        data = {
            "type": customer.type,
            "subtype": 7,  # سایر
            "name": customer.name,
            "lastname": customer.last_name,
            # "name_en": "",
            "lastname_en": "",
            "economiccode": None,  # Todo نیاز به افزودن
            "identificationcode": customer.national_code,
            "registrationcode": None,  # Todo نیاز به افزودن
            "website": customer.website,
            "email": customer.email,
            "isinblacklist": customer.black_list,
            "isvendor": False,
            "isbroker": False,
            "commissionrate": 0.0,
            "brokeropeningbalance": None,
            "brokeropeningbalancetype": 2,
            "isemployee": False,
            "iscustomer": True,
            "discountrate": 0.0,
            # "maximumcredit": customer.extra_credit,
            "customercategoryfortax": 2,  # عادی
            # "birthdate": None,
            # "marriagedate": None,
            "creator": request.user.sepidar_code,
            "creationdate": customer.created_date.isoformat(),
            "lastmodifier": customer.editor_user.pk,
            "lastmodificationdate": customer.last_update_date.isoformat(),
            "hascredit": False,
            "creditcheckingtype": 3,
            # "customerremaining": None,
            # "brokergroupingref": None,
            # "guid": None,
            # "dlref": 12,
            # "vendorgroupingref": null,
            # "salespersonpartyref": null,
            # "customergroupingref": 526,
            "addresses": addresses,
            "phone": phones,
            "related_persons": related_persons,
            "extra_data": extradata,
        }
        res = requests.post(endpoint, json=data, headers=cls.headers)
        if res.ok:
            return res

    @classmethod
    def get_party(cls, party_id):
        cls.setup()
        endpoint = cls.endpoints.get(settings.SEPIDAR_CUSTOM_API_VERSION).get('party')
        endpoint += f'?partyid={party_id}'
        res = requests.get(endpoint, headers=cls.headers)
        out = dict()
        if res.ok:
            response = res.json()
            result = response.get('results')
            if result:
                out = result[0]
        return out

    @classmethod
    def get_receipt_item(cls, item_ref):
        cls.setup()
        endpoint = cls.endpoints.get(settings.SEPIDAR_CUSTOM_API_VERSION).get('receipt_item')
        endpoint += f'?itemref={item_ref}&inventoryreceiptref__type=1'
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
    def factor_to_sepidar(cls, obj, request=None, update=False):
        cls.setup()
        endpoint = cls.endpoints.get(settings.SEPIDAR_CUSTOM_API_VERSION).get('invoice')
        if update:
            data = {}
        else:
            invoice_data = cls.data.get_invoice_data(obj, request, invoice_item_data=None)

            d = {'data': invoice_data}
            res = requests.post(endpoint, json=d, headers=cls.headers)
            if res.ok:
                data = res.json()
                out = {
                    "number": data.get("number"),
                    "invoiceid": data.get("invoiceid"),
                    "sepidar_inventory_delivery_number": data.get('sepidar_inventory_delivery_number'),
                    "sepidar_inventory_delivery_id": data.get('sepidar_inventory_delivery_id'),
                    "sepidar_voucher_number": data.get('sepidar_voucher_number'),
                    "sepidar_voucher_id": data.get('sepidar_voucher_id'),
                    'invoice_items': [{"invoiceitemid": x.get("invoiceitemid"),
                                       "quantity": x.get('quantity'),
                                       "itemref": x.get('itemref'),
                                       }
                                      for x in res.json().get('invoice_items')
                                      ],
                }
                return out
            else:
                return res.json()

    @classmethod
    def buy_factor_to_sepidar(cls, obj, request=None, update=False):
        cls.setup()
        endpoint = cls.endpoints.get(settings.SEPIDAR_CUSTOM_API_VERSION).get('inventory_purchase_invoice')
        if update:
            data = {}
        else:
            inventory_purchase_invoice_data = cls.data.get_inventory_purchase_invoice_data(obj, request=request)

            res = requests.post(endpoint, json=inventory_purchase_invoice_data, headers=cls.headers)
            if res.ok:
                data = res.json()
                out = {
                    "valid": True,
                    "number": data.get("number"),
                    "buy_factor_id": data.get("inventorypurchaseinvoiceid"),
                    'buy_factor_items': [
                        {(x.get('itemref'), x.get('quantity')):
                             {"inventory_purchase_invoice_item_id": x.get("inventorypurchaseinvoiceitemid"),
                              "itemref": x.get('itemref'),
                              "quantity": x.get('quantity'),
                              }
                         }
                        for x in data.get('inventorypurchaseinvoice_item')
                    ],
                }
                return out
            elif res.status_code == 500:
                return {
                    "errors": "خطا در سرور سپیدار",
                }
            elif res.status_code == 400:
                return res.json().get('nested_data')
            else:
                return {
                    "errors": "خطا",
                }

    @classmethod
    def bazar_buy_factor_to_sepidar(cls, obj, request=None, update=False):
        cls.setup()
        endpoint = cls.endpoints.get(settings.SEPIDAR_CUSTOM_API_VERSION).get('bazar_buy_factor')
        if update:
            data = {}
        else:
            inventory_purchase_invoice_data = cls.data.get_inventory_purchase_invoice_data(obj, request=request)

            res = requests.post(endpoint, json=inventory_purchase_invoice_data, headers=cls.headers)
            return res

    @classmethod
    def trade_buy_factor_to_sepidar(cls, obj, request=None, update=False, buy_factor_data=None):
        """ send GIO to sepidar
            1: `buy factor`
            2: `inventory_receipt_before_central_wh`
            3: `voucher`
        """
        cls.setup()
        endpoint = cls.endpoints.get(settings.SEPIDAR_CUSTOM_API_VERSION).get('inventory_purchase_invoice')
        # endpoint = cls.endpoints.get(settings.SEPIDAR_CUSTOM_API_VERSION).get('gio')

        if update:
            data = {}
        else:
            buy_factor_list = list()
            out = dict()
            for supplier_currency, gio_items in obj.items():
                """ generate inventory_purchase_invoice data """
                inventory_purchase_invoice_data = cls.data.get_trade_inventory_purchase_invoice_data(supplier_currency, gio_items, request=request)
                res = requests.post(endpoint, json=inventory_purchase_invoice_data, headers=cls.headers)
                buy_factor_list.append(inventory_purchase_invoice_data)

            """ generate wh_to_wh_data """
            # wh_to_wh_data = cls.data.get_receipt_before_central_wh_data(buy_factor_data, request)

            """ make request for create
             1: `buy factor`
             2: `inventory_receipt_before_central_wh`
             3: `voucher` 
            """
            # d = {'buy_factor_list': buy_factor_list, "wh_to_wh_data": wh_to_wh_data}
            d = {'buy_factor_list': buy_factor_list}
            res = requests.post(endpoint, json=d, headers=cls.headers)
            if res.ok:
                out = cls.response_manager.clean_dict(res.json())
                return out

            elif res.status_code == 500:
                return {
                    "errors": "خطا در سرور سپیدار",
                }
            elif res.status_code == 400:
                return {'errors': res.json()}
            else:
                return {
                    "errors": "خطای کنترل نشده",
                }

    @classmethod
    def payment_to_sepidar(cls, objs: List["OrderPaymentItem"], request, response_function=None):

        try:
            transfer_rate = ...
            final_response = [False, dict()]
            not_allow_key = ['meta_datas', 'blank_objects', 'fk_strs', '__str__', '__len__', 'navigation_instances',
                             'navigation_instances_by_user', 'past_post_res']
            cls.setup()
            endpoint = cls.endpoints.get(settings.SEPIDAR_CUSTOM_API_VERSION).get('debit_credit')
            payment = objs[0].payment
            transfer_rate = payment.exchange_rate
            destination_currency = objs[0].order.currency
            source_currency = payment.currency
            orders_total_amount_in_payment = sum([x.total_amount for x in objs])
            destination_vendors = [x.order.final_supplier for x in objs]
            destination_vendors_str = ','.join([x.title for x in destination_vendors])
            karmozd_rate = round(payment.total_amount / (orders_total_amount_in_payment + (payment.karmozd or 0)), 2)

            transfer_rate = Dl.account_currency_rate(payment.vendor_party.dlref, cls.const.get('fiscalyearref'),
                                                     cls.const.get('hesab_pardakhtani'), source_currency.sepidar_id)
            transfer_rate = round(transfer_rate, 0)
            if 'rmb' in destination_currency.title_en.lower() or "یوآن" in destination_currency.title.lower():
                currency_name = 'rmb'
            elif 'ero' in destination_currency.title_en.lower() or "یورو" in destination_currency.title.lower():
                currency_name = 'ero'
            elif 'usd' in destination_currency.title_en.lower() or "دلار" in destination_currency.title.lower():
                currency_name = 'usd'

            """ارسال دستور پرداخت به سپیدار که معادل با اعلامیه بدهکار بستانکار میباشد"""
            if source_currency != destination_currency:
                'دوتا سند'
                'سند انتقال پول'
                karmozd_amount = round(payment.karmozd * karmozd_rate, 2)
                data1 = {
                    'version': 1,
                    "fiscalyearref": cls.const.get('fiscalyearref'),

                    "date": timezone.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
                    "creationdate": timezone.now().isoformat(),
                    "lastmodificationdate": timezone.now().isoformat(),
                    "creator": request.user.sepidar_code,
                    "lastmodifier": request.user.sepidar_code,
                    "currencyref": payment.currency.sepidar_id,

                    "rate": transfer_rate,  # Todo اینون بریم توی سپیدار حساب کنیم
                    "sumamount": payment.total_amount + (payment.karmozd or 0),  # مبلغ کل ردیف ها
                    "sumamountinbasecurrency": round((payment.total_amount + (payment.karmozd or 0)) * transfer_rate, 4),
                    # مبلغ به ریال Todo اینم بریم توی سپیدار حساب کنیم

                    # "voucherref": 243070, Todo: بعد از ثبت سند مالی باید یکبار این سند آپدیت بشه و این مقدار رو بگیره

                    'debitcreditnote_items': [
                        {
                            'version': 1,
                            "rowid": 1,
                            "debitslref": settings.SEPIDAR_CONST_DATA.get('pardakhtani_vaset_arzi'),
                            "creditslref": settings.SEPIDAR_CONST_DATA.get('hesab_pardakhtani'),
                            "debitdlref": payment.vendor_party.dlref,
                            "creditdlref": payment.vendor_party.dlref,
                            "debittype": 1,
                            "credittype": 1,
                            "amount": payment.total_amount,
                            "rate": transfer_rate,  # Todo اینون بریم توی سپیدار حساب کنیم
                            "amountinbasecurrency": round(payment.total_amount * transfer_rate, 3),
                            # Todo اینون بریم توی سپیدار حساب کنیم
                            "description": f'''انتقال {payment.total_amount} {source_currency} (معادل {orders_total_amount_in_payment} {destination_currency}) از حساب {payment.vendor_party.title} به {destination_vendors_str}''',
                            "description_en": f'''انتقال {payment.total_amount} {source_currency} (معادل {orders_total_amount_in_payment} {destination_currency}) از حساب {payment.vendor_party.title} به {destination_vendors_str}''',
                        },
                    ]
                }

                if karmozd_amount:
                    data1['debitcreditnote_items'].append(
                        {
                            'version': 1,
                            "rowid": 2,
                            "debitslref": cls.const.get('karmozd_sarafi'),
                            "creditslref": cls.const.get('hesab_pardakhtani'),
                            "debitdlref": None,
                            "creditdlref": payment.vendor_party.dlref,
                            "debittype": 3,
                            "credittype": 1,
                            "amount": karmozd_amount,
                            "rate": transfer_rate,  # Todo اینون بریم توی سپیدار حساب کنیم
                            "amountinbasecurrency": round(karmozd_amount * transfer_rate, 3),
                            "description": f"مبلغ {payment.karmozd * karmozd_rate}  معادل {payment.karmozd} {payment.karmozd_currency}"
                                           f" بابت انتقال {payment.total_amount} {source_currency} (معادل {orders_total_amount_in_payment} {destination_currency}) "
                                           f"از حساب {payment.vendor_party.title} به {destination_vendors_str}",
                            "description_en": f"مبلغ {payment.karmozd * karmozd_rate}  معادل {payment.karmozd} {payment.karmozd_currency}"
                                              f" بابت انتقال {payment.total_amount} {source_currency} (معادل {orders_total_amount_in_payment} {destination_currency}) "
                                              f"از حساب {payment.vendor_party.title} به {destination_vendors_str}",
                        }
                    )

                rate_to_final_supplier = round((payment.total_amount * transfer_rate) / orders_total_amount_in_payment,
                                               6)  # ارزش ریالی سند اول تقسیم بر ارزش ارزی پرداختی به تامین کننده نهایی
                data2 = {
                    "version": 1,
                    "fiscalyearref": cls.const.get('fiscalyearref'),

                    "date": timezone.now().isoformat(),
                    "creationdate": timezone.now().isoformat(),
                    "lastmodificationdate": timezone.now().isoformat(),
                    "creator": request.user.sepidar_code,
                    "lastmodifier": request.user.sepidar_code,
                    "currencyref": destination_currency.sepidar_id,

                    "rate": rate_to_final_supplier,  # Todo اینون بریم توی سپیدار حساب کنیم
                    "sumamount": orders_total_amount_in_payment,  # مبلغ کل ردیف ها
                    "sumamountinbasecurrency": round(orders_total_amount_in_payment * rate_to_final_supplier, 3),
                    # مبلغ به ریال Todo اینم بریم توی سپیدار حساب کنیم

                    # "voucherref": 243070, Todo: بعد از ثبت سند مالی باید یکبار این سند آپدیت بشه و این مقدار رو بگیره

                    'debitcreditnote_items': [
                        {
                            "rowid": idx,
                            "debitslref": settings.SEPIDAR_CONST_DATA.get('hesab_pardakhtani'),
                            "creditslref": settings.SEPIDAR_CONST_DATA.get('pardakhtani_vaset_arzi'),
                            "debitdlref": payment_item.order.final_supplier.dlref or settings.SEPIDAR_CONST_DATA.get(
                                f'no_name_vendor_{currency_name}'),
                            "creditdlref": payment.vendor_party.dlref,
                            "debittype": 1,
                            "credittype": 1,
                            "amount": payment_item.total_amount,
                            "rate": rate_to_final_supplier,  # Todo اینون بریم توی سپیدار حساب کنیم
                            "amountinbasecurrency": round(payment_item.total_amount * rate_to_final_supplier, 3),
                            # Todo اینون بریم توی سپیدار حساب کنیم
                            "description": f'''انتقال {payment.total_amount} {source_currency} (معادل {orders_total_amount_in_payment} {destination_currency}) از حساب {payment.vendor_party.title} به {destination_vendors_str}''',
                            "description_en": f'''انتقال {payment.total_amount} {source_currency} (معادل {orders_total_amount_in_payment} {destination_currency}) از حساب {payment.vendor_party.title} به {destination_vendors_str}''',
                            "version": 1,
                            # "debitcreditnoteref": 18877,
                        } for idx, payment_item in enumerate(objs, start=1)
                    ]
                }

                d = {'data_list': [data1, data2]}

                res = requests.post(endpoint, json=d, headers=cls.headers)
                if res.ok:
                    o = cls.response_manager.clean_dict(res.json())
                    final_response = o
                    return [True, final_response]
                else:
                    return [False, {'errors': res.json()}]

            else:
                'یدونه سند'
                rate_to_final_supplier = round((payment.total_amount * transfer_rate) / orders_total_amount_in_payment,
                                               6)  # ارزش ریالی سند اول تقسیم بر ارزش ارزی پرداختی به تامین کننده نهایی

                data = {
                    "version": 1,
                    "fiscalyearref": cls.const.get('fiscalyearref'),

                    "date": timezone.now().isoformat(),
                    "creationdate": timezone.now().isoformat(),
                    "lastmodificationdate": timezone.now().isoformat(),
                    "creator": request.user.sepidar_code,
                    "lastmodifier": request.user.sepidar_code,
                    "currencyref": destination_currency.sepidar_id,

                    "rate": rate_to_final_supplier,  # Todo اینون بریم توی سپیدار حساب کنیم
                    "sumamount": orders_total_amount_in_payment,  # مبلغ کل ردیف ها
                    "sumamountinbasecurrency": round(orders_total_amount_in_payment * rate_to_final_supplier, 3),
                    # مبلغ به ریال Todo اینم بریم توی سپیدار حساب کنیم

                    # "voucherref": 243070, Todo: بعد از ثبت سند مالی باید یکبار این سند آپدیت بشه و این مقدار رو بگیره

                    'debitcreditnote_items': [
                        {
                            "rowid": idx,
                            "debitslref": settings.SEPIDAR_CONST_DATA.get('hesab_pardakhtani'),
                            "creditslref": settings.SEPIDAR_CONST_DATA.get('hesab_pardakhtani'),
                            "debitdlref": payment_item.order.final_supplier.dlref or settings.SEPIDAR_CONST_DATA.get(
                                f'no_name_vendor_{currency_name}'),
                            "creditdlref": payment.vendor_party.dlref,
                            "debittype": 1,
                            "credittype": 1,
                            "amount": payment_item.total_amount,
                            "rate": rate_to_final_supplier,  # Todo اینون بریم توی سپیدار حساب کنیم
                            "amountinbasecurrency": round(payment_item.total_amount * rate_to_final_supplier, 3),
                            # Todo اینون بریم توی سپیدار حساب کنیم
                            "description": f'''انتقال {payment.total_amount} {source_currency} (معادل {orders_total_amount_in_payment} {destination_currency}) از حساب {payment.vendor_party.title} به {destination_vendors_str}''',
                            "description_en": f'''انتقال {payment.total_amount} {source_currency} (معادل {orders_total_amount_in_payment} {destination_currency}) از حساب {payment.vendor_party.title} به {destination_vendors_str}''',
                            "version": 1,
                            # "debitcreditnoteref": 18877,
                        } for idx, payment_item in enumerate(objs, start=1)
                    ]
                }
                d = {'data_list': [data]}

                req1_res = requests.post(endpoint, json=d, headers=cls.headers)
                if req1_res.ok:
                    o = cls.response_manager.clean_dict(req1_res.json())
                    final_response[1]['res1'] = o
                    final_response[0] = True
                    return final_response

            return [False, {'errors': 'no valid response'}]
        except Exception as e:
            return [False, {'errors': str(e)}]

    @classmethod
    def get_bazar_supplier(cls, request):
        cls.setup()
        endpoint = cls.endpoints.get(settings.SEPIDAR_CUSTOM_API_VERSION).get('bazar_supplier')
        q = request.GET.get('q', '')
        x = q.replace('ی', 'ي').replace('ک', 'ك')
        endpoint += f"&name__icontains={x}"
        res = requests.get(endpoint, headers=cls.headers)
        if res.ok:
            res = {x.get('dlref'): x.get('name') + ' ' + x.get('lastname', '') for x in res.json().get('results')}
            return res

        return dict()

    @classmethod
    def get_all_supplier(cls, request, response_function=None) -> List[SupplierType]:
        cls.setup()
        results = []
        endpoint = cls.endpoints.get(settings.SEPIDAR_CUSTOM_API_VERSION).get('bazar_supplier') + "&page_size=-1&dlref__isactive=1"
        res = requests.get(endpoint, headers=cls.headers)
        if res.ok:
            res = getattr(cls.response_manager, (response_function or 'supplier_default_response'))(res)
            return res

        return list(dict())

    @classmethod
    def get_supplier_by_partyid(cls, partyid, request, response_function=None) -> List[SupplierType]:
        cls.setup()
        endpoint = cls.endpoints.get(settings.SEPIDAR_CUSTOM_API_VERSION).get('bazar_supplier')
        endpoint += f'&partyid={partyid}&dlref__isactive=1'
        res = requests.get(endpoint, headers=cls.headers)
        if res.ok:
            res = getattr(cls.response_manager, (response_function or 'supplier_default_response'))(res)
            return res

        return list(dict())

    @classmethod
    def supplier_to_sepidar(cls, supplier, request, response_function=None, update=False) -> List[SupplierType]:
        cls.setup()
        endpoint = cls.endpoints.get(settings.SEPIDAR_CUSTOM_API_VERSION).get('party')
        if update:
            endpoint += f'{supplier.partyid}/'
        """
        type: [("1", "تلفن دفتر"), ("2", "تلفن همراه"), ("3", "منزل"), ("4", "سایر"), ("5", "دورنگار دفتر"),
         ("6", "دورنگار منزل "), ("7", "دورنگار سایر"),]

        """,
        phones = [
            {
                "ismain": 1,
                "type": 2,  # تلفن همراه
                "phone": supplier.phone,
                # "partyref": 10
            } if False else {},
        ]
        related_persons = []
        # for customer_related in supplier.customerexpert_set.all():
        #     related_persons.append(
        #         {
        #             "ismain": customer_related.is_main,
        #             "name": customer_related.name,
        #             "post": customer_related.position,
        #             "name_en": customer_related.name,
        #             "post_en": customer_related.position,
        #             "phone": customer_related.phone,
        #             "email": None,
        #             # "partyref": 10
        #         }
        #     )

        addresses = [
            {
                "ismain": 1,
                "type": 6,  # آدرس رسمی
                "address": supplier.address,
                "zipcode": None,
                "address_en": supplier.address,
                "latitude": supplier.lat,
                "longitude": supplier.long,
                "title": None,
                "guid": None,
                # "partyref": 10,
                "locationref": None
            }
        ] if False else None

        extradata = [
            {
                "entitytypename": "SG.General.PartyManagement.Common.DsParty",
                "entityref": 10,
                "stringcolumn1": None,
                "stringcolumn2": None,
                "stringcolumn3": None,
                "stringcolumn4": None,
                "stringcolumn5": None,
                "stringcolumn6": None,
                "stringcolumn7": None,
                "stringcolumn8": None,
                "stringcolumn9": None,
                "stringcolumn10": None,
                "stringcolumn11": None,
                "stringcolumn12": None,
                "stringcolumn13": None,
                "stringcolumn14": None,
                "stringcolumn15": None,
                "note": "some note for test",
                "datecolumn1": None,
                "datecolumn2": None,
                "datecolumn3": None,
                "datecolumn4": None,
                "datecolumn5": None,
                "integercolumn1": None,
                "integercolumn2": None,
                "integercolumn3": None,
                "integercolumn4": None,
                "integercolumn5": None,
                "decimalcolumn1": None,
                "decimalcolumn2": None,
                "decimalcolumn3": None,
                "decimalcolumn4": None,
                "decimalcolumn5": None,
                "decimalcolumn6": None,
                "decimalcolumn7": None,
                "decimalcolumn8": None,
                "decimalcolumn9": None,
                "decimalcolumn10": None,
                "urlcolumn1": None,
                "urlcolumn2": None,
                "urlcolumn3": None,
                "urlcolumn4": None,
                "urlcolumn5": None
            }
        ] if False else None

        data = {
            "type": supplier.type,
            "subtype": 7,  # سایر
            "name": supplier.title,
            "lastname": "",
            # "name_en": "",
            "lastname_en": "",
            "economiccode": None,  # Todo نیاز به افزودن
            "identificationcode": "",
            "registrationcode": None,  # Todo نیاز به افزودن
            "website": "",
            "email": "",
            "isinblacklist": False,
            "isvendor": True,
            "isbroker": False,
            "commissionrate": 0.0,
            "brokeropeningbalance": None,
            "brokeropeningbalancetype": 2,
            "isemployee": False,
            "iscustomer": True,
            "discountrate": 0.0,
            # "maximumcredit": customer.extra_credit,
            "customercategoryfortax": 2,  # عادی
            # "birthdate": None,
            # "marriagedate": None,
            "creator": request.user.sepidar_code,
            "creationdate": supplier.created_date.isoformat(),
            "lastmodifier": supplier.editor_user.sepidar_code,
            "lastmodificationdate": supplier.last_update_date.isoformat(),
            "hascredit": False,
            "creditcheckingtype": 3,
            # "customerremaining": None,
            # "brokergroupingref": None,
            # "guid": None,
            # "dlref": 12,
            # "vendorgroupingref": null,
            # "salespersonpartyref": null,
            # "customergroupingref": 526,
            # "addresses": addresses,
            # "phone": phones,
            # "related_persons": related_persons,
            # "extra_data": extradata,
        }

        # data = {
        #
        # }
        res = requests.post(endpoint, json=data, headers=cls.headers)

        if res.ok:
            res = getattr(cls.response_manager, (response_function or 'create_supplier_response'))(res)
            return res
        else:
            raise Exception

        return list(dict())

    @classmethod
    def packing(cls, packing, request, response_function=None):
        cls.setup()
        endpoint = cls.endpoints.get(settings.SEPIDAR_CUSTOM_API_VERSION).get('packing')

        data = cls.data.get_wh_to_wh_data(packing)
        d = {'data': data}
        res = requests.post(endpoint, json=d, headers=cls.headers)
        if res.ok:
            clean_res = cls.response_manager.clean_dict(res.json())
            return clean_res
        else:
            return {'errors': res}

    @classmethod
    def gio_to_sepidar(cls, obj, request=None, update=False, buy_factor_data=None):
        """ send GIO to sepidar
            1: `buy factor`
            2: `inventory_receipt_before_central_wh`
            3: `voucher`
        """
        cls.setup()
        # endpoint = cls.endpoints.get(settings.SEPIDAR_CUSTOM_API_VERSION).get('inventory_purchase_invoice')
        endpoint = cls.endpoints.get(settings.SEPIDAR_CUSTOM_API_VERSION).get('gio')

        if update:
            data = {}
        else:
            buy_factor_list = list()
            out = dict()
            for supplier_currency, gio_items in obj.items():
                """ generate inventory_purchase_invoice data """
                inventory_purchase_invoice_data = cls.data.get_trade_inventory_purchase_invoice_data(supplier_currency, gio_items, request=request)
                buy_factor_list.append(inventory_purchase_invoice_data)

            """ make request for create
             1: `buy factor`
             2: `inventory_receipt_before_central_wh`
             3: `voucher` 
            """
            d = {'buy_factor_list': buy_factor_list}
            res = requests.post(endpoint, json=d, headers=cls.headers)
            if res.ok:
                out = cls.response_manager.clean_dict(res.json())
                return out

            elif res.status_code == 500:
                return {
                    "errors": "خطا در سرور سپیدار",
                }
            elif res.status_code == 400:
                return {'errors': res.json()}
            else:
                return {
                    "errors": "خطای کنترل نشده",
                }

    @classmethod
    def wh_receipt_from_bazar(cls, obj, request=None, update=False):
        cls.setup()
        endpoint = cls.endpoints.get(settings.SEPIDAR_CUSTOM_API_VERSION).get('wh_receipt_from_bazar')

        d = {'data': obj}
        res = requests.post(endpoint, json=d, headers=cls.headers)
        if res.ok:
            clean_res = cls.response_manager.clean_dict(res.json())
            return clean_res
        else:
            return {'errors': res}

    @classmethod
    def get(cls, sepidar_model_name, object_id=None, param=None):
        cls.setup()
        if object_id:
            endpoint = f'{cls.protocol}://{cls.host}:{cls.port}/api2/sepidar_api-{sepidar_model_name}/{object_id}'
        else:
            endpoint = f'{cls.protocol}://{cls.host}:{cls.port}/api2/sepidar_api-{sepidar_model_name}/'

        if param:
            endpoint += "?" + param

        res = requests.get(endpoint, headers=cls.headers)

        return res
