import uuid

import jdatetime
from django.contrib.auth import get_user_model
from django.db import models, IntegrityError
from django.db.models import Q, Sum
from django.utils import timezone
import os

from django.utils.safestring import mark_safe
from jalali_date.fields import JalaliDateField
from django.conf import settings
import dw.models
from micmod_base.base import BaseModel
from core.models import BaseManager, AbsBaseModel
from django.apps import apps

from sepidar.api_call import SepidarApiCall
from sepidar.models import APILogs, Item as sepidarItem
from sepidar.scripts.sepidar_classes import Urls
from tools.utils import to_jalali_date, set_secret_id
from translator import get_text as _
from sepidar.models import BaseData
from tools.form_tools import select_cquery
from django.core.validators import MaxValueValidator
from queryable_properties.properties import queryable_property

from transportation.models import TradeTransportationMethod
from dw.models import DimOrder
from django.core.cache import cache

class DiscountBasedPriceType(models.TextChoices):
    RInv = "0", _("calculate_in_invoice_row")
    SKU = "1", _("calculate_in_sku")


class CustomerType(models.TextChoices):
    Person = "1", _("person")
    Company = "2", _("company")


class CalculationMethod(models.TextChoices):
    Old = "0", _("old_calculation_method")
    New = "1", _("new_calculation_method")


def discount_based_price_json():
    return [
        {
            "title": "First Profit < 0.2 (RMB)",
            "value": 0.2,
            "percentage": -1
        },
        {
            "title": "0.5 (RMB) > First Profit >= 0.2 (RMB)",
            "value": 0.5,
            "percentage": -1.5
        },
        {
            "title": "1 (RMB) > First Profit >= 0.5 (RMB)",
            "value": 1,
            "percentage": -2
        },
        {
            "title": "2.5 (RMB) > First Profit >= 1 (RMB)",
            "value": 2.5,
            "percentage": -2.5
        },
        {
            "title": "5 (RMB) > First Profit >= 2.5 (RMB)",
            "value": 5,
            "percentage": -3
        },
        {
            "title": "10 (RMB) > First Profit >= 5 (RMB)",
            "value": 10,
            "percentage": -4
        },
        {
            "title": "20 (RMB) > First Profit >= 10 (RMB)",
            "value": 20,
            "percentage": -4.5
        },
        {
            "title": "First Profit >= 30 (RMB)",
            "value": 30,
            "percentage": -4.5
        }
    ]


def discount_based_quantity_json():
    return [
        {
            "title": "Qty 1-9",
            "value": 9,
            "percentage": -6
        },
        {
            "title": "Qty 10-99",
            "value": 99,
            "percentage": -7
        },
        {
            "title": "Qty 100-999",
            "value": 999,
            "percentage": -8
        },
        {
            "title": "Qty +1000",
            "value": 9999,
            "percentage": -10
        },
        {
            "title": "Qty +10K",
            "value": 100000,
            "percentage": -11
        }
    ]


def discount_based_customer_json():
    return [
        {
            "title": "Special",
            "percentage": -2
        },
        {
            "title": "Grade A+",
            "percentage": -2
        },
        {
            "title": "Grade A",
            "percentage": -1
        },
        {
            "title": "Grade B",
            "percentage": 0
        },
        {
            "title": "Grade C",
            "percentage": 0
        }
    ]


def discount_based_payment_method_json():
    return [
        {
            "title": "Cash",
            "rmb_percentage": 0,
            "rial_percentage": 0
        },
        {
            "title": "1 Month",
            "rmb_percentage": 3,
            "rial_percentage": 4
        },
        {
            "title": "2 Month",
            "rmb_percentage": 6,
            "rial_percentage": 8
        },
        {
            "title": "3 Month",
            "rmb_percentage": 9,
            "rial_percentage": 12
        },
        {
            "title": "4 Month",
            "rmb_percentage": 12,
            "rial_percentage": 16
        }
    ]


class PriceSettings(AbsBaseModel):
    activate = models.BooleanField(default=False, verbose_name=_("activate"))
    title = models.CharField(verbose_name=_("title"),max_length=100,unique=True)
    dollar_rmb_rate = models.FloatField(verbose_name=_('dollar_rmb_rate'), default=7)
    customs_rmb_rate = models.FloatField(verbose_name=_('customs_rmb_rate'), default=67000)
    free_rmb_rate = models.FloatField(verbose_name=_('free_rmb_rate'), default=72000)
    free_rmb_rate_new_order = models.FloatField(verbose_name=_('free_rmb_rate_new_order'), default=74000)
    talar_rmb_rate = models.FloatField(verbose_name=_('talar_rmb_rate'), default=67000)
    office_cost_percentage = models.FloatField(verbose_name=_('office_cost_percentage'), default=8)
    duty_on_value_percentage = models.FloatField(verbose_name=_('duty_on_value_percentage'), default=9)
    interest_percentage = models.FloatField(verbose_name=_('interest_percentage'), default=34)
    express_transportation_cost = models.FloatField(verbose_name=_('express_transportation_cost'), default=73)
    air_transportation_cost = models.FloatField(verbose_name=_('air_transportation_cost'), default=50)
    sea_transportation_cost = models.FloatField(verbose_name=_('sea_transportation_cost'), default=6)
    discount_based_price_type = models.CharField(max_length=2, choices=DiscountBasedPriceType.choices,
                                                 default=DiscountBasedPriceType.RInv,
                                                 verbose_name=_('discount_based_price_type'))
    discount_based_price = models.JSONField(verbose_name=_('discount_based_price'), default=discount_based_price_json)
    discount_based_quantity = models.JSONField(verbose_name=_('discount_based_quantity'), default=discount_based_quantity_json)
    discount_based_customer = models.JSONField(verbose_name=_('discount_based_customer'), default=discount_based_customer_json)
    discount_based_payment_method = models.JSONField(verbose_name=_('discount_based_payment_method'), default=discount_based_payment_method_json)
    calculation_method = models.CharField(max_length=5, verbose_name=_('calculation_method'),choices=CalculationMethod.choices
                                          ,default=CalculationMethod.Old)
    max_discount_for_final_step = models.FloatField(default=-13, verbose_name=_('max_discount_for_final_step'))
    delivery_in_china = models.BooleanField(default=False, verbose_name=_('delivery_in_china'))
    permission_json = models.JSONField(null=True, blank=True, verbose_name=_('permission_json'))
    air_extra_percent = models.PositiveSmallIntegerField(_('درصد اضافی (هوایی)'), null=True, blank=True)
    sea_extra_percent = models.PositiveSmallIntegerField(_('درصد اضافی (دریایی)'), null=True, blank=True)
    express_extra_percent = models.PositiveSmallIntegerField(_('درصد اضافی (اکسپرس)'), null=True, blank=True)

    # auto_complete = 'title'
    @staticmethod
    def setting():
        return PriceSettings.objects.filter(activate=True).first()

    def get_discount_based_price(self, price):
        for line in self.discount_based_price:
            if float(price) <= line['value']:
                return line['percentage']
        return self.discount_based_price[-1]['percentage']

    def get_discount_based_quantity(self, quantity):
        for line in self.discount_based_quantity:
            if float(quantity) <= line['value']:
                return line['percentage']
        return self.discount_based_quantity[-1]['percentage']

    def get_discount_based_customer(self, grade):
        for line in self.discount_based_customer:
            if grade == line['title']:
                return line['percentage']
        return 0

    def get_discount_based_payment_method(self, payment_method, currency):
        for line in self.discount_based_payment_method:
            if payment_method == line['title']:
                currency_prefix = currency.title_en.lower()
                return line.get(f'{currency_prefix}_percentage')
        return 0

    def __str__(self):
        return self.title


