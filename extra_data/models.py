import uuid

from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone
import os

from django.utils.safestring import mark_safe

import dw.models
from micmod_base.base import BaseModel
from core.models import BaseManager, AbsBaseModel
from django.apps import apps

from sepidar.models import APILogs, Item as sepidarItem
from sepidar.scripts.sepidar_classes import Urls
from translator import get_text as _
from sepidar.models import BaseData
from tools.form_tools import select_cquery
from django.core.validators import MaxValueValidator
from queryable_properties.properties import queryable_property


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
                return line.get(currency.title_en.lower(),line.get('rial_percentage'))
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
    is_sea_default = models.BooleanField(verbose_name=_("is_sea_default"), default=False)
    active_main_item = models.BooleanField(default=True, verbose_name=_('active_main_item'))
    parent = models.ForeignKey('self', verbose_name=_('parent_code'), on_delete=models.DO_NOTHING, null=True, blank=True)
    hs = models.ForeignKey(HS, verbose_name=_('hs'), on_delete=models.DO_NOTHING, null=True, blank=True)
    objects = BaseManager(is_public=True)

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
            # customer = self.quotation.customer_party_id
            customer_factor_item = self.factor_goods_code.filter(qi__quotation__customer_party_id=customer).first()
            #customer_part_number = self.qi.all().first() #CustomerPartNumber.objects.filter(customer=customer, item=item).order_by('id').last()
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

    # base_fields = ['sku','part_number']

    @property
    def supply_locations_(self):
        # res = [('', '-----------')]
        res = []
        stock_qty_qry = sepidarItem.get_stock_qty(self.sku)
        for stock_qty in stock_qty_qry:
            if stock_qty.quantity:
                sepidar_wh_code = 1000
                sepidar_wh_name = 'اسم انبار سپیدار'
                # wh = WH.objects.get(sepidar_wh_code=1)  # stock_qty.wh_code
                # todo get wh__order from db, show reserve and stock_quantity
                quantity_sum = self.factor_goods_code.filter(supply_location__startswith=f'wh__{sepidar_wh_code}').aggregate(
                    total_sum=Sum('quantity'))['total_sum'] or 0
                if stock_qty.quantity.is_integer():
                    qty = int(stock_qty.quantity)
                    res.append((f'wh__{sepidar_wh_code}', f'{sepidar_wh_name} {qty} / {qty - quantity_sum}'))
                else:
                    qty = stock_qty.quantity
                    res.append((f'wh__{sepidar_wh_code}', f'{sepidar_wh_name} {stock_qty.quantity}'))


        # for o in self.orderitem_set.all():
        for o in self.order_set.filter(cancel=False).order_by('-quantity'):
            remaining_quantity = o.remaining_quantity
            if remaining_quantity > 0:
                if o.local_sepidar_wh_code:
                    res.append(((f'wh__{o.local_sepidar_wh_code}__{o.pk}'), f"رزرو انبار {o.pk} ام ({o.quantity:0.20g})"))
                else:
                    res.append((str(o.pk), f"سفارش در راه {o.pk} ام ({o.quantity:0.20g} از {remaining_quantity:0.20g})"))

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
        obj = self.item_weights.filter(creator_user__isnull=False).order_by('-creator_user__groups__name', '-created_date').first()
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
        return self.item_weights.order_by('-creator_user__groups__name', '-created_date').first()

    @property
    def price(self):
        if not self.extra_data.price:
            # self.extra_data.price = self.items.filter(sku=self).filter(active=True,inquiry_type_id=1).first()
            self.extra_data.price = self.items.filter(sku=self).filter(active=True, inquiry_type_id__in=[1, 2, 3, 6]).order_by('-last_update_date').first()
        return self.extra_data.price

    @property
    def all_trade_active_price_(self):
        trade_filter = Q(inquiry_type__title__icontains='خارج')
        return [(k.pk, k.inquiry_type.title) for k in self.items.filter(trade_filter, sku=self).filter(active=True)]

    @property
    def all_bazar_active_price_(self):
        bazar_filter = Q(inquiry_type__title__icontains='داخل')
        return [(k.pk, k.inquiry_type.title) for k in self.items.filter(bazar_filter, sku=self).filter(active=True)]

    @property
    def all_active_price_(self):
        return [(k.pk, k.inquiry_type.title) for k in self.items.filter(active=True)]

    @property
    def bazar_price(self):
        bazar_filter = Q(inquiry_type_id=4) | Q(inquiry_type_id=5)
        if not self.extra_data.bazar_price:
            self.extra_data.bazar_price = self.items.filter(sku=self).filter(bazar_filter, active=True).first()
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
        bazar_filter = Q(inquiry_type__title__icontains='داخل')
        bazar_inquiry_count = self.items.filter(bazar_filter, active=True).count()

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
            self.id = self.sku
            super(Item,self).save()
            from tools.import_data import reset_seq
            reset_seq(self._meta.model)
            self.sku = self.id
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


class ItemWeight(AbsBaseModel):
    sku = models.ForeignKey(Item, on_delete=models.DO_NOTHING, verbose_name=_('sku'),related_name="item_weights")
    weight = models.FloatField(verbose_name=_('weight'))

    def __str__(self):
        return f'{self.sku}'


class CustomerGroup(AbsBaseModel):
    title = models.CharField(max_length=100, verbose_name=_('title'), unique=True)
    sepidar_id = models.AutoField(verbose_name=_('sepidar_id'), unique=True, primary_key=True, editable=False)
    sepidar_group_id = models.BigIntegerField(verbose_name=_('sepidar_group_id'), blank=True, null=True, unique=True)

    auto_complete = 'title'


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


class Customer(AbsBaseModel):
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
    z_cheque_ns = models.PositiveBigIntegerField(_('Z_cheque_ns'), default=False, null=True, blank=True)
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

    @staticmethod
    def get_list(text):
        res = Customer.objects.filter(sepidar_dl_code=text)
            # ('default').raw(f"""
        # Select sepidar_dl_code as code, title as name, sepidar_dl_id, * From public.extra_data_customer where sepidar_dl_code='{text}'""")
        return res

    def __str__(self):
        return f'{self.title}'


class CustomerDocuments(AbsBaseModel):
    DOC_CHOICES = (
        ("A", _("id_card")),
        ("B", _("image_meet_in_person")),
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