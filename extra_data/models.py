from django.db import models

import dw.models
import inquiry.models
from micmod_base.base import BaseModel
from core.models import BaseManager, AbsBaseModel
from django.apps import apps

from sepidar.models import APILogs
from sepidar.scripts.sepidar_classes import Urls
from translator import get_text as _


class DiscountBasedPriceType(models.TextChoices):
    RInv = "0", _("calculate_in_invoice_row")
    SKU = "1", _("calculate_in_sku")


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
    free_rmb_rate_new_order = models.FloatField(verbose_name=_('free_rmb_rate'), default=74000)
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
        return self.discount_based_price[-2]['percentage']

    def get_discount_based_customer(self, grade):
        for line in self.discount_based_customer:
            if grade == line['title']:
                return line['percentage']
        return 0

    def get_discount_based_payment_method(self, payment_method, currency):
        for line in self.discount_based_payment_method:
            if payment_method == line['title']:
                return line.get(currency.title_en.lower(),line.get('rial_percentage'))
        return 0


class HS(AbsBaseModel):
    code = models.CharField(verbose_name=_('code'),max_length=8,unique=True)
    title = models.CharField(verbose_name=_('title'),max_length=200,unique=True)
    price_settings = models.ForeignKey(PriceSettings, verbose_name=_("price_settings"), blank=True, null=True,
                                       on_delete=models.CASCADE)
    customs_rate = models.FloatField(verbose_name=_('customs_rate'), default=4)

    def __str__(self):
        return f'{self.title} ({self.customs_rate}%)'

    class Meta:
        ordering = ['title']


class PurchaseGroup(AbsBaseModel):
    title = models.CharField(verbose_name=_('title'), max_length=100, unique=True)
    price_settings = models.ForeignKey(PriceSettings,verbose_name=_("price_settings"), blank=True, null=True, on_delete=models.CASCADE)
    hs = models.ForeignKey(HS, verbose_name=_("hs"), on_delete=models.DO_NOTHING,null=True,blank=True)
    sea_transportation = models.FloatField(verbose_name=_('customs_rate'), default=1)
    air_transportation = models.FloatField(verbose_name=_('customs_rate'), default=1)
    express_transportation = models.FloatField(verbose_name=_('customs_rate'), default=1)
    sepidar_id = models.BigIntegerField(verbose_name=_('sepidar_id'), unique=True,null=True,blank=True)
    sepidar_code = models.BigIntegerField(verbose_name=_('sepidar_code'), unique=True,null=True,blank=True)
    auto_complete = 'title'

    def __str__(self):
        return f'{self.title}'

    class Meta:
        ordering = ['title']


class SaleGroup(AbsBaseModel):
    title = models.CharField(verbose_name=_('title'), max_length=100, unique=True)
    sepidar_id = models.BigIntegerField(verbose_name=_('sepidar_id'), unique=True, null=True, blank=True)
    sepidar_code = models.BigIntegerField(verbose_name=_('sepidar_code'), unique=True, null=True, blank=True)

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
    title = models.CharField(verbose_name=_('title'), max_length=50, unique=True)
    sepidar_id = models.BigIntegerField(verbose_name=_('sepidar_id'), unique=True, null=True, blank=True)
    sepidar_code = models.BigIntegerField(verbose_name=_('sepidar_code'), unique=True, null=True, blank=True)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return f'{self.title}'


class Item(BaseModel):
    BATCH_TYPE = (('box', _('box')), ('rol', _('rol')))
    sku = models.CharField(max_length=10, verbose_name=_('sku'), null=True, blank=True, unique=True)
    sepidar_id = models.BigIntegerField(verbose_name=_('sepidar_id'), null=True, blank=True, unique=True)
    part_number = models.CharField(max_length=150, verbose_name=_('part number'), unique=True)
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
    batch_type = models.CharField(verbose_name=_('batch type'), choices=BATCH_TYPE, max_length=16, null=True, blank=True)
    batch_count = models.FloatField(verbose_name=_('batch count'), null=True, blank=True)
    extra_cost_percentage = models.FloatField(verbose_name=_('extra_cost_percentage'), null=True, blank=True,default=0)
    express_extra_cost_percentage = models.FloatField(verbose_name=_('express_extra_cost_percentage'), null=True, blank=True,default=0)
    air_extra_cost_percentage = models.FloatField(verbose_name=_('air_extra_cost_percentage'), null=True, blank=True,default=0)
    sea_extra_cost_percentage = models.FloatField(verbose_name=_('sea_extra_cost_percentage'), null=True, blank=True,default=7)
    customs_price = models.FloatField(verbose_name=_('customs_price'), null=True, blank=True)
    technical_confirm = models.BooleanField(verbose_name=_('technical_confirm'), default=False)
    price_settings = models.ForeignKey(PriceSettings, verbose_name=_("price_settings"), blank=True, null=True,
                                       on_delete=models.CASCADE)
    objects = BaseManager(is_public=True)

    @property
    def sepidar_stock(self):
        if self.sepidar_id:
            return  APILogs.new_call(Urls.item_inventories.url.format(self.sepidar_id))[1]
        return dict()

    @property
    def price(self):
        return self.items.filter(sku=self).filter(active=True).first()

    @property
    def get_customs_price(self):
        return 0

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


class ItemWeight(AbsBaseModel):
    sku = models.ForeignKey(Item, on_delete=models.DO_NOTHING, verbose_name=_('sku'),related_name="item_weights")
    weight = models.FloatField(verbose_name=_('weight'))

    def __str__(self):
        return f'{self.sku}'

