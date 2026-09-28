from typing import Optional
import jdatetime
import requests
from django.conf import settings
from django.core.cache import cache
from django.contrib import messages


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class ShopDataFactory(metaclass=SingletonMeta):
    def __init__(self):
        pass

    @classmethod
    def some_obj_data(cls, obj, request=None):
        """ implement data function for obj's """
        pass


class ShopResponseManager(metaclass=SingletonMeta):
    def __init__(self):
        pass

    @staticmethod
    def default(res):
        return res.json()


class ShopApiCall:
    data = ShopDataFactory()
    response_manager = ShopResponseManager()
    shop_url = settings.SHOP_URL
    token = ''
    headers = {}
    endpoints = {
        "v1": {
            'login': f'{shop_url}/core/access_token/',
            'create_shop_buy_factor': f'{shop_url}/api2/sales-purchaseorder/0/?struct_name=purchase_detail&ignore_readonly_fields',
            'update_shop_buy_factor': f'{shop_url}/api2/sales-purchaseorder/{0}/?struct_name=purchase_detail&ignore_readonly_fields',
            "shop_document": f"{shop_url}/api2/sales-supplyrequestdocument/",
        },
    }

    @classmethod
    def setup(cls):
        cls.set_token()
        cls.set_header()

    @classmethod
    def get_token(cls):
        res = cls.login()
        return res.get('tokens').get('access_token').get('value')

    @classmethod
    def set_token(cls):
        from django.core.cache import cache
        cls.token = cache.get('shop_access_token')
        if cls.token:
            return
        else:
            cls.token = cls.get_token()
            cache.set('shop_access_token', cls.token, timeout=20)

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
    def login(cls, username='09036879691', password='1234567'):
        url = cls.endpoints.get(settings.SHOP_API_VERSION).get('login')
        data = {'username': username, 'password': password}
        res = requests.post(url, data=data)
        if res.ok:
            res = res.json()
            return res
        else:
            return {}

    @classmethod
    def create_shop_buy_factor(cls, factor, response_function=None, request=None, *args, **kwargs):
        from ..product.api_call import ProductApiCall
        """
        if factor customer is MICMOD SHOP and factor has sepidar_id call shop create buy_factor api
        """

        cls.setup()
        endpoint = cls.endpoints.get(settings.PRODUCT_API_VERSION).get('create_shop_buy_factor')
        try:
            customer = getattr(factor, 'customer_party_id', None) or getattr(factor.q, 'customer_party_id', None)
            if not customer:
                return

            if customer.pk != 2691:  # 2691 is MICMOD SHOP pk in portal extra_data.customer
                return

            l = list()
            skus = ','.join(map(str, factor.factoritem_set.values_list('goods_code__id', flat=True)))
            product_access_token = cache.get("product_access_token")
            if not product_access_token:
                product_access_token = ProductApiCall.get_token()
                cache.set('product_access_token', product_access_token, 20)
            products = ProductApiCall.get_product_by_skus(skus, response_function='products_map')

            product_id = products.get('id') if products else None

            for fi in factor.factoritem_set.all():

                product_id = products.get(str(fi.goods_code.pk)) if products else None

                l.append({
                    "user": 6832,  # ادمین سیستم شاپ
                    "quantity": getattr(getattr(fi.qi, 'customer_request_item', None), 'quantity', None) or fi.quantity, # تعداد در درخواست مشتری، اگر نداشت به تعدادی که در فاکتور است میزنم
                    # تعداد در درخواست مشتری
                    "received_quantity": fi.quantity,  # تعداد در ردیف فاکتور
                    "unit_price": fi.fee_() / 10,  # فی ردیف
                    "discounted_unit_price": fi.fee_after_discount / 10,  # فی بعد از تخفیف
                    "discount_per_unit": fi.total_discount_per_item / 10,  # discount per item
                    "product": product_id,  # شناسه محصول در پروداکت
                    "source_warehouse_name": "انبارمرکزی",
                })

            d = {
                "user": 6832,  # ادمین سیستم شاپ
                "source_invoice_no": f"{factor.pk}",
                "purchase_items": l,
                "description": getattr(factor, "description", ""),
                "status": "purchase_status-invoiced_purchase"  # همین عبارت بفرست
            }

            res = requests.post(endpoint, json=d, headers=cls.headers)
            if res.ok:
                return res.json().get('pk')
            else:
                messages.error(request, f'خطا در ایجاد فاکتور خرید شاپ: {res.json()}')
                return None
        except Exception as e:
            messages.error(request, f'خطا در ایجاد فاکتور خرید شاپ: {str(e)}')
            return

    @classmethod
    def update_shop_buy_factor(cls, factor, response_function, *args, **kwargs):
        pass

    @classmethod
    def create_or_update_shop_document(cls, obj):
        supply_request = getattr(obj, 'customer_request_id', None) or getattr(getattr(obj, 'q', None), 'customer_request_id', None)
        if not supply_request:
            return

        cls.setup()
        endpoint = cls.endpoints.get(settings.PRODUCT_API_VERSION).get('shop_document')
        endpoint += f"{getattr(obj, 'shop_document_id', None) or 0}/?struct_name=doc_detail&ignore_readonly_fields"

        d = {
            "user_id": getattr(getattr(obj, 'customer_request', None), 'customer_shop', None) or getattr(getattr(getattr(obj, 'q', None), 'customer_request', None), 'customer_shop', None),
            "id": getattr(obj, 'shop_document_id', None) or 0, # باید روی اسناد پرتال این شناسه ذخیره شود و با همین شناسه آپدیت ها ارسال شود یا صفر برای ایجاد سند
            "doc_type": str(obj.__class__.__name__),  # عنوان سند quotation/factor
            "doc_number": obj.pk,  # شناسه سند در پرتال این فیلد با داک تایپ در سمت شاپ یونیک شده
            "description": getattr(obj, 'description', ""),
            "supply_request": supply_request,  # شماره درخواست مشتری
            "prepayment": (getattr(obj, 'prepayment', None) or 0) / 10,
            "supplier_source": "rahavard" if getattr(obj, "is_official", None) else "shop",  # shop/rahavard
            "doc_status": getattr(getattr(obj, 'last_work_flow', None), 'current_state_name', None),
            "final_price": obj.payment[4] / 10,  # قیمت پس از تخفیف و مالیات
            "doc_title": f"{str(obj.__class__.__name__)}_{obj.pk}",
        }

        res = requests.post(endpoint, json=d, headers=cls.headers)
        if res.ok:
            return res.json().get('id') or res.json().get('pk')
        else:
            return None