class HS(AbsBaseModel):
    code = models.CharField(verbose_name=_('code'),max_length=8,unique=True)
    title = models.CharField(verbose_name=_('title'),max_length=200,unique=True)
    title_en = models.CharField(verbose_name=_('title_en'),max_length=200,blank=True, null=True)
    price_settings = models.ForeignKey(PriceSettings, verbose_name=_("price_settings"), blank=True, null=True,
                                       on_delete=models.CASCADE)
    customs_rate = models.FloatField(verbose_name=_('customs_rate'), default=4)

    def __str__(self):
        return f'{self.code}:[{self.title_en}] {self.title[:30]} ({self.customs_rate}%)'

    class Meta:
        ordering = ['title']


class PurchaseGroup(AbsBaseModel):
    title = models.CharField(verbose_name=_('title'), max_length=100, unique=True)
    price_settings = models.ForeignKey(PriceSettings,verbose_name=_("price_settings"), blank=True, null=True, on_delete=models.CASCADE)
    hs = models.ForeignKey(HS, verbose_name=_("hs"), on_delete=models.DO_NOTHING,null=True,blank=True)
    sea_transportation = models.FloatField(verbose_name=_('sea_transportation'), default=1)
    air_transportation = models.FloatField(verbose_name=_('air_transportation'), default=1)
    express_transportation = models.FloatField(verbose_name=_('express_transportation'), default=1)
    sepidar_id = models.BigIntegerField(verbose_name=_('sepidar_id'), unique=True,null=True,blank=True)
    sepidar_code = models.BigIntegerField(verbose_name=_('sepidar_code'), unique=True,null=True,blank=True)
    # trade_transportation_method = models.ForeignKey(TradeTransportationMethod, verbose_name=_('trade_transportation_method'),
    #                                                 on_delete=models.DO_NOTHING, null=True, blank=True)
    trade_transportation_method_json = models.JSONField(_('trade_transportation_method_json'), null=True, blank=True)
    auto_complete = 'title'

    def __str__(self):
        return f'{self.title}'

    class Meta:
        ordering = ['title']


class SaleGroup(AbsBaseModel):
    title = models.CharField(verbose_name=_('title'), max_length=100, unique=True)
    sepidar_id = models.BigIntegerField(verbose_name=_('sepidar_id'), unique=True, null=True, blank=True)
    sepidar_code = models.BigIntegerField(verbose_name=_('sepidar_code'), unique=True, null=True, blank=True)
    auto_complete = 'title'

    def __str__(self):
        return f'{self.title}'

    class Meta:
        ordering = ['title']


class CustomsGroup(AbsBaseModel):
    title = models.CharField(verbose_name=_('title'), max_length=100, unique=True)
    sepidar_id = models.BigIntegerField(verbose_name=_('sepidar_id'), unique=True, null=True, blank=True)
    sepidar_code = models.BigIntegerField(verbose_name=_('sepidar_code'), unique=True, null=True, blank=True)

    def __str__(self):
        return f'{self.title}'

    class Meta:
        ordering = ['title']


class Brand(AbsBaseModel):
    title = models.CharField(verbose_name=_('title'), max_length=100, unique=True)
    sepidar_id = models.BigIntegerField(verbose_name=_('sepidar_id'), unique=True, null=True, blank=True)
    sepidar_code = models.BigIntegerField(verbose_name=_('sepidar_code'), unique=True, null=True, blank=True)

    auto_complete = 'title'

    class Meta:
        ordering = ['title']

    def __str__(self):
        return f'{self.title}'


