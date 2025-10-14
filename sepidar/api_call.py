from typing import Optional
import jdatetime
import requests
from django.conf import settings
from django.utils import timezone
from core.exceptions import StockRefNotFoundError
from tools import utils


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
    def get_inventory_purchase_invoice_data(cls, obj, request=None):
        prefix = 'form'
        counter = 0
        currency = obj.get('currency') or 1
        rate = obj.get('rate') or 1
        price = obj.get('total_price') or 0
        tax = obj.get('tax') or 0
        duty = obj.get('duty') or 0
        discount = obj.get('discount') or 0
        addition = obj.get('addition') or 0
        rate, price, tax, duty, discount, addition = map(int, (rate, price, tax, duty, discount, addition))
        net_price = price - discount + addition + tax
        fisicalyearref = 46

        data = {
            "version": 1,
            "vendordlref": 3,
            "invoicenumber": None,  # گفتن که ازش استفاده نمیکنن و کلا ۴ رکورد در دیتابیس هست که اینو دارن
            "date": timezone.now().date().isoformat(),
            "currencyref": currency,
            "currencyrate": rate,
            "totalprice": price,
            "totalpriceinbasecurrency": price * rate,
            "totaltax": tax,
            "totalduty": duty,
            "totaltransportprice": 0,  # همیشه صفر بود. در جلسه تصمیم بر این شد که هزینه حمل روی رسید انبار بزنن
            "totalnetprice": net_price,
            "totalnetpriceinbasecurrency": net_price * rate,
            "totalwithholdingtaxamount": None,  # همیشه null بجز یک رکورد Todo
            "totalinsuranceamount": None,  # همیشه null بجز یک رکورد Todo
            "fiscalyearref": fisicalyearref,
            "creator": 1,  # Todo
            "creationdate": timezone.now().date().isoformat(),
            "lastmodifier": 1,  # Todo
            "lastmodificationdate": timezone.now().date().isoformat(),
            "paymentheaderref": None,  # همیشه null بجز چهار رکورد Todo
            "type": 1,  # همیشه 1 یجز همون یک رکورد Todo
            "accountingvoucherref": None,  # همیشه null بجز همون یک رکورد Todo
            "slaccountref": None,  # همیشه null بجز همون یک رکورد Todo
            "costcenterref": None,  # همیشه null
            "assetacquisitionpurchaseslref": None,  # همیشه null
            "inventorypurchaseinvoice_item": cls.get_inventory_purchase_invoice_item_data(obj, request),
        }

        return data

    @classmethod
    def get_inventory_purchase_invoice_item_data(cls, obj, request=None):
        grouped = utils.grouped_value(obj, target_suffixes=('-discount', '-itemref', '-quantity', '-price', '-addition'))

        rate = obj.get('rate') or 1
        all_tax = obj.get('tax') or 0
        all_duty = obj.get('duty') or 0
        all_discount = obj.get('discount') or 0
        rate, all_tax, all_duty, all_discount = map(int, (rate, all_tax, all_duty, all_discount))

        row_count = len(grouped) - 1  # first row is empty

        inventory_purchase_invoice_item_data = []

        for idx, row_data in grouped.items():
            if idx == '0' or idx == 0:
                continue  # first row is empty

            itemref = row_data.get('itemref')
            fee = row_data.get('price') or 0
            quantity = row_data.get('quantity') or 0
            fee, quantity = map(int, (fee, quantity))
            discount = (row_data.get('discount') or 0) + (all_discount / row_count)
            description = row_data.get('description')
            addition = row_data.get('addition') or 0

            if not (itemref or fee or quantity):
                raise Exception
            data = {
                # "inventorypurchaseinvoiceitemid": "",
                # "inventorypurchaseinvoiceref": "",
                "version": 1,
                "rownumber": int(idx),  # first row is empty
                "itemref": itemref,
                "quantity": quantity,
                "secondaryquantity": 0,  # همیشه 0
                "remainingquantity": quantity,
                "remainingsecondaryquantity": 0,  # همیشه 0
                "currencyrate": rate,
                "fee": fee,
                "feeinbasecurrency": round(fee * rate, 4),
                "price": round(fee * quantity, 4),  # کل ارزش ردیف
                "priceinbasecurrency": round(fee * quantity * rate, 4),  # کل ارزش ردیف همیشه به ریال
                "discount": discount,
                "discountinbasecurrentcy": round(discount * rate, 4),
                "addition": addition,
                "additioninbasecurrency": round(addition * rate, 4),
                "tax": round(all_tax / row_count, 4),
                "taxinbasecurrency": round((all_tax / row_count) * rate, 4),
                "duty": round(all_duty / row_count, 4),
                "dutyinbasecurrency": round((all_duty / row_count) * rate, 4),
                "transportprice": None,  # همیشه null
                # "transportpriceinbasecurrency": None,  # همیشه null  # Computed
                "transporttax": None,  # همیشه null
                # "transporttaxinbasecurrency": None,  # همیشه null  # Computed
                "transportduty": None,  # همیشه null
                # "transportdutyinbasecurrency": None,  # همیشه null   # Computed
                "transportdescription": None,  # همیشه null
                "netpriceinbasecurrency": round((fee * quantity) - discount, 4),
                "description": description,
                "description_en": None,
                # "version": "",
                "costserviceaccountslref": None,  # بجز یک رکورد همه null بودن TODO
                "insuranceamount": None,  # یک ردیف 0 بقیه همه نال
                "insuranceamountinbasecurrency": None,  # یک ردیف 0 بقیه همه نال
                "withholdingtaxamount": None,  # یک ردیف 0 بقیه همه نال
                "withholdingtaxamountinbasecurrency": None,  # یک ردیف 0 بقیه همه نال
                "tracingref": None,  # همه نال
                # "netprice": "",  # Computed
            }
            inventory_purchase_invoice_item_data.append(data)
        return inventory_purchase_invoice_item_data

    @classmethod
    def get_invoice_data(cls, obj, request=None, invoice_item_data=None):
        from inquiry.models import CurrencyAmount
        sale_type = obj.sale_type
        # currency = obj.sale_type.currency

        currency = obj.q.currency_ref

        if currency.title_en.lower() != 'rial':
            slref = 580  # حساب دریافتنی ارزی
        elif obj.is_official:
            slref = 677  # حسابهای دریافتنی رسمی
        else:
            slref = 420  # حساب دریافتنی

        currency_amount = CurrencyAmount.objects.filter(currency=currency).order_by('id').last()
        try:
            rate = float(currency_amount.open_rate) or 1  # Todo: check which price should be use
        except Exception:
            rate = 1

        if invoice_item_data is None:
            invoice_item_data = cls._get_invoice_item_data(obj, rate=rate)

        price = obj.get_price
        addition = obj.addition or 0
        duty = obj.duty or 0
        sum_tax = obj.sum_tax or 0
        sum_discount = obj.sum_discount

        invoice_data = {
            "invoice_items": invoice_item_data,
            # "partyaddressref": None,  # calculate in base
            "price": price,  # محاسبه از تمام ردیف ها fi.quantity * fi.fee
            "priceinbasecurrency": price * rate,  # calculate in save
            "date": timezone.now().date().isoformat(),  # obj.created_date.isoformat(),
            "shouldcontrolcustomercredit": 1,  # بر اساس داده های سپیدار همه 1 بودن
            "state": 1,  # بر اساس داده های سپیدار همه 1 بودن
            "additionfactor_vateffective": 0,  # بر اساس داده های سپیدار همه 0 بودن
            "additionfactorinbasecurrency_vateffective": 0,  # بر اساس داده های سپیدار همه 0 بودن
            "customerrealname_en": obj.q.customer_party_id.title,  # calculate in save
            "netpriceinbasecurrency": (price + addition + duty + sum_tax - sum_discount) * rate,  # calculate in save
            "currencyref": currency.sepidar_id,  # calculate in base
            "additioninbasecurrency": addition * rate,  # calculate in save
            "additionfactorinbasecurrency_vatineffective": 0,  # بر اساس داده های سپیدار همه 0 بودن
            "discount": sum_discount,  # calculate in base
            "quotationref": obj.q.sepidar_quotation_id,
            "lastmodifier": obj.editor_user.sepidar_code or 1,  # Todo: set sepidar_code for all portal user
            "taxinbasecurrency": sum_tax * rate,  # calculate in save
            # "number": None,  # calculate in base
            "version": 1,  # calculate in base
            "slref": slref,  # از آقای مختاری سوال شود
            "creationdate": timezone.now().isoformat(),  # calculate in base
            "duty": duty,  # calculate in base
            "guid": obj.guid,
            "deliverylocationref": 1,  # بر اساس داده های سپیدار همه 1 بودن
            "taxpayerbillissuedatetime": None,  # زمان ثبت سند در سامانه مودیان با آقای مختاری
            "orderref": None,  # همه null بودن
            "rate": rate or 1,
            # بعدا مکانیزم طوری شود که ریت به صورت روزانه توسط ادمین اپدیت شود در جدول کارنسی و اینجا ملزم ار ان گرفته شود و نده
            "settlementtype": 1,  # همه 1 بودن
            "creator": obj.creator_user.sepidar_code or 1,
            "customerpartyref": obj.q.customer_party_id_id,
            "baseoninventorydelivery": 1,  # 0-1  هست دقیق بررسی شود با چه فرمولی
            # "voucherref": None, base
            "agreementref": None,  # all null
            "additionfactor_vatineffective": 0,  # all 0
            "description": obj.description,
            "customerrealname": obj.q.customer_party_id.title,  # calculate in save
            "addition": addition,
            "dutyinbasecurrency": duty * rate,  # calculate in save
            "fiscalyearref": 46,  # calculate in base
            # "netprice": None,  # محاسبه میشه
            "tax": sum_tax,  # محاسبه از تمام ردیف ها
            "discountinbasecurrency": sum_discount * rate,  # calculate in save
            "lastmodificationdate": obj.last_update_date.isoformat(),  # calculate in base
            "saletyperef": sale_type.pk,  # باید معادل کد سپیداری را بفرستیم توی مدلش اضافه کنیم این فیلد Todo
        }

        return invoice_data

    @classmethod
    def _get_invoice_item_data(cls, obj, *args, **kwargs):
        from inquiry.models import CurrencyAmount
        invoice_item_data = list()

        fis = obj.factoritem_set.all()
        addition = obj.q.addition or 0
        fis_count = obj.factoritem_set.count()
        rate = float(kwargs.get('rate', 1))

        for fi in fis:
            row_price = fi.row_price
            discount = fi.discount_value
            tax = fi.tax
            duty = 0  # fi.duty
            fi.description = ''
            stockref = fi.get_sepidar_stock_code_from_selected_supply_location()
            if not stockref:
                raise StockRefNotFoundError()
            d = {
                "rowid": fi.index + 1 if fi.index else 1,
                "tracingref": None,  # همیشه نال
                "quantity": fi.quantity,  # check with sepidar quantity when InventoryDeliveryItem save
                "secondaryquantity": 0.0,  # معمولا 0
                "fee": fi.price,  # unit_price
                "price": row_price,  # total per row: quantity * unit_price
                "priceinbasecurrency": row_price * rate,  # calculate in save
                "discount": discount,
                "discountinbasecurrency": discount * rate,  # calculate in save
                "priceinfodiscountrate": 0.0,  # معمولا صفر (نرخ تخفیف روی قیمت)
                "customerdiscountrate": fi.customerdiscountrate(row_price, discount),
                # از اقای مختاری و فروش سوال شود (تخفیف به مشتری)
                "addition": addition / fis_count,  # از اقای مختاری و فروش سوال شود
                "additioninbasecurrency": (addition / fis_count) * rate,  # calculate in save از آقای مختاری
                "tax": tax,  # calculate in save از آقای مختاری
                "taxinbasecurrency": tax * rate,  # calculate in save از آقای مختاری
                "duty": duty,  # calculate in save از آقای مختاری
                "dutyinbasecurrency": duty * rate,  # calculate in save از آقای مختاری
                "netpriceinbasecurrency": (row_price + tax + duty + addition - discount) * rate,
                # calculate in save = row_price + tax + duty + addition - discount
                "rate": rate,  # fi.factor.rate,  # نده و در سیو از اینویس بگیرش
                "description": fi.description,
                "description_en": fi.description,
                "priceinfopricediscount": 0.0,  # سوال شود calculate in save فقط در فاکتور های قدیمی زده شده
                "priceinfopercentdiscount": 0.0,  # سوال شود calculate in save فقط در فاکتور های قدیمی زده شده
                "customerdiscount": 0.0,  # سوال شود calculate in save Todo
                "productpackquantity": None,  # همیشه null بود
                "aggregateamountdiscountrate": 0.0,  # همیشه 0
                "aggregateamountpricediscount": 0.0,  # همیشه 0
                "aggregateamountpercentdiscount": 0.0,  # همیشه 0
                "orderitemref": None,  # همیشه null
                "additionfactor_vateffective": 0.0,  # همیشه 0
                "additionfactorinbasecurrency_vateffective": 0.0,  # همیشه 0
                "additionfactor_vatineffective": 0.0,  # همیشه 0
                "additionfactorinbasecurrency_vatineffective": 0.0,  # همیشه 0
                "itemref": fi.goods_code.sepidar_id_0,
                "stockref": stockref,
                "quotationitemref": fi.qi.sepidar_id,
                "discountinvoiceitemref": None,  # همیشه null بود
                "productpackref": None,  # همیشه null بود
                "discountitemgroupref": None,  # همیشه null بود
            }
            invoice_item_data.append(d)

        return invoice_item_data

    # @classmethod
    # def get_voucher_data(cls, obj, voucher_item_data):
    #     voucher_data = {
    #         # "VoucherId": "",
    #         # "Number": "", base
    #         "voucher_items": voucher_item_data,
    #         "Date": timezone.now().date(),
    #         "ReferenceNumber": None,  # ?
    #         "SecondaryNumber": None,  # ?
    #         "State": 1,  # 1, 2 ?
    #         "Type": 1,  # 1,2,3,4,5,6 ?
    #         "FiscalYearRef": "",  # base
    #         "Description": "",  # base
    #         "Description_En": "",  # base
    #         # "Version": "",  # base
    #         "Creator": obj.creator_user.sepidar_code,
    #         "CreationDate": timezone.now(),
    #         "LastModifier": obj.editor_user.sepidar_code,
    #         "LastModificationDate": obj.last_update_date,
    #         "DailyNumber": "",  # base
    #         "IssuerSystem": "",  # ?
    #         "IsMerged": 0,  # همه رکورد ها 0 بودن
    #         "MergedIssuerSystem": None  # همه null بودن
    #     }
    #
    #     return voucher_data
    #
    # @classmethod
    # def get_voucher_item_data(cls, obj):
    #     voucher_item_data = [
    #         {
    #             # "VoucherRef": "",
    #             "RowNumber": '1',
    #             "AccountSLRef": "?",
    #             "DLRef": obj.customer.sepidar_party_id,
    #             "Debit": 1,
    #             "Credit": 0,
    #             "CurrencyRef": obj.q.sale_type.currency.number if obj.q.sale_type.currency.title != 'ریال' else None,
    #             "CurrencyRate": obj.currency_rate if getattr(obj, 'currency_rate', None) else None,
    #             "CurrencyDebit": "",  # مبلغ غیر ریالی فاکتور
    #             "CurrencyCredit": "",  # مبلغ غیر ریالی فاکتور
    #             "TrackingNumber": "",  # ?
    #             "TrackingDate": "",  # ?
    #             "IssuerEntityName": "SG.Sales.InvoiceManagement.Common.DsInvoice, SG.Sales.InvoiceManagement.Common, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null",
    #             "IssuerEntityRef": "",  # ?
    #             "Description": "",  # calculate in save
    #             "Description_En": "",  # calculate in save
    #         },
    #         {
    #             # "VoucherRef": "",
    #             "RowNumber": '2',
    #             "AccountSLRef": "?",
    #             "DLRef": None,
    #             "Debit": 0,
    #             "Credit": 1,
    #             "CurrencyRef": obj.q.sale_type.currency.number if obj.q.sale_type.currency.title != 'ریال' else None,
    #             "CurrencyRate": obj.currency_rate if getattr(obj, 'currency_rate', None) else None,
    #             "CurrencyDebit": "",  # مبلغ غیر ریالی فاکتور
    #             "CurrencyCredit": "",  # مبلغ غیر ریالی فاکتور
    #             "TrackingNumber": "",  # ?
    #             "TrackingDate": "",  # ?
    #             "IssuerEntityName": "SG.Sales.InvoiceManagement.Common.DsInvoice, SG.Sales.InvoiceManagement.Common, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null",
    #             "IssuerEntityRef": "",  # ?
    #             "Description": "",  # calculate in save
    #             "Description_En": "",  # calculate in save
    #         }
    #     ]
    #
    #     return voucher_item_data
    #
    # @classmethod
    # def get_inventory_delivery_data(cls):
    #     return
    #
    # @classmethod
    # def get_inventory_delivery_item_data(cls, obj):
    #     inventory_delivery_item_data = list()
    #     for fi in obj.factoritem_set.all():
    #         d = {
    #             # "InventoryDeliveryItemID": "",  # pk
    #             # "InventoryDeliveryRef": "",  # FK to parent
    #             "IsReturn": 0,  # 0, 1
    #             "RowNumber": fi.index + 1 if fi.index else 1,
    #             # "BaseInvoiceItem": fi.pk,  # ردیف فاکتور سپیدار
    #             "BaseInventoryDeliveryItem": "",
    #             "BaseReturnedInvoiceItem": "",
    #             "ItemRef": "",
    #             "TracingRef": "",
    #             "Quantity": "",
    #             "SecondaryQuantity": "",
    #             "RemainingQuantity": "",
    #             "RemainingSecondaryQuantity": "",
    #             "SLAccountRef": "",
    #             "Price": "",
    #             "Description": "",
    #             "Description_En": "",
    #             "Version": "",
    #             "ProductOrderRef": "",
    #             "ParityCheck": "",
    #             "QuotationItemRef": "",
    #             "WeighingRef": "",
    #             "ItemRequestItemRef": "",
    #             "ItemDescription": "",
    #             "Fee": ""
    #         }
    #         inventory_delivery_item_data.append(d)
    #
    #     return inventory_delivery_item_data
    #
    # @classmethod
    # def get_extra_data_data(cls):
    #     return


class SepidarApiCall:
    data = SepidarDataFactory()
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
            'voucher': f'{protocol}://{host}:{port}/api2/sepidar_api-voucher/',
            'extra_data': f'{protocol}://{host}:{port}/api2/sepidar_api-extradata/',
            'inventory_delivery': f'{protocol}://{host}:{port}/api2/sepidar_api-inventorydelivery/',
            'inventory_purchase_invoice': f'{protocol}://{host}:{port}/api2/sepidar_api-inventorypurchaseinvoice/',
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
                r = {item.get('stockref_str'): item.get('quantity') for item in response.get('results') if
                     float(item.get('quantity')) > 0}
            else:
                r = {(item.get('fk_strs').get('stockref'), item.get('stockref')): item.get('quantity') for item in
                     response.get('results') if
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
    def factor_to_sepidar(cls, obj, request=None, update=False):
        cls.setup()
        endpoint = cls.endpoints.get(settings.SEPIDAR_CUSTOM_API_VERSION).get('invoice')
        if update:
            data = {}
        else:
            invoice_data = cls.data.get_invoice_data(obj, request, invoice_item_data=None)

            res = requests.post(endpoint, json=invoice_data, headers=cls.headers)
            if res.ok:
                data = res.json()
                out = {
                    "number": data.get("number"),
                    "invoiceid": data.get("invoiceid"),
                    'invoice_items': [{"invoiceitemid": x.get("invoiceitemid"),
                                       "quantity": x.get('quantity'),
                                       "itemref": x.get('itemref'),
                                       }
                                      for x in res.json().get('invoice_items')
                                      ],
                }
                return out
            else:
                return None

    @classmethod
    def buy_factor_to_sepidar(cls, obj, request=None, update=False):
        cls.setup()
        endpoint = cls.endpoints.get(settings.SEPIDAR_CUSTOM_API_VERSION).get('inventory_purchase_invoice')
        if update:
            data = {}
        else:
            inventory_purchase_invoice_data = cls.data.get_inventory_purchase_invoice_data(obj, request=None)

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