from django.contrib.contenttypes.fields import GenericRelation
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.contrib import messages

from accounts.models import User
from core.models import BaseModel, BaseManager, BaseModeWF
from extra_data.models import Item
from micmod_base.base import SLSDoc, DeliveryTime
from micmod_base.models import Quotation, SaleType, QuotationItem
from order.models import Order
from tools.utils import show_error

from translator import get_text as _


class FactorItemManager(BaseManager):
    def get_queryset(self):
        qs = super().get_queryset()
        return qs.order_by('index', 'qi__is_over', 'qi__id')

    def base_qs(self):
        return self.get_queryset().order_by('-index', 'id')


class Factor(SLSDoc):
    q = models.ForeignKey(Quotation, verbose_name=_('q'), related_name='q', on_delete=models.DO_NOTHING)

    delivery_time = models.CharField(choices=DeliveryTime, max_length=10, null=True, blank=True,
                                     verbose_name=_('delivery_time'), default="2-3 week")
    description = models.TextField(max_length=1000, null=True, blank=True, verbose_name=_('description'))
    guid = models.UUIDField(_('guid'), default=None, editable=False, null=True, blank=True)
    # sepidar_quotation_id = models.BigIntegerField(_('sepidar_quotation_id'), null=True, blank=True)
    sepidar_number = models.BigIntegerField(_('sepidar_number'), null=True, blank=True)

    workflows = GenericRelation('workflow.Workflow', related_query_name="model")
    factor_self = models.ForeignKey('self', on_delete=models.DO_NOTHING, related_name='factor_rel', null=True, blank=True)
    self_discount = models.PositiveSmallIntegerField(verbose_name=_('self_discount'), default=0, validators=[MaxValueValidator(100)])
    is_official = models.BooleanField(default=False, verbose_name=_('is_official'))
    official_value = models.FloatField(default=0, verbose_name=_('official_value'), null=True, blank=True)
    cancel = models.BooleanField(default=False, verbose_name=_('cancel'))

    sale_type = models.ForeignKey(SaleType, on_delete=models.DO_NOTHING, related_name='factors')

    @classmethod
    def get_qs_count(cls, user):
        return len(cls.objects.get_access_object(user, q='active', quotation=False))

    # def generate_order_per_factor_item(self):
    #     for fi in self.factoritem_set.all():
    #         order_rel = ''
    #         data_base = {
    #             "order_title": "خودکار توسط سیستم",
    #             "status": "1",
    #             "item": fi.qi.goods_code_fk,
    #             # "customer": fi.qi.quotation.customer_party_id,
    #             # "transportation_method": "",
    #             "production_lead_time": fi.qi.lead_time,
    #             # "trade_commitment_date": "",
    #             # "commitment_date_to_customer": "",
    #             "quantity": fi.quantity,
    #             # "description_sale": "",
    #             # "order_type": "",
    #             # "sales_admin_confirmation": "",
    #             "cancel": False,
    #             "is_over": False,
    #             "qi": fi.qi,
    #         }
    #         data_rel = {
    #             "order_title": "خودکار توسط سیستم",
    #             "status": "1",
    #             "item": fi.qi.goods_code_fk,
    #             # "customer": fi.qi.quotation.customer_party_id,
    #             # "transportation_method": "",
    #             "production_lead_time": fi.qi.lead_time,
    #             # "trade_commitment_date": "",
    #             # "commitment_date_to_customer": "",
    #             "quantity": fi.quantity,
    #             # "description_sale": "",
    #             # "order_type": "",
    #             # "sales_admin_confirmation": "",
    #             "cancel": False,
    #             "is_over": False,
    #             "qi": fi.qi,
    #         }
    #         if fi.supply_locations.remaining_quantity >= fi.quantity:
    #             ...
    #         order_base = Order.create_with_rel(data_base=data_base, data_rel=data_rel)

    @property
    def sum_prices(self):
        fis = self.factoritem_set.all()
        sum_price = 0
        row_price = 0
        for fi in fis:
            price = fi.price
            quantity = fi.quantity
            row_price = price * quantity
        sum_price += row_price
        return sum_price, row_price