class ItemPackage(BaseModel):
    weight = models.FloatField(null=True, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return f'{self.title}'

    auto_complete = 'title'
    insert_new = False


class Item(BaseModel):
    print('import item .....')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.extra_data.dl_code = None
        self.extra_data.price = None
        self.extra_data.prices = None
        self.extra_data.bazar_price = None

    BATCH_TYPE = (('box', _('box')), ('rol', _('rol')))
    sku = models.CharField(max_length=10, verbose_name=_('sku'), null=True, blank=True, unique=True)
    sepidar_id_0 = models.BigIntegerField(verbose_name=_('sepidar_id'), null=True, blank=True, unique=True)
    part_number = models.CharField(max_length=350, verbose_name=_('part number'), unique=True)
    brand = models.ForeignKey(Brand, related_name="items", verbose_name=_('brand'), null=True, blank=True
                              ,on_delete=models.DO_NOTHING)
    quality = models.CharField(max_length=100, verbose_name=_('quality'), null=True, blank=True)
    sale_group = models.ForeignKey(SaleGroup, related_name="items", verbose_name=_('sale_group')
                                   , null=True, blank=True,on_delete=models.DO_NOTHING)
    purchase_group = models.ForeignKey(PurchaseGroup, related_name="items", verbose_name=_('purchase_group')
                                       ,on_delete=models.DO_NOTHING)
    customs_group = models.ForeignKey(CustomsGroup, related_name="items", verbose_name=_('customs_group'),
                                      null=True, blank=True,on_delete=models.DO_NOTHING)
    package = models.CharField(max_length=100, verbose_name=_('package'), null=True, blank=True)
    package2 = models.ForeignKey(ItemPackage, on_delete=models.DO_NOTHING, null=True, blank=True)
    batch_type = models.CharField(verbose_name=_('batch type'), choices=BATCH_TYPE, max_length=16, null=True, blank=True)
    batch_count = models.FloatField(verbose_name=_('batch count'), null=True, blank=True)
    count_in_box = models.FloatField(verbose_name=_('count_in_box'), null=True, blank=True)
    count_in_main_box = models.FloatField(verbose_name=_('count_in_main_box'), null=True, blank=True)
    location_in_wh = models.CharField(_('location_in_wh'), max_length=127, null=True, blank=True)
    extra_cost_percentage = models.FloatField(verbose_name=_('extra_cost_percentage'), null=True, blank=True,default=0)
    express_extra_cost_percentage = models.FloatField(verbose_name=_('express_extra_cost_percentage'), null=True, blank=True,default=0)
    air_extra_cost_percentage = models.FloatField(verbose_name=_('air_extra_cost_percentage'), null=True, blank=True,default=0)
    sea_extra_cost_percentage = models.FloatField(verbose_name=_('sea_extra_cost_percentage'), null=True, blank=True,default=5)
    customs_price = models.FloatField(verbose_name=_('customs_price'), null=True, blank=True)
    technical_confirm = models.BooleanField(verbose_name=_('technical_confirm'), default=False)
    price_settings = models.ForeignKey(PriceSettings, verbose_name=_("price_settings"), blank=True, null=True,
                                       on_delete=models.CASCADE)
    is_sea_default = models.BooleanField(verbose_name=_("is_sea_default"), default=False)
    active_main_item = models.BooleanField(default=True, verbose_name=_('active_main_item'))
    parent = models.ForeignKey('self', verbose_name=_('parent_code'), on_delete=models.DO_NOTHING, null=True, blank=True)
    hs = models.ForeignKey(HS, verbose_name=_('hs'), on_delete=models.DO_NOTHING, null=True, blank=True)
    # trade_transportation_method = models.ForeignKey(TradeTransportationMethod, verbose_name=_('trade_transportation_method'),
    #                                                 on_delete=models.DO_NOTHING, null=True, blank=True)
    trade_transportation_method_json = models.JSONField(_('trade_transportation_method_json'), null=True, blank=True)
    site_urls = models.JSONField(default=list, verbose_name='مراجع مشابه', null=True, blank=True)
    item_price_json = models.JSONField(_("item_price_json"), null=True, blank=True)
    objects = BaseManager(is_public=True)

    def get_images(self):
        pass
    
    @staticmethod
    def get_list(text):
        res = Item.objects.filter(pk=text)
        return res

    # @property
    def reserved_count_in_portal(self, wh_code):
        if wh_code == 2:
            pass
        from order.models import Order, OrderOrder
        from factor.models import FactorItem
        exclude_order_rel_ids = Order.objects.filter(item=self, is_wh=True, receipt_in_wh=True, sepidar_wh_code=wh_code, is_deleted=False, factor_items__factor__sepidar_id__isnull=True, cancel=False, is_kasri=False).values_list('id', flat=True)
        order_receipt_in_wh = Order.objects.filter(item=self, is_wh=True, receipt_in_wh=True, sepidar_wh_code=wh_code, is_deleted=False, factor_items__factor__sepidar_id__isnull=True, cancel=False, is_kasri=False).aggregate(reserved_quantity=Sum("quantity")).get("reserved_quantity", 0) or 0
        r = OrderOrder.objects.filter(sepidar_wh_code__isnull=False, sepidar_wh_code=wh_code, item=self, fi__factor__sepidar_id__isnull=True).exclude(order_rel_id__in=exclude_order_rel_ids).aggregate(reserved_quantity=Sum("quantity")).get("reserved_quantity", 0) or 0

        r += order_receipt_in_wh
        if not r or r < 0:
            return 0
        else:
            return r

    @property
    def order_inway(self):
        return DimOrder.order_inway(self.sku)

    @property
    def active_hs(self):
        hs = self.hs
        if hs:
            return hs
        elif self.purchase_group:
            return self.purchase_group.hs
        return hs

    def appearance_or_real_part_number(self, customer):
        try:
            customer_factor_item = self.factor_goods_code.filter(qi__quotation__customer_party_id=customer).first()
            if customer_factor_item:
                return customer_factor_item.part_number_show
            else:
                return self.part_number
        except Exception as e:
            print(e)

    def appearance_or_real_part_number_(self, customer):
        try:
            l = [("", "--------", "selected")]
            for item in self.factor_goods_code.filter(qi__quotation__customer_party_id=customer):
                l.append((item.pk, item.part_number_show, ''))
            return {'list': l}
        except Exception as e:
            ...

    @property
    def supply_locations_(self):
        """ WARN__: this function has massive execution time"""
        year = jdatetime.date.today().year
        res = []
        stock_qty_api = SepidarApiCall.get_stock_quantity([self.sepidar_id_0], year)
        api_res = stock_qty_api.get('res')
        if api_res:
            for name_code, stock_qty in api_res.items():
                if stock_qty:
                    sepidar_wh_name = name_code[0]  # re.search(r'(.*)\(code.*\)', code).group(1)
                    sepidar_wh_code = name_code[1]  # re.search(r'(code: (\d+))', code).group(2)
                    # todo get wh__order from db, show reserve and stock_quantity

                    quantity_sum = self.reserved_count_in_portal(sepidar_wh_code)
                    if stock_qty.is_integer():
                        qty = int(stock_qty)
                        if qty - quantity_sum < 0:
                            res.append((f'wh__{sepidar_wh_code}', f'☑️ {sepidar_wh_name} (کل:{qty:,}) - (آزاد: منفی{int(abs(qty - quantity_sum)):,})', int(qty - quantity_sum)))
                        else:
                            res.append((f'wh__{sepidar_wh_code}', f'☑️ {sepidar_wh_name} (کل:{qty:,}) - (آزاد:{int(qty - quantity_sum):,})', int(qty - quantity_sum)))
                    else:
                        qty = stock_qty
                        res.append((f'wh__{sepidar_wh_code}', f'☑️ {sepidar_wh_name} {stock_qty}'))
            else:
                res.sort(key=lambda x: x[2], reverse=True)
                res = [(x[0], x[1]) for x in res]


        for o in self.order_set.filter(cancel=False, is_wh=False).order_by('-quantity'):
            if o.cancel:
                for oo in o.order_base_items.all():
                    if oo.sepidar_wh_code:
                        res.append(
                            ((f'wh__{oo.sepidar_wh_code}__{o.pk}'), f"رزرو انبار {o.pk} ام ({oo.quantity:0.20g})"))
                    else:
                        remaining_quantity = o.remaining_quantity
                        if remaining_quantity > 0:
                            res.append((str(o.pk),
                                        f"🧺 {o.last_work_flow.current_state_name} {o.pk} ام ({o.final_quantity:0.20g} کل) - (آزاد {remaining_quantity:0.20g})"))
            else:
                remaining_quantity = o.remaining_quantity
                if remaining_quantity > 0:
                    res.append((str(o.pk),
                                f"🧺 {o.last_work_flow.current_state_name} {o.pk} ام (کل {o.final_quantity:0.20g}) - (آزاد {remaining_quantity:0.20g})  🕘 {o.estimate_arrive_at}"))

        return res

    @property
    def sepidar_id(self):
        if self.sepidar_id_0:
            return self.sepidar_id_0
        else:
            try:
                self.sepidar_id_0 = int(select_cquery(f"select itemid from inv.item where code ='{self.sku}'",'sepidar').values[0,0])
                self.save()
                return self.sepidar_id_0
            except:
                ...

    @property
    def weight(self):
        # obj = self.item_weights.order_by('-creator_user__groups__name', '-created_date').first()
        obj = self.item_weights.filter(creator_user__isnull=False).order_by('-editor_user__groups__name', '-created_date').first()
        return obj.weight if obj else None

    @property
    def wh_last_weight(self):
        obj = self.item_weights.filter(Q(creator_user__isnull=False) & Q(creator_user__groups__name='wh_user')).order_by('id').last()
        return obj.weight if obj else None

    @property
    def trade_last_weight(self):
        obj = self.item_weights.filter(Q(creator_user__isnull=False) & Q(creator_user__groups__name='trade_user')).order_by('id').last()
        return obj.weight if obj else None

    @property
    def weight_percentage(self):
        if self.trade_last_weight and self.wh_last_weight is not None:
            difference = self.wh_last_weight - self.trade_last_weight
            difference_average = (difference / self.trade_last_weight) * 100
            res = round(difference_average)
            return abs(res)

    @property
    def weight_obj(self):
        return self.item_weights.order_by('-editor_user__groups__name', '-created_date').first()

    @property
    def price(self):
        if not self.extra_data.price:
            # self.extra_data.price = self.items.filter(sku=self).filter(active=True,inquiry_type_id=1).first()
            self.extra_data.price = self.items.filter(sku=self).filter(active=True, inquiry_type_id__in=[1, 2, 3, 6]).order_by('-last_update_date').first()
        return self.extra_data.price

    @property
    def all_trade_active_price_(self):
        trade_filter = Q(inquiry_type__title__icontains='خارج')
        return [(k.pk, k.inquiry_type.title + " " + self.variant_show(k.variants_json)) for k in self.items.filter(trade_filter, sku=self).filter(active=True)]

    @staticmethod
    def variant_show(json_obj):
        l = []
        for k, v in json_obj.items() if json_obj else []:
            l.append(str(k) + ": " + str(v))
        y = '|'.join(l)
        return f'( {y} )' if y else ''

    @property
    def all_bazar_active_price_(self):
        bazar_filter = Q(inquiry_type__title__icontains='داخل')
        return [(k.pk, k.inquiry_type.title) for k in self.items.filter(bazar_filter, sku=self).filter(active=True)]

    @property
    def all_active_price_(self):
        return [(k.pk, k.inquiry_type.title) for k in self.items.filter(active=True)]

    @property
    def bazar_price(self):
        now = timezone.now()
        last_72_hour = (now - timezone.timedelta(hours=72_000), now)  # 3000 days
        bazar_filter = Q(inquiry_type_id=4) | Q(inquiry_type_id=5)
        if not self.extra_data.bazar_price:
            self.extra_data.bazar_price = self.items.filter(sku=self).filter(bazar_filter, active=True, last_update_date__range=last_72_hour).first()
        return self.extra_data.bazar_price

    def set_price(self, price_id):
        if not self.extra_data.price and not price_id:
            self.extra_data.price = self.items.filter(sku=self).filter(active=True, id=price_id)
        return self.extra_data.price

    @property
    def prices(self):
        if not self.extra_data.prices:
            self.extra_data.prices = self.items.filter(sku=self).filter(active=True)
        return self.extra_data.prices

    @property
    def get_customs_price(self):
        return 0

    @property
    def inquiry_count(self):
        now = timezone.now()
        last_72_hour = (now - timezone.timedelta(hours=72_000), now)  # 3000 days
        bazar_filter = Q(inquiry_type__title__icontains='داخل')
        bazar_inquiry_count = self.items.filter(bazar_filter, active=True, last_update_date__range=last_72_hour).count()

        trade_filter = Q(inquiry_type__title__icontains='خارج')
        trade_inquiry_count = self.items.filter(trade_filter, active=True).count()

        return trade_inquiry_count + bazar_inquiry_count


    def set_extra_data_sepidar(self, customer_code=None):
        self.extra_data.sepidar_data = dict()
        self.extra_data.sepidar_data['customer_code'] = customer_code
        curr_year = BaseData.current_year_ref()
        qry = f"""select s.Title, iss.Quantity
from inv.ItemStockSummary iss
join inv.Stock s on s.StockID = iss.StockRef
where FiscalYearRef={curr_year} and ItemRef ={self.sepidar_id} order by s.code"""
        self.extra_data.sepidar_data['stocks'] = select_cquery(qry, "sepidar")
        self.extra_data.sepidar_data['stocks_sum'] = float(self.extra_data.sepidar_data['stocks'].sum()[1])


        dl_filter = f" and dl.Code={customer_code or -1}"
        qry = """
        select top 5
                docs.Date
                ,docs.NetPriceInBaseCurrency/docs.Quantity as fee
                ,docs.Quantity
                , Convert(nvarchar(20),st.Title) sales_type
        from
        (
        select I.Date,I.Number,I.FiscalYearRef,I.CustomerPartyRef,I.SaleTypeRef, I.CurrencyRef,I.Rate
                ,II.ItemRef, II.Quantity,II.Fee,II.NetPrice,II.NetPriceInBaseCurrency,II.Price,II.PriceInBaseCurrency,II.{doc_type}ItemID itemId
                ,1 as coef,'{doc_type}' as doc_type
        from [SLS].[{doc_type}] as I Join [SLS].[{doc_type}Item] as II on II.{doc_type}Ref = I.{doc_type}Id
        )as docs
        join [SLS].[SaleType] as st on st.SaleTypeId = docs.SaleTypeRef
        join [INV].[Item] as Item on Item.ItemID = docs.ItemRef
        left join [GNR].[Grouping] as g_p on g_p.GroupingID = Item.PurchaseGroupRef
        join [GNR].[Party] as p on p.PartyId = docs.CustomerPartyRef join [ACC].[DL] as dl on dl.DLId = p.DLRef
        join [GNR].[Grouping] as g1 on g1.GroupingID = p.CustomerGroupingRef
        join [FMK].[FiscalYear] as fy on fy.FiscalYearId = docs.FiscalYearRef
        join [GNR].[Currency] as curr on curr.CurrencyID = docs.CurrencyRef
        where 1=1 {dl_filter} 
                  and Item.Code={sku}
        order by docs.Date desc
                    """
        self.extra_data.sepidar_data['customer_invoices'] = select_cquery(
            qry.format(dl_filter=dl_filter,sku=self.sku,doc_type='invoice'),
            "sepidar")
        self.extra_data.sepidar_data['customer_quotations'] = select_cquery(
            qry.format(dl_filter=dl_filter,sku=self.sku,doc_type='quotation'),
            "sepidar")

        dl_filter = f" and dl.Code<>{customer_code or -1}"
        self.extra_data.sepidar_data['other_invoices'] = select_cquery(
            qry.format(dl_filter=dl_filter, sku=self.sku, doc_type='invoice'),
            "sepidar")
        self.extra_data.sepidar_data['other_quotations'] = select_cquery(
            qry.format(dl_filter=dl_filter, sku=self.sku, doc_type='quotation'),
            "sepidar")


        qry = f"""
select min(fee) as min,avg(fee) as mean, max(fee) as max from 
(select II.NetPriceInBaseCurrency/II.Quantity as fee
from SLS.InvoiceItem as II 
join SLS.Invoice as inv on inv.InvoiceId = II.InvoiceRef
join Inv.Item as I on I.ItemID = II.ItemRef
where I.Code = {self.sku} and inv.Date >= DATEADD(DAY,-60,GETDATE())) as inv_items        
        """
        self.extra_data.sepidar_data['mean_price'] = select_cquery(qry,"sepidar")

        if customer_code:
            qry = f"""
    select dl.*,p.* 
    from gnr.Party as p
    join acc.dl as dl on dl.DLId = p.DLRef
    where dl.Code = {customer_code}        
            """
            self.extra_data.sepidar_data['customer'] = select_cquery(qry, "sepidar")
        return self.extra_data.sepidar_data

    def save(self):
        if self.id is None:
            # self.id = int(self.sku) if self.sku else None
            super(Item,self).save()
            from tools.import_data import reset_seq
            reset_seq(self._meta.model)
            self.sku = str(self.id) if self.id else None
            super().save()
        else:
            super(Item, self).save()

        # super(Item,self).save()
        # if self.sku:
        #     obj = self._meta.model.objects.get(sku=self.sku)
        #     obj.update
        #     obj.id = int(obj.sku)
        #
        #     super(Item,self).save()
        #     from tools.import_data import reset_seq
        #     reset_seq(self._meta.model)

    def __str__(self):
        #  only return sku, it's necessary for InquiryResult datatable search
        return f'{self.sku}'

    # def __init__(self):
    #     super().__init__()
    #     self.set_public()

    # def get_items(self):
    #     if self.is_public():
    #         return Item.objects.all()
    #     else:
    #         return Item.objects.filter('')

    @classmethod
    def import_data_from_dw(cls):
        item_list = dw.models.ItemModel.get_items_extra_data()
        print(item_list.__dict__)
        for item in item_list:
            print(item)
            cls.objects.update_or_create(sku=item.sku,part_number=item.title,brand=item.goods_group,quality=1,group_sell=item.sales_group,
                                         group_buy=item.purchase_group,group_customs="",package=item.package)


class ItemRakedManager(models.Manager):
    pass


class ItemRaked(BaseModel):
    goods_code_fk = models.ForeignKey(Item, on_delete=models.DO_NOTHING, related_name='items_raked')
    priority_text = models.CharField(max_length=255, null=True, blank=True)
    last_sale_date_str = models.CharField(max_length=255, null=True, blank=True)

    created_date = None
    last_update_date = None
    creator_user = editor_user = code = title = group = None

    objects = ItemRakedManager()

    def __str__(self):
        from datetime import datetime
        date = ''
        if self.last_sale_date_str:
            year, month, day = map(int, self.last_sale_date_str.split('-'))
            date = to_jalali_date(datetime(year=year, month=month, day=day))
        return f'{self.priority_text} - {date}'


class ItemWeight(AbsBaseModel):
    sku = models.ForeignKey(Item, on_delete=models.DO_NOTHING, verbose_name=_('sku'),related_name="item_weights")
    weight = models.FloatField(verbose_name=_('weight'))

    def __str__(self):
        return f'{self.pk}'


class CustomerGroup(AbsBaseModel):
    title = models.CharField(max_length=100, verbose_name=_('title'), unique=True)
    sepidar_id = models.AutoField(verbose_name=_('sepidar_id'), unique=True, primary_key=True, editable=False)
    sepidar_group_id = models.BigIntegerField(verbose_name=_('sepidar_group_id'), blank=True, null=True, unique=True)
    name = models.CharField(max_length=100, verbose_name=_('name'), null=True, blank=True)
    current_user = models.ForeignKey(get_user_model(), on_delete=models.DO_NOTHING, null=True, blank=True, verbose_name=_('portal_current_user'))

    auto_complete = 'title'

    insert_new = False


class AccountingUser(AbsBaseModel):
    title = models.CharField(max_length=100, verbose_name=_('title'), unique=True)
    sepidar_id = models.BigIntegerField(verbose_name=_('sepidar_id'), unique=True, null=True, blank=True)
    sepidar_group_id = models.BigIntegerField(verbose_name=_('sepidar_group_id'), unique=True, blank=True, null=True)
    name = models.CharField(max_length=100, verbose_name=_('name'), null=True, blank=True)

    # auto_complete = 'title'

    # insert_new = True

    def __str__(self):
        return f'{self.title} - {self.name}'


class Senf(AbsBaseModel):
    title = models.CharField(max_length=100, verbose_name=_('title'), unique=True)

    auto_complete = 'title'
    insert_new = False


class SubSenf(AbsBaseModel):
    title = models.CharField(max_length=100, verbose_name=_('title'), unique=True)

    auto_complete = 'title'


class IntroductionMethod(AbsBaseModel):
    title = models.CharField(max_length=100, verbose_name=_('title'), unique=True)

    auto_complete = 'title'


class Introducer(AbsBaseModel):
    title = models.CharField(max_length=100, verbose_name=_('title'), unique=True)

    auto_complete = 'title'


class Marketer(AbsBaseModel):
    title = models.CharField(max_length=100, verbose_name=_('title'), unique=True)

    auto_complete = 'title'


class Province(AbsBaseModel):
    title = models.CharField(max_length=100, verbose_name=_('title'), unique=True)
    location_id = models.AutoField(verbose_name=_('location_id'), primary_key=True, editable=False)
    sepidar_location_id = models.BigIntegerField(verbose_name=_('sepidar_location_id'), blank=True, null=True, unique=True)

    auto_complete = 'title'
    insert_new = False


CustomerGrade = (
    ("-2,A+,0", _("A+ Cash")),
    ("-1,A,0", _("A Cash")),
    ("0,B,0", _("B Cash")),

    ("-2,A+,1", _("A+ 1 Month")),
    ("-1,A,1", _("A 1 Month")),
    ("0,B,1", _("B 1 Month")),

    ("-2,A+,2", _("A+ 2 Month")),
    ("-1,A,2", _("A 2 Month")),
    ("0,B,2", _("B 2 Month")),

    ("-2,A+,3", _("A+ 3 Month")),
    ("-1,A,3", _("A 3 Month")),
    ("0,B,3", _("B 3 Month")),

    ("-2,A+,4", _("A+ 4 Month")),
    ("-1,A,4", _("A 4 Month")),
    ("0,B,4", _("B 4 Month")),
)
CustomerGrade = (
    ("-3,Special", _("special")),
    ("-2,A+", _("A+")),
    ("-1,A", _("A")),
    ("0,B", _("B")),
    ("0,C", _("C")),
)

CustomerGrade = (
    ("-3,Special", _("special")),
    ("-2,A+", _("A+")),
    ("-1,A", _("A")),
    ("0,B", _("B")),
    ("0,C", _("C")),
)


def uploaded_file_path(instance, filename: str):
    """generate file path for file"""
    name = '_'.join(filename.split(' '))
    name = f"_{name}"
    return os.path.join('uploads/file/customer/', name)


def uploaded_image_path(instance, filename: str):
    """generate file path for image"""
    name = '_'.join(filename.split(' '))
    name = f"_{name}"

    return os.path.join('uploads/icons/customer/', name)


class Ostan(models.Model):
    name = models.CharField(max_length=127)
    amar_code = models.CharField(max_length=50, null=True, blank=True)


class Shahrestan(models.Model):
    name = models.CharField(max_length=127)
    ostan = models.ForeignKey(Ostan, on_delete=models.DO_NOTHING)
    amar_code = models.CharField(max_length=50, null=True, blank=True)


class CustomerAddress(models.Model):
    class AddressType(models.TextChoices):
        ACTIVITY_LOCATION = ("1", "محل فعالیت")
        DELIVER_BILL = ("2", "ارسال صورتحساب")
        DELIVER_ITEM = ("3", "ارسال کالا")
        WH = ("4", "انبار")
        HOUSE = ("5", "منزل")
        OFFICIAL = ("6", "رسمی")
        POSTI = ("7", "پستی")
        OTHER = ("8", "سایر")
    customer = models.ForeignKey('Customer', on_delete=models.DO_NOTHING, to_field='sepidar_party_id')
    location = models.ForeignKey(Province, on_delete=models.DO_NOTHING, null=True, blank=True)
    address = models.TextField()
    zip_code = models.CharField(max_length=10, null=True, blank=True)
    latitude = models.CharField(max_length=128, null=True, blank=True)
    longitude = models.CharField(max_length=128, null=True, blank=True)
    title = models.CharField(max_length=128, null=True, blank=True)
    guid = models.CharField(max_length=128, null=True, blank=True)
    is_main = models.BooleanField(default=False)
    type = models.CharField(max_length=2, choices=AddressType.choices, default=AddressType.OFFICIAL)

    def __str__(self):
        return f'{self.address}'


class CustomerPhone(models.Model):
    class PhoneType(models.TextChoices):
        OFFICE_PHONE = ("1", "تلفن دفتر")
        MOBILE = ("2", "تلفن همراه")
        HOME_PHONE = ("3", "تلفن منزل")
        OTHER_PHONE = ("4", "تلفن سایر")
        OFFICE_FAX = ("5", "دورنگار دفتر")
        HOME_FAX = ("6", "دورنگار منزل")
        OTHER_FAX = ("7", "دورنگار سایر")
    customer = models.ForeignKey('Customer', on_delete=models.DO_NOTHING)
    type = models.CharField(max_length=2, choices=PhoneType.choices, default=PhoneType.OFFICE_PHONE)
    phone = models.CharField(max_length=20)
    is_main = models.BooleanField(default=False)


class Customer(AbsBaseModel):
    RISK_STATUS_CHOICE = (
        ("low risk", "کم ریسک"),
        ("mid risk", "متوسط ریسک"),
        ("high risk", "پر ریسک"),
        ("suspicious", "مشکوک الوصول"),
        ("valid", "معتبر"),
    )
    secret_id = models.CharField(max_length=6, null=True, blank=True, unique=True)
    sepidar_dl_id = models.BigIntegerField(verbose_name=_('sepidar_id'), null=True, blank=True, unique=True)
    sepidar_dl_code = models.BigIntegerField(verbose_name=_('sepidar_code'), null=True, blank=True, unique=True)
    sepidar_party_id = models.BigIntegerField(verbose_name=_('sepidar_party_id'), null=True, blank=True, unique=True)
    # sepidar_sl_ref = models.BigIntegerField(verbose_name=_('sepidar_sl_ref'), null=True, blank=True, unique=True)#delete
    title = models.CharField(max_length=350, verbose_name=_('title'), unique=True)
    type = models.CharField(choices=CustomerType.choices,verbose_name=_("type"), max_length=10, default=CustomerType.Company)
    national_code = models.CharField(max_length=12, verbose_name=_("national_code"), null=True, blank=True)
    name = models.CharField(max_length=150, verbose_name=_("name"), null=True, blank=True)
    last_name = models.CharField(max_length=150, verbose_name=_("last_name"), null=True, blank=True)
    email = models.EmailField(max_length=150, verbose_name=_("email"), null=True, blank=True)
    website = models.URLField(max_length=150, verbose_name=_("website"), null=True, blank=True)
    phone = models.CharField(max_length=50, verbose_name=_("phone"), null=True, blank=True)
    # mobile = models.CharField(max_length=50, verbose_name=_("mobile"), null=True, blank=True)#delete

    credit_with_doc = models.BigIntegerField(verbose_name=_("credit_with_doc"), null=True, blank=True)  # delete
    customer_group = models.ForeignKey(CustomerGroup, on_delete=models.DO_NOTHING, related_name='customers',verbose_name=_("customer_group"), null=True, blank=True)  # delete
    province = models.ForeignKey(Province, on_delete=models.DO_NOTHING, related_name='customers_p',verbose_name=_("province"), null=True, blank=True)
    location = models.ForeignKey(Province, on_delete=models.DO_NOTHING, related_name='customers_l',verbose_name=_("location"), null=True, blank=True)
    address = models.CharField(max_length=400, verbose_name=_("address"), null=True, blank=True)
    senf = models.ForeignKey(Senf, on_delete=models.DO_NOTHING, related_name='customers',verbose_name=_("senf"), null=True, blank=True)
    sub_senf = models.ForeignKey(SubSenf, on_delete=models.DO_NOTHING, related_name='customers',verbose_name=_("sub_senf"), null=True, blank=True)
    introduction_method = models.ForeignKey(IntroductionMethod, on_delete=models.DO_NOTHING, related_name='customers',verbose_name=_("introduction_method"), null=True, blank=True)
    introducer = models.ForeignKey(Introducer, on_delete=models.DO_NOTHING, related_name='customers',verbose_name=_("introducer"), null=True, blank=True)

    revival_date = models.DateField(verbose_name=_("revival_date"), null=True, blank=True)

    # new field
    # ضمانت
    z_no = models.BooleanField(_('Z_no'), default=False)
    z_safte = models.PositiveBigIntegerField(_('Z_safte'), null=True, blank=True)
    z_cheque_s = models.PositiveBigIntegerField(_('Z_cheque_s'), null=True, blank=True)
    z_cheque_ns = models.PositiveBigIntegerField(_('Z_cheque_ns'), default=0, null=True, blank=True)
    z_max_credit_rafi = models.PositiveBigIntegerField(_('Z_max_credit_rafi'), null=True, blank=True)
    # مبلغ زمانت
    extra_credit = models.PositiveBigIntegerField(_('extra_credit'), null=True, blank=True)

    # نوع فاکتور
    i_type1_target = models.PositiveSmallIntegerField(_('Z_credit'), null=True, blank=True, validators=[MaxValueValidator(100)])

    # حد اعتبار
    # مشتریان فعال
    # کارشناس
    marketer = models.ForeignKey(Marketer, on_delete=models.DO_NOTHING, related_name='customers',
                                 verbose_name=_("marketer"), null=True, blank=True)
    accounting_user = models.ForeignKey(AccountingUser, on_delete=models.DO_NOTHING, related_name='customer_accounting',
                                 verbose_name="کاربر مالی", null=True, blank=True)
    # مشتریان بدون قرارداد ( چک هنگام تحویل کالا)
    cheque_to_delivery = models.BooleanField(_('cheque_to_delivery'), default=False)

    # قرارداد
    # contract = models.ForeignKey('CustomerContract', verbose_name=_('contract'), null=True, blank=True,
    #                              on_delete=models.DO_NOTHING)

    # توافق با مشتری
    customer_sale_type = models.ForeignKey('micmod_base.SaleType', on_delete=models.DO_NOTHING,
                                           verbose_name=_('customer_sale_type'), null=True, blank=True)

    # نام رسمی
    official_name = models.CharField(_('official_name'), max_length=255, null=True, blank=True)
    customer_grade = models.CharField(choices=CustomerGrade, max_length=10, null=True, blank=True,
                                      verbose_name=_('customer_grade'), default="-1,A")

    description = models.TextField(_('description'), max_length=1000, null=True, blank=True)
    lat = models.CharField(_('lat'), max_length=100, null=True, blank=True)
    long = models.CharField(_('long'), max_length=100, null=True, blank=True)

    customer_field = models.ManyToManyField('CustomerFields', related_name='customer_rel', verbose_name=_('customer_field'))
    active = models.BooleanField(_('active'), default=True)
    guid = models.UUIDField(_('guid'), default=uuid.uuid4, editable=False)
    # customer_expert = models.CharField(_('customer_expert'), max_length=255, null=True, blank=True)
    # customer_expert_phone_number = models.CharField(_('customer_expert_phone_number'), max_length=50, null=True, blank=True)
    meet_in_person = models.BooleanField(_('meet_in_person'), default=False)
    black_list = models.BooleanField(_('black_list'), default=False)

    # customer_debts = models.CharField(max_length=255, verbose_name=_('customer_debts'), null=True, blank=True)
    risk_status = models.CharField(max_length=32, verbose_name='وضعیت ریسک', choices=RISK_STATUS_CHOICE, null=True, blank=True)
    shop_id = models.BigIntegerField(_('shop_id'), null=True, blank=True, unique=True)

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        if not self.pk:
            for _ in range(10):
                self.secret_id = set_secret_id()
                try:
                    super().save(force_insert=False, force_update=False, using=None, update_fields=None)
                    break
                except IntegrityError as e:
                    print(self.pk, e)
                    continue
        else:
            super().save(force_insert=False, force_update=False, using=None, update_fields=None)


    def get_sepidar_credit(self):
        credit = 'در دسترس نیست'

        qry = f'''select 
            [ReceiptChequeId] as id,
            sum(rc.[amount]) as sum_check,
            rc.[DlRef] as dl_ref
            from RPA.ReceiptCheque rc 
            left join RPA.ReceiptHeader as rh on rc.ReceiptHeaderRef=rh.ReceiptHeaderId where rc.State=1 and rc.[description] like '%%ضم%%' and FiscalYearRef={settings.SEPIDAR_CONST_DATA.get("fiscalyearref")} and rc.DlRef={self.sepidar_dl_id}
            group by rc.DlRef, [ReceiptChequeId]'''

        try:
            credit = Customer.objects.raw(qry, using='sepidar')
            credit = float(credit[0].sum_check)
        except Exception as e:
            credit = 'در دسترس نیست'

        return credit

    @staticmethod
    def get_list(text):
        res = Customer.objects.filter(Q(sepidar_dl_code=text) | Q(shop_id__exact=text))
            # ('default').raw(f"""
        # Select sepidar_dl_code as code, title as name, sepidar_dl_id, * From public.extra_data_customer where sepidar_dl_code='{text}'""")
        return res

    def __str__(self):
        return f'{self.title}'


class CustomerDocuments(AbsBaseModel):
    DOC_CHOICES = (
        ("A", _("id_card")),
        ("B", _("image_meet_in_person")),
        ("C", _("روزنامه رسمی")),
        ("D", _("اساس نامه")),
        ("E", _("آگهی تغییرات")),
        ("F", _("اضهارنامه ثبت تاسیس")),
        ("G", _("چک ضمانت")),
    )
    path = models.FileField(verbose_name=_('file'), upload_to=uploaded_file_path, null=True, blank=True)
    doc_type = models.CharField(_('doc_type'), max_length=1, choices=DOC_CHOICES)
    description = models.TextField(_('description'), null=True, blank=True)
    customer = models.ForeignKey(Customer, verbose_name=_('customer'), on_delete=models.DO_NOTHING)


class CustomerExpert(AbsBaseModel):
    customer = models.ForeignKey(Customer, verbose_name=_('customer'), on_delete=models.DO_NOTHING)
    name = models.CharField(_('name'), max_length=200)
    phone = models.CharField(_('phone'), max_length=20, null=True, blank=True, help_text='09123456789 or 0213456789')
    position = models.CharField(_('position'), max_length=200, null=True, blank=True, help_text='')
    is_main = models.BooleanField(_('is_main'), default=False)


class CustomerContract(AbsBaseModel):
    CONTRACT_TYPE = (
        ("A", _('contract')),
        ("B", _('sorat_jalase')),
        ("C", _('الحاقیه (تمدید) قرارداد')),
    )
    contract_date = models.DateField(_('contract_date'), null=True, blank=True)
    contract_due_date = models.DateField(_('contract_due_date'), null=True, blank=True)
    description = models.TextField(_('description'), max_length=3000)
    contract_type = models.CharField(_('contract_type'), max_length=1, choices=CONTRACT_TYPE)
    customer = models.ForeignKey(Customer, on_delete=models.DO_NOTHING, verbose_name=_('contract'), null=True, blank=True)
    # file = ... generic


class CustomerFields(AbsBaseModel):
    title = models.CharField(_('customer_field'), max_length=255, null=True, blank=True)
    icon = models.FileField(verbose_name=_('image'), upload_to=uploaded_image_path, null=True, blank=True)
    # customer = models.ManyToManyField(Customer)

    def __str__(self):
        return f'{self.title}'


class ChangeCustomerGroup(AbsBaseModel):
    customer = models.ForeignKey(Customer, verbose_name=_('customer'), on_delete=models.DO_NOTHING, related_name='change_marketer_rel')
    from_marketer = models.ForeignKey(CustomerGroup, on_delete=models.DO_NOTHING, related_name='from_marketer_rel',
                                      verbose_name=_("from_marketer"), null=True, blank=True)
    to_marketer = models.ForeignKey(CustomerGroup, on_delete=models.DO_NOTHING, related_name='to_marketer_rel',
                                    verbose_name=_("to_marketer"), null=True, blank=True)


# class CustomerPartNumber(AbsBaseModel):
#     item = models.ForeignKey(Item, on_delete=models.DO_NOTHING, related_name='part_number_appearance', null=True, blank=True)
#     customer = models.ForeignKey(Customer, on_delete=models.DO_NOTHING, related_name='customer_part_number', null=True, blank=True)
#     part_number = models.CharField(max_length=255, verbose_name=_('customer_part_number'))


class WH(BaseModel):
    backend_name = models.CharField(max_length=128, unique=True)
    front_name = models.CharField(max_length=255, unique=True)
    sepidar_wh_code = models.IntegerField(_('sepidar_wh_code'))

    def __str__(self):
        return f'{self.sepidar_wh_code} : {self.backend_name} : {self.front_name}'


class ItemPrice(BaseModel):
    item = models.ForeignKey(Item, on_delete=models.DO_NOTHING, null=True, blank=True)
    air = models.FloatField(null=True, blank=True)
    sea = models.FloatField(null=True, blank=True)
    sepidar_quantity = models.FloatField(null=True, blank=True)
    in_way_count = models.FloatField(null=True, blank=True)
    quantity_json = models.JSONField(null=True, blank=True)
    express = models.FloatField(null=True, blank=True)
    price_update_date = models.DateTimeField(null=True, blank=True)
    is_sea_default = models.BooleanField(_('is_sea_default'), default=False)
    part_number = models.CharField(_('part_number'), max_length=255, default="")
    purchase_group = models.CharField(_('purchase_group'), max_length=255, default="")
    sales_group = models.CharField(_('sales_group'), max_length=255, default="")


class ItemStockSummary(models.Model):
    last_update_date = models.DateTimeField(auto_now=True)
    item = models.ForeignKey(Item, on_delete=models.DO_NOTHING, related_name='stock_summary')
    stockref = models.IntegerField()
    quantity = models.FloatField()
    fiscalyearref = models.IntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['item', 'stockref', 'fiscalyearref'],
                name='unique_item_stockref_fiscalyearref'
            )
        ]

    @classmethod
    def update(cls):
        pass

    @property
    def display_name(self):
        from order.models import Order
        return Order.sepidar_wh_map.get(self.stockref)