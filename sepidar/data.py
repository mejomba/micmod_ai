from django.conf import settings
from django.utils import timezone
from datetime import datetime, time, timedelta
from core.exceptions import StockRefNotFoundError
from sepidar.models import Dl
from tools import utils

delta = timezone.timedelta(hours=3, minutes=30)


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
    def get_quotation_data(cls, obj):
        currency = obj.currency_ref.sepidar_id or 1
        rate = obj.currency_ref.current_rate() or 1
        quotation_payment = obj.payment
        price_ = quotation_payment[0] or 1
        tax_ = quotation_payment[3] or 0
        duty_ = obj.duty_amount or 0
        addition_ = quotation_payment[1]  # sepidar dont save addition for quotation(main form)
        discount_ = quotation_payment[2] or 0

        qis = []
        for idx, qi in enumerate(obj.quotation.all(), 1):
            fee = qi.sepidar_fee or 1
            net_price = qi.net_price or 1
            discount = qi.discount_value or 0
            tax = qi.tax or 0
            duty = qi.duty or 0
            addition = obj.addition if (idx == 1 and obj.addition) else 0

            d = {
                "rowid": idx,
                "itemref": qi.goods_code_fk.sepidar_id_0,
                "tracingref": None,
                "stockref": 2,  # optional
                "quantity": qi.quantity,
                "secondaryquantity": None,
                "fee": round(fee, 4),
                "price": round(net_price, 4),
                "priceinbasecurrency": round(net_price * rate, 4),
                "discount": discount,
                "discountinbasecurrency": round(discount * rate, 4),
                "priceinfodiscountrate": 0,
                "customerdiscountrate": 0.0,
                "addition": round(addition, 4),
                "additioninbasecurrency": round(addition * rate, 4),
                "tax": round(tax, 4),
                "taxinbasecurrency": round(tax * rate, 4),
                "duty": round(duty, 4),
                "dutyinbasecurrency": round(duty * rate, 4),
                "netpriceinbasecurrency": round(net_price * rate, 4),
                "rate": 1,
                "usedquantity": 0,
                "description": (qi.description or '') + '(پرتال)',
                "description_en": "",
                "discountquotationitemref": None,
                "priceinfopricediscount": 0,
                "priceinfopercentdiscount": 0,
                "customerdiscount": 0.0,
                "productpackref": None,
                "productpackquantity": None,
                "aggregateamountdiscountrate": 0,
                "aggregateamountpricediscount": 0,
                "aggregateamountpercentdiscount": 0,
                "additionfactor_vateffective": 0,
                "additionfactorinbasecurrency_vateffective": 0,
                "additionfactor_vatineffective": 0,
                "additionfactorinbasecurrency_vatineffective": 0
            }
            qis.append(d)

        q = {
            "fiscalyearref": settings.SEPIDAR_CONST_DATA['fiscalyearref'],
            "customerpartyref": obj.customer_party_id.sepidar_party_id,
            "saletyperef": obj.sale_type.sepidar_id or obj.sale_type.pk,
            "expirationdate": obj.expiration_date.isoformat(),
            "date": timezone.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
            "creationdate": obj.created_date.isoformat(),
            "lastmodificationdate": obj.last_update_date.isoformat(),
            "currencyref": currency,
            "price": round(price_, 4),
            "discount": round(discount_, 4),
            "addition": round(addition_, 4),
            "tax": round(tax_, 4),
            "discountinbasecurrency": round(discount_ * rate, 4),
            "additioninbasecurrency": round(addition_ * rate, 4),
            "taxinbasecurrency": round(tax_ * rate, 4),
            "dutyinbasecurrency": round(duty_ * rate, 4),
            "netpriceinbasecurrency": round(price_ * rate, 4),
            "duty": round(duty_, 4),
            "priceinbasecurrency": round(price_ * rate, 4),
            "rate": round(rate, 4),
            "deliverylocationref": 1,
            "creator": obj.creator_user.sepidar_code,
            "lastmodifier": obj.editor_user.sepidar_code,
            "closed": 0,
            "receiptref": None,
            "paymentref": None,
            "customerrealname": obj.customer_party_id.title,
            "customerrealnameen": obj.customer_party_id.title,
            "guid": None,
            "additionfactor_vateffective": 0,
            "additionfactor_vatineffective": 0,
            "additionfactorinbasecurrency_vateffective": 0,
            "additionfactorinbasecurrency_vatineffective": 0,
            "version": 1,
            "quotation_items": qis
        }

        return q

    @classmethod
    def get_inventory_purchase_invoice_data(cls, obj, request=None):
        prefix = 'form'
        counter = 0
        currency = obj.get('currency') or 1
        rate = obj.get('rate') or 1
        price = obj.get('total_price') or 0
        tax = obj.get('tax') or 0
        duty = obj.get('duty') or 0
        supplier = obj.get('supplier')
        creator = request.user.sepidar_code
        if not creator:
            raise Exception("کاربر کد سپیدار ندارد")
        if not supplier:
            raise Exception("تامین کننده انتخاب نشده")
        discount = obj.get('discount') or 0
        addition = obj.get('addition') or 0
        rate, price, tax, duty, discount, addition = map(float, (rate, price, tax, duty, discount, addition))


        grouped = utils.grouped_value(obj, target_suffixes=('-discount', '-itemref', '-quantity', '-price', '-addition'))
        for idx, row_data in grouped.items():
            if idx == '0' or idx == 0:
                continue  # first row is empty in bazar order trade order start idx from 1 => (enumerate(order, start=1)
            discount += (row_data.get('discount') or 0)
            addition += (row_data.get('addition') or 0)

        net_price = price - discount + addition + tax

        fisicalyearref = settings.SEPIDAR_CONST_DATA.get('fiscalyearref')

        delta = timezone.timedelta(hours=3, minutes=30)

        data = {
            "version": 1,
            "vendordlref": supplier,
            "invoicenumber": None,  # گفتن که ازش استفاده نمیکنن و کلا ۴ رکورد در دیتابیس هست که اینو دارن
            "date": (timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)).isoformat(),
            "currencyref": currency,
            "currencyrate": rate,
            "totalprice": round(price, 4),
            "totalpriceinbasecurrency": round(price * rate, 4) if currency != 1 else 0,
            "totaltax": round(tax, 4),
            "totalduty": round(duty, 4),
            "totaltransportprice": 0,  # همیشه صفر بود. در جلسه تصمیم بر این شد که هزینه حمل روی رسید انبار بزنن
            "totalnetprice": round(net_price, 4),
            "totalnetpriceinbasecurrency": round(net_price * rate, 4) if currency != 1 else 0,
            "totalwithholdingtaxamount": None,  # همیشه null بجز یک رکورد Todo
            "totalinsuranceamount": None,  # همیشه null بجز یک رکورد Todo
            "fiscalyearref": fisicalyearref,
            "creator": creator,  # Todo
            "creationdate": (timezone.now()+delta).isoformat(),
            "lastmodifier": creator,  # Todo
            "lastmodificationdate": (timezone.now()+delta).isoformat(),
            "paymentheaderref": None,  # همیشه null بجز چهار رکورد Todo
            "type": 1,  # همیشه 1 یجز همون یک رکورد Todo
            "accountingvoucherref": None,  # همیشه null بجز همون یک رکورد Todo
            "slaccountref": None,  # همیشه null بجز همون یک رکورد Todo
            "costcenterref": None,  # همیشه null
            "assetacquisitionpurchaseslref": None,  # همیشه null
            "inventorypurchaseinvoice_item": cls.get_inventory_purchase_invoice_item_data(obj, request, grouped=grouped),
        }

        return data

    @classmethod
    def get_inventory_purchase_invoice_item_data(cls, obj, request=None, grouped=None):

        total_price = obj.get('total_price') or 0
        rate = obj.get('rate') or 1
        all_tax = obj.get('tax') or 0
        all_duty = obj.get('duty') or 0
        all_discount = obj.get('discount') or 0
        rate, all_tax, all_duty, all_discount = map(int, (rate, all_tax, all_duty, all_discount))

        row_count = len(grouped) - 1  # first row is empty

        inventory_purchase_invoice_item_data = []

        for idx, row_data in grouped.items():
            if idx == '0' or idx == 0:
                continue  # first row is empty in bazar order trade order start idx from 1 => (enumerate(order, start=1)
            discount_weight = (row_data.get('price', 0) * row_data.get('quantity', 0) / total_price)
            tax_weight = ((row_data.get('price', 0) * row_data.get('quantity', 0)) / total_price) if all_tax else 1
            tax = row_data.get('tax', 0) + all_tax * tax_weight
            itemref = row_data.get('itemref')
            fee = row_data.get('price') or 0
            quantity = row_data.get('quantity') or 0
            fee, quantity = map(float, (fee, quantity))
            discount = (row_data.get('discount') or 0) + (all_discount * discount_weight)
            description = row_data.get('description')
            addition = row_data.get('addition') or 0

            if not (itemref or fee or quantity):
                raise Exception("(itemref or fee or quantity) is None")
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
                "feeinbasecurrency": round(fee * rate, 4) if rate != 1 else 0,
                "price": round(fee * quantity, 4),  # کل ارزش ردیف
                "priceinbasecurrency": round(fee * quantity * rate, 4) if rate != 1 else 0,  # کل ارزش ردیف همیشه به ریال
                "discount": round(discount, 4),
                "discountinbasecurrentcy": round(discount * rate, 4) if rate != 1 else 0,
                "addition": round(addition, 4),
                "additioninbasecurrency": round(addition * rate, 4) if rate != 1 else 0,
                "tax": round(tax, 4),
                "taxinbasecurrency": round(tax * rate, 4) if rate != 1 else 0,
                "duty": round(all_duty / row_count, 4),
                "dutyinbasecurrency": round((all_duty / row_count) * rate, 4) if rate != 1 else 0,
                "transportprice": None,  # همیشه null
                "transporttax": None,  # همیشه null
                "transportduty": None,  # همیشه null
                "transportdescription": None,  # همیشه null
                "netpriceinbasecurrency": round((fee * quantity) - discount, 4) if rate != 1 else 0,
                "description": description,
                "description_en": None,
                "costserviceaccountslref": None,  # بجز یک رکورد همه null بودن TODO
                "insuranceamount": None,  # یک ردیف 0 بقیه همه نال
                "insuranceamountinbasecurrency": None,  # یک ردیف 0 بقیه همه نال
                "withholdingtaxamount": None,  # یک ردیف 0 بقیه همه نال
                "withholdingtaxamountinbasecurrency": None,  # یک ردیف 0 بقیه همه نال
                "tracingref": None,  # همه نال
            }
            inventory_purchase_invoice_item_data.append(data)
        return inventory_purchase_invoice_item_data

    @classmethod
    def get_invoice_data(cls, obj, request=None, invoice_item_data=None):
        from inquiry.models import CurrencyAmount
        sale_type = obj.sale_type
        # currency = obj.sale_type.currency

        currency = getattr(obj, 'currency_ref', None) or obj.q.currency_ref
        customer = getattr(obj, 'customer_party_id', None) or obj.q.customer_party_id

        if currency.title_en.lower() != 'rial':
            slref = settings.SEPIDAR_CONST_DATA['hesab_daryaftani_arzi'] #580  # حساب دریافتنی ارزی
        elif obj.is_official:
            slref = settings.SEPIDAR_CONST_DATA['hesab_daryaftani_rasmi']  # حسابهای دریافتنی رسمی
        else:
            slref = settings.SEPIDAR_CONST_DATA['hesab_daryaftani']  # حساب دریافتنی

        currency_amount = CurrencyAmount.objects.filter(currency=currency).order_by('id').last()
        try:
            rate = float(obj.currency_amount) if obj.currency_amount else float(currency_amount.open_rate) or 1
        except Exception:
            rate = 1

        if invoice_item_data is None:
            invoice_item_data = cls._get_invoice_item_data(obj, rate=rate)

        price = obj.get_price
        addition = obj.addition or obj.q.addition or 0
        duty = obj.duty or 0
        sum_tax = obj.sum_tax or 0
        sum_discount = obj.sum_discount

        invoice_data = {
            "invoice_items": invoice_item_data,
            # "partyaddressref": None,  # calculate in base
            "price": round(price, 4),  # محاسبه از تمام ردیف ها fi.quantity * fi.fee
            "priceinbasecurrency": round(price * rate, 4) if rate != 1 else 0,
            "date": timezone.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),  # obj.created_date.isoformat(),
            "shouldcontrolcustomercredit": 1,  # بر اساس داده های سپیدار همه 1 بودن
            "state": 1,  # بر اساس داده های سپیدار همه 1 بودن
            "additionfactor_vateffective": 0,  # بر اساس داده های سپیدار همه 0 بودن
            "additionfactorinbasecurrency_vateffective": 0,  # بر اساس داده های سپیدار همه 0 بودن
            "customerrealname_en": customer.title.replace("ی", "ي").replace("ک", "ك"),  # calculate in save
            "netpriceinbasecurrency": round((price + addition + duty + sum_tax - sum_discount) * rate, 4),
            "currencyref": currency.sepidar_id,  # calculate in base
            "additioninbasecurrency": round(addition * rate, 4),  # calculate in save
            "additionfactorinbasecurrency_vatineffective": 0,  # بر اساس داده های سپیدار همه 0 بودن
            "discount": round(sum_discount, 4),
            "quotationref": None, #obj.q.sepidar_quotation_id,
            "lastmodifier": obj.editor_user.sepidar_code or 1,  # Todo: set sepidar_code for all portal user
            "taxinbasecurrency": round(sum_tax * rate, 4),  # calculate in save
            "version": 1,  # calculate in base
            "slref": slref,  # از آقای مختاری سوال شود
            "creationdate": timezone.now().isoformat(),  # calculate in base
            "duty": round(duty or 0, 4),
            "guid": obj.guid,
            "deliverylocationref": 1,  # بر اساس داده های سپیدار همه 1 بودن
            "taxpayerbillissuedatetime": None,  # زمان ثبت سند در سامانه مودیان با آقای مختاری
            "orderref": None,  # همه null بودن
            "rate": rate or 1,
            # بعدا مکانیزم طوری شود که ریت به صورت روزانه توسط ادمین اپدیت شود در جدول کارنسی و اینجا ملزم ار ان گرفته شود و نده
            "settlementtype": 1,  # همه 1 بودن
            "creator": obj.creator_user.sepidar_code or 1,
            "customerpartyref": customer.sepidar_party_id,
            "baseoninventorydelivery": 1,  # 0-1  هست دقیق بررسی شود با چه فرمولی
            # "voucherref": None, base
            "agreementref": None,  # all null
            "additionfactor_vatineffective": 0,  # all 0
            "description": obj.description,
            "customerrealname": customer.title.replace("ی", "ي").replace("ک", "ك"),  # calculate in save
            "addition": round(addition, 4),
            "dutyinbasecurrency": round(duty * rate, 4),
            "fiscalyearref": settings.SEPIDAR_CONST_DATA.get('fiscalyearref'),
            "tax": round(sum_tax, 4),
            "discountinbasecurrency": round(sum_discount * rate, 4),
            "lastmodificationdate": obj.last_update_date.isoformat(),
            "saletyperef": sale_type.sepidar_id or sale_type.pk,
        }

        return invoice_data

    @classmethod
    def _get_invoice_item_data(cls, obj, *args, **kwargs):
        from inquiry.models import CurrencyAmount
        invoice_item_data = list()

        fis = obj.factoritem_set.all().order_by('id')
        addition = getattr(obj, 'addition', None) or getattr(obj.q, 'addition', None) or 0
        fis_count = obj.factoritem_set.count()
        rate = float(kwargs.get('rate', 1))

        for idx, fi in enumerate(fis):
            row_price = fi.row_price
            discount = fi.discount_value
            tax = fi.tax or 0
            duty = 0  # fi.duty
            fi.description = ''
            stockref = fi.get_sepidar_stock_code_from_selected_supply_location()
            if stockref == 0:
                raise StockRefNotFoundError("فاکتور با محل تامین از نوع سفارش قبل از رسید شدن کالا در انبار قابل ارسال به سپیدار نیست.")
            if not stockref:
                raise StockRefNotFoundError()
            d = {
                "rowid": idx + 1,
                "tracingref": None,  # همیشه نال
                "quantity": fi.quantity,  # check with sepidar quantity when InventoryDeliveryItem save
                "secondaryquantity": 0.0,  # معمولا 0
                "fee": round(fi.price, 4),  # unit_price
                "price": round(row_price, 4),  # total per row: quantity * unit_price
                "priceinbasecurrency": round(row_price * rate, 4),
                "discount": round(discount, 4),
                "discountinbasecurrency": round(discount * rate, 4),
                "priceinfodiscountrate": 0.0,  # معمولا صفر (نرخ تخفیف روی قیمت)
                "customerdiscountrate": fi.customerdiscountrate(row_price, discount),
                # از اقای مختاری و فروش سوال شود (تخفیف به مشتری)
                "addition": round(addition / fis_count, 4) if rate != 1 else int(addition / fis_count),  # از اقای مختاری و فروش سوال شود
                "additioninbasecurrency": round((addition / fis_count) * rate, 4),
                "tax": round(tax, 4),  # calculate in save از آقای مختاری
                "taxinbasecurrency": round(tax * rate, 4),  # calculate in save از آقای مختاری
                "duty": round(duty, 4),  # calculate in save از آقای مختاری
                "dutyinbasecurrency": round(duty * rate, 4),  # calculate in save از آقای مختاری
                "netpriceinbasecurrency": round((row_price + tax + duty + addition - discount) * rate, 4),
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
                "quotationitemref": getattr(fi.qi, 'sepidar_id', None) or None,
                "discountinvoiceitemref": None,  # همیشه null بود
                "productpackref": None,  # همیشه null بود
                "discountitemgroupref": None,  # همیشه null بود
            }
            invoice_item_data.append(d)

        return invoice_item_data

    @classmethod
    def get_trade_inventory_purchase_invoice_data(cls, supplier_currency, gio_items, request):
        totalprice = tax = duty = addition = discount = 0
        fiscalyearref = settings.SEPIDAR_CONST_DATA.get('fiscalyearref')
        creator = request.user.sepidar_code

        rate = Dl.account_currency_rate(supplier_currency.split('___')[0],
                                        settings.SEPIDAR_CONST_DATA.get('fiscalyearref'),
                                        settings.SEPIDAR_CONST_DATA.get('hesab_pardakhtani'),
                                        supplier_currency.split('___')[1])
        rate = round(rate, 0)
        all_tax = 0
        all_duty = 0
        all_discount = 0
        rate, all_tax, all_duty, all_discount = map(int, (rate, all_tax, all_duty, all_discount))

        row_count = len(gio_items)
        row_items = []
        for idx, gio_item in enumerate(gio_items, start=1):
            totalprice += gio_item.order.final_price
            itemref = gio_item.order.item.sepidar_id_0
            fee = gio_item.order.final_price or 0
            quantity = gio_item.quantity or 0
            fee, quantity = map(float, (fee, quantity))
            discount = (gio_item.order.final_discount or 0) + (all_discount / row_count)
            description = gio_item.description
            addition = gio_item.order.final_addition or 0

            if not (itemref or fee or quantity):
                raise Exception("(itemref or fee or quantity) is None")

            row_data = {
                # "inventorypurchaseinvoiceitemid": "",
                # "inventorypurchaseinvoiceref": "",
                "version": 1,
                "rownumber": int(idx),
                "itemref": itemref,
                "quantity": quantity,
                "secondaryquantity": 0,  # همیشه 0
                "remainingquantity": quantity,
                "remainingsecondaryquantity": 0,  # همیشه 0
                "currencyrate": rate or 1,
                "fee": round(fee, 4),
                "feeinbasecurrency": round(fee * rate, 4) if rate != 1 else 0,
                "price": round(fee * quantity, 4),  # کل ارزش ردیف
                "priceinbasecurrency": round(fee * quantity * rate, 4) if rate != 1 else 0,
                "discount": round(discount, 4),
                "discountinbasecurrentcy": round(discount * rate, 4) if rate != 1 else 0,
                "addition": addition,
                "additioninbasecurrency": round(addition * rate, 4) if rate != 1 else 0,
                "tax": round(all_tax / row_count, 4),
                "taxinbasecurrency": round((all_tax / row_count) * rate, 4) if rate != 1 else 0,
                "duty": round(all_duty / row_count, 4),
                "dutyinbasecurrency": round((all_duty / row_count) * rate, 4) if rate != 1 else 0,
                "transportprice": None,  # همیشه null
                # "transportpriceinbasecurrency": None,  # همیشه null  # Computed
                "transporttax": None,  # همیشه null
                # "transporttaxinbasecurrency": None,  # همیشه null  # Computed
                "transportduty": None,  # همیشه null
                # "transportdutyinbasecurrency": None,  # همیشه null   # Computed
                "transportdescription": None,  # همیشه null
                "netpriceinbasecurrency": round((fee * quantity) - discount, 4) if rate != 1 else 0,
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
            row_items.append(row_data)

        totalnetprice = round(totalprice - discount + addition + tax, 4)

        data = {
                "version": 1,
                "vendordlref": supplier_currency.split('___')[0],
                "invoicenumber": None,  # گفتن که ازش استفاده نمیکنن و کلا ۴ رکورد در دیتابیس هست که اینو دارن
                "date": timezone.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
                "currencyref": supplier_currency.split('___')[1],
                "currencyrate": rate or 1,  # Todo این چطوری حساب میشه؟
                "totalprice": round(totalprice, 4),
                "totalpriceinbasecurrency": round(totalprice * rate, 4) if rate != 1 else 0,
                "totaltax": round(tax, 4),
                "totalduty": round(duty, 4),
                "totaltransportprice": 0,  # همیشه صفر بود. در جلسه تصمیم بر این شد که هزینه حمل روی رسید انبار بزنن
                "totalnetprice": round(totalnetprice, 4),
                "totalnetpriceinbasecurrency": round(totalnetprice * rate, 4) if rate != 1 else 0,
                "totalwithholdingtaxamount": None,  # همیشه null بجز یک رکورد Todo
                "totalinsuranceamount": None,  # همیشه null بجز یک رکورد Todo
                "fiscalyearref": fiscalyearref,
                "creator": creator,  # Todo
                "creationdate": timezone.now().isoformat(),
                "lastmodifier": creator,  # Todo
                "lastmodificationdate": timezone.now().isoformat(),
                "paymentheaderref": None,  # همیشه null بجز چهار رکورد Todo
                "type": 1,  # همیشه 1 یجز همون یک رکورد Todo
                "accountingvoucherref": None,  # همیشه null بجز همون یک رکورد Todo
                "slaccountref": None,  # همیشه null بجز همون یک رکورد Todo
                "costcenterref": None,  # همیشه null
                "assetacquisitionpurchaseslref": None,  # همیشه null
                "inventorypurchaseinvoice_item": row_items,
            }

        return data

    @classmethod
    def get_receipt_before_central_wh_data(cls, buy_factor_data, request):

        inventoryreceipt_items = []
        for idx, ipi in enumerate(buy_factor_data.get('inventorypurchaseinvoice_item'), start=1):
            currency_rate = ipi.get('currencyrate')
            if currency_rate and float(currency_rate) == 1.0:
                currency_rate = None

            inventoryreceipt_items.append({
                # "inventoryreceiptref": 555,
                "isreturn": 0,
                "currencyref": None,
                "taxcurrencyvalue": None,
                "dutycurrencyvalue": None,
                "paritycheck": None,
                "productorderref": None,
                "inventorydeliveryitemref": None,
                "weighingref": None,
                "baseimportpurchaseinvoiceitemref": None,
                "allotmenedothercostinbasecurrency": None,
                "rownumber": ipi.get('rownumber'),
                "base": 1300,
                "itemref": ipi.get('itemref'),
                "tracingref": None,
                "quantity": ipi.get('quantity'),
                "remainingquantity": ipi.get('remainingquantity'),
                "secondaryquantity": ipi.get('secondaryquantity'),
                "currencyrate": currency_rate,
                "currencyvalue": None,
                "fee": ipi.get('fee'),
                "price": ipi.get('price'),
                "tax": ipi.get('tax'),
                "duty": ipi.get('duty'),
                "transportprice": ipi.get('transportprice'),
                "transporttax": ipi.get('transporttax'),
                "transportduty": ipi.get('transportduty'),
                "transportdescription": ipi.get('transportdescription'),
                "description": ipi.get('description'),
                "version": ipi.get('version'),
                "description_en": ipi.get('description_en'),
                "basepurchaseinvoiceitemref": ipi.get('inventorypurchaseinvoiceitemid'),
            })

        data = {
            "isreturn": 0,
            "stockref": settings.SEPIDAR_CONST_DATA.get('before_central_wh_id'),  # مقدار ثابت که به انبار قبل مرکزی اشاره دارد
            "delivererdlref": buy_factor_data.get('vendordlref'),
            "slaccountref": settings.SEPIDAR_CONST_DATA.get('hesab_pardakhtani'),
            "paymentheaderref": None,
            "creator": buy_factor_data.get('creator'),
            "creationdate": timezone.now().isoformat(),
            "lastmodifier": buy_factor_data.get('lastmodifier'),
            "lastmodificationdate": timezone.now().isoformat(),
            "version": 1,
            "transportbrokerslaccountref": settings.SEPIDAR_CONST_DATA.get('transportation_vaset'),
            "transporterdlref": None,  # buy_factor_data.get('vendordlref'),
            "baseinventorydeliveryref": None,
            "baseimportpurchaseinvoiceref": None,
            "totalothercost": 0,
            "date": timezone.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
            "purchasetype": 1,
            "accountingvoucherref": None,
            "totalnetprice": 1,
            "fiscalyearref": settings.SEPIDAR_CONST_DATA.get('fiscalyearref'),
            "basepurchaseinvoiceref": buy_factor_data.get('inventorypurchaseinvoiceid'),
            "totaltransportprice": 0,
            "totalduty": 0,
            "totaltax": 0,
            "totalprice": 1,
            "creatorform": 1,
            "description": None,
            "type": 1,
            "inventoryreceipt_item": inventoryreceipt_items
        }

        return data

    @classmethod
    def get_wh_to_wh_data(cls, packing, *, destination_stock_ref, lines, creator_code=None):
        """Build one Inventorydelivery payload for exactly one destination.

        The caller must split normal and damaged quantities before invoking this
        method; a Sepidar packing endpoint creates one delivery/receipt pair.
        """
        if not lines:
            raise ValueError('A warehouse transfer cannot have empty items.')
        if not destination_stock_ref:
            raise ValueError('Destination warehouse is required.')
        creator = creator_code or packing.editor_user.sepidar_code
        now = timezone.now()
        inventory_delivery_item_data = []
        for idx, line in enumerate(lines, start=1):
            inventory_delivery_item_data.append({
                "isreturn": 0,
                "rownumber": idx,
                "baseinvoiceitem": None,
                "baseinventorydeliveryitem": None,
                "basereturnedinvoiceitem": None,
                "itemref": line['itemref'],
                "tracingref": None,
                "quantity": float(line['quantity']),
                "secondaryquantity": None,
                "remainingquantity": 0,
                "remainingsecondaryquantity": None,
                "slaccountref": settings.SEPIDAR_CONST_DATA.get('wh_to_wh_vaset'),
                "price": None,
                "description": None,
                "description_En": None,
                "version": 1,
                "productorderref": None,
                "paritycheck": None,
                "quotationitemref": None,
                "weighingref": None,
                "itemrequestitemref": None,
                "itemdescription": None,
            })
        return {
            "isreturn": 0,
            "type": 4,
            "stockref": settings.SEPIDAR_CONST_DATA.get('before_central_wh_id'),
            "receiverdlref": None,
            "date": now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
            "totalprice": None,
            "accountingvoucherref": None,
            "fiscalyearref": settings.SEPIDAR_CONST_DATA.get('fiscalyearref'),
            "destinationstockref": int(destination_stock_ref),
            "creatorform": 1,
            "creator": creator,
            "creationdate": now.isoformat(),
            "lastmodifier": creator,
            "lastmodificationdate": now.isoformat(),
            "version": 1,
            "description": f'Packing {packing.pk}: warehouse transfer (portal)',
            "inventorydeliveryitem_set": inventory_delivery_item_data,
        }