class FactorItem(BaseModel):
    supply_locations_choice = ((1, 'انبار'), (2, 'سفارش داخل'), (3, 'س'), (4, ''), (5, ''))
    factor = models.ForeignKey(Factor, on_delete=models.DO_NOTHING, verbose_name=_('factor'))
    qi = models.ForeignKey(QuotationItem, verbose_name=_('qi'), related_name='qi', on_delete=models.DO_NOTHING)
    goods_code = models.ForeignKey(Item, on_delete=models.DO_NOTHING, related_name='factor_goods_code', verbose_name=_('goods_code'), null=True, blank=True)
    part_number_show = models.CharField(max_length=255, verbose_name=_('part_number_show'), null=True, blank=True)
    price = models.FloatField(verbose_name=_('price'), null=True, blank=True)
    index = models.IntegerField(null=True, blank=True, verbose_name=_("index"))
    quantity = models.PositiveBigIntegerField(null=True, blank=True, validators=[MinValueValidator(0)], verbose_name=_("quantity"))
    delivery_time = models.CharField(choices=DeliveryTime, max_length=20, null=True, blank=True,
                                     verbose_name=_('delivery_time'))
    custom_price = models.FloatField(_('custom_price'), null=True, blank=True)
    supply_locations = models.ForeignKey(Order, on_delete=models.DO_NOTHING, related_name='factor_items', null=True, blank=True, verbose_name=_('supply_locations'))
    supply_location = models.CharField(null=True, blank=True, verbose_name=_('supply_location'))
    # supply_locations = models.ManyToManyField(Order, through='FactorOrder',
    #                                             related_name='factor_items', null=True, blank=True,
    #                                             verbose_name=_('supply_locations'))

    objects = FactorItemManager()

    @property
    def is_wh(self):
        try:
            return True if self.supply_locations.local_sepidar_wh_code else False
        except Exception as e:
            return False

    @property
    def is_order(self):
        try:
            return True if not self.supply_locations.local_sepidar_wh_code else False
        except Exception as e:
            return False

    @property
    def select_wh_reserve(self):
        return self.supply_location and str(self.supply_location).startswith('wh__') and len(str(self.supply_location).split('__')) == 3

    @property
    def select_wh_sepidar(self):
        return self.supply_location and str(self.supply_location).startswith('wh__') and len(str(self.supply_location).split('__')) == 2

    @property
    def select_order(self):
        return self.supply_location and not str(self.supply_location).startswith('wh__')

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        if self.quantity == 0 and not self.pk:
            return
        else:
            condition1 = self.is_order and self.select_wh_sepidar
            # condition2 = self.is_wh and (self.supply_location and not self.supply_location.startswith('wh__'))
            condition3 = self.is_wh and self.select_wh_sepidar
            # condition4 = ''
            # condition5 = self.is_order and self.select_wh_reserve
            condition6 = self.is_wh and self.select_order
            condition7 = self.is_order and self.select_order
            # condition8 = self.is_wh and self.select_wh_reserve
            # condition9 = ''
            condition10 = self.pk is None and not self.select_wh_sepidar and not self.select_order
            condition11 = self.pk is None and self.select_wh_sepidar
            # condition12 = self.pk is None and self.select_order # condition7
            condition_list = [condition1, condition3, condition6, condition7, condition10, condition11]
            if self.pk and self.quantity == 0:
                self.is_deleted = True


            # if self.pk is None:
            #     if self.select_wh_sepidar: # str(self.supply_location).startswith('wh__'):
            #         # generate wh order
            #         data_base = {
            #             "order_title": "خودکار توسط سیستم",
            #             "status": "1",
            #             "item": self.qi.goods_code_fk,
            #             "production_lead_time": 10,  # self.qi.lead_time,
            #             "quantity": self.quantity,
            #             "cancel": False,
            #             "is_over": False,
            #             "qi": self.qi,
            #             "local_sepidar_wh_code": int(self.supply_location[4:]),
            #             "creator_user": self.extra_data.request.user,
            #             "editor_user": self.extra_data.request.user,
            #         }
            #         o1 = Order.create_with_rel(data_base)
            #         self.supply_locations = o1
            #         self.supply_location = o1.pk
            #     elif self.supply_location:
            #         # generate order with rel
            #         data_base = {
            #             "order_title": "خودکار توسط سیستم",
            #             "status": "1",
            #             "item": self.qi.goods_code_fk,
            #             "production_lead_time": 5,  # self.qi.lead_time,
            #             "quantity": self.quantity,
            #             "cancel": False,
            #             "is_over": False,
            #             "qi": self.qi,
            #             "creator_user": self.extra_data.request.user,
            #             "editor_user": self.extra_data.request.user,
            #         }
            #         o2 = Order.objects.filter(pk=self.supply_location).first()
            #
            #         o1 = Order.create_with_rel(data_base, o2)
            #         self.supply_locations = o1
            #     elif not self.supply_location:
            #         # generate order independent
            #         data_base = {
            #             "order_title": "خودکار توسط سیستم",
            #             "status": "1",
            #             "item": self.qi.goods_code_fk,
            #             "production_lead_time": 5,  # self.qi.lead_time,
            #             "quantity": self.quantity,
            #             "cancel": False,
            #             "is_over": False,
            #             "qi": self.qi,
            #             "creator_user": self.extra_data.request.user,
            #             "editor_user": self.extra_data.request.user,
            #         }
            #         o1 = Order.create_with_rel(data_base)
            #         self.supply_locations = o1
            if self.pk:
                old = self.__class__.objects.filter(pk=self.pk).first()
            else:
                old = None

            if condition10:
                o1 = Order.create_with_rel(factor_item=self)
                self.supply_locations = o1
                self.supply_location = o1.pk
            elif condition11:
                # generate wh order
                data_base = {
                    "order_title": "رزرو انبار (خودکار توسط سیستم)",
                    "status": "1",
                    "item": self.qi.goods_code_fk,
                    "production_lead_time": 10,  # self.qi.lead_time,
                    "quantity": self.quantity,
                    "cancel": False,
                    "is_over": False,
                    "qi": self.qi,
                    "local_sepidar_wh_code": int(self.supply_location[4:]),
                    "creator_user": self.extra_data.request.user,
                    "editor_user": self.extra_data.request.user,
                }
                o1 = Order.create_with_rel(data_base)
                self.supply_locations = o1
                self.supply_location = o1.pk
            # elif condition12:
            #     self.supply_locations_id = self.supply_location

            elif condition1 or condition3:
                # generate wh order
                data_base = {
                    "order_title": "رزرو انبار (خودکار توسط سیستم)",
                    "status": "1",
                    "item": self.qi.goods_code_fk,
                    "production_lead_time": 10,  # self.qi.lead_time,
                    "quantity": self.quantity,
                    "cancel": False,
                    "is_over": False,
                    "qi": self.qi,
                    "local_sepidar_wh_code": int(self.supply_location[4:]),
                    "creator_user": self.extra_data.request.user,
                    "editor_user": self.extra_data.request.user,
                }
                o1 = Order.create_with_rel(data_base)
                if old and old.supply_locations.local_sepidar_wh_code:
                    old.supply_locations.is_deleted = True
                    old.supply_locations.save()
                self.supply_locations = o1
                self.supply_location = o1.pk

            elif condition6:
                self.supply_locations_id = self.supply_location
                if old:
                    old.supply_locations.is_deleted = True
                    old.supply_locations.save()
            elif condition7:
                self.supply_locations_id = self.supply_location
            elif not any(condition_list):
                if self.supply_locations_id == self.supply_location:
                    pass
                else:
                    self.supply_locations_id = self.supply_location.split('__')[-1]

            super().save(force_insert, force_update, using, update_fields)
            total_quantity = self.qi.total_quantity_in_factor
            if total_quantity >= self.qi.quantity:
                self.qi.is_over = True
                self.qi.save()
            else:
                self.qi.is_over = False
                self.qi.save()

    def total_supply(self):
        s = sum([x.quantity for x in self.supply_locations.order_base_items.all()])
        quantity = self.quantity
        div = quantity - s
        status = True if s == quantity else False
        return s, quantity, status, div

    class Meta:
        ordering = ['id']


class FactorOrder(BaseModeWF):
    fi = models.ForeignKey(FactorItem, on_delete=models.DO_NOTHING, null=True, blank=True)
    order = models.ForeignKey(Order, on_delete=models.DO_NOTHING, null=True, blank=True)
    quantity = models.FloatField(_('quantity'), default=0)