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
from datetime import datetime


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
    is_bazar = models.BooleanField(_('is_bazar'), default=False)

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

    def get_sepidar_stock_code_from_selected_supply_location(self):
        sp = self.supply_location.split('__')
        wh_code = sp[1] if len(sp) >= 2 else -1
        return wh_code

    def quantity_for_wh_order(self):
        from sepidar.api_call import SepidarApiCall
        import re
        res = SepidarApiCall.get_stock_quantity([self.goods_code.sepidar_id_0])
        res = res.get('res')
        if res:
            for code, quantity in res.items():
                code = re.search(r'(code: (\d+))', code).group(2)
                wh_code = self.get_sepidar_stock_code_from_selected_supply_location()
                if code == wh_code:
                    return min([int(quantity), int(self.quantity)])
                # if self.pk is None:
                #     if code == wh_code:
                #         return min([int(quantity), int(self.quantity)])
                # elif self.pk:
                #     if code == wh_code:
                #         return min([int(quantity), int(self.quantity)])

    def selected_order(self):
        """
        کدام محل تامینن انتخاب شده است
        """
        unselect = select_order = select_wh = select_bazar = deselect_bazar = None
        if self.is_bazar:
            select_bazar = True
            select_order = select_wh = unselect = False
        elif not self.supply_location:
            unselect = True
            select_order = select_wh = select_bazar = False
        else:
            try:
                if int(self.supply_location) != self.supply_locations.pk:
                    select_order = True
                    unselect = select_wh = select_bazar= False
                else:
                    deselect_bazar = True
            except Exception as e:
                # if self.supply_location.__icontains__('__'):
                select_wh = True
                unselect = select_order = no_change = False

        return unselect, select_order, select_wh, select_bazar, deselect_bazar

    # def unselected_status(self):
    #     """
    #     هیچ محل تامینی انتخاب نشده است
    #     """
    #     return bool(self.supply_location)
    #
    # def selected_order_status(self):
    #     """
    #     سفارش ناقص انتخاب شده است
    #     """
    #     order_id = self.supply_location
    #     order = Order.objects.filter(pk=order_id).first()
    #     return order.remaining_quantity < self.quantity
    #
    # def selected_wh_status(self):
    #     """
    #     سفارش کامل انتخاب شده است
    #     """
    #     try:
    #         selected_order_id = self.supply_location.split('__')
    #         if len(selected_order_id) == 2:
    #             if int(selected_order_id[1]):
    #                 return True
    #         elif len(selected_order_id) == 3:
    #             ...
    #     except Exception as e:
    #         return False
    #     return False

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):

        unselect, select_order, select_wh, select_bazar, deselect_bazar = self.selected_order()
        if self.pk is None:
            if not self.quantity:
                return
            if unselect or select_bazar:
                """ایجاد سفارش کامل"""
                o1 = Order.create_with_rel(factor_item=self)
                self.supply_locations = o1
                self.supply_location = o1.pk
            elif select_order:
                """ایجاد سفارش کامل"""
                """ایجاد سفارش میانی به اندازه ظرفیت سفارش انتخاب شده"""
                o2 = Order.objects.filter(pk=self.supply_location).first()
                o1 = Order.create_with_rel(o2=o2, factor_item=self)
                self.supply_locations = o1
            elif select_wh:
                """ایجاد سفارش کامل"""
                """ایجاد سفارش میانی به اندازه ظرفیت سفارش انتخاب شده به همراه اطلاعات کد انبار"""

                """generate order with quantity min(sepidar_wh_quantity, fi.quantity)"""
                data_base = {
                    "order_title": "رزرو انبار (خودکار توسط سیستم)",
                    # "status": "1",
                    "item": self.qi.goods_code_fk,
                    "production_lead_time": 10,  # self.qi.lead_time,
                    "quantity": self.quantity_for_wh_order(),  # self.quantity,
                    "cancel": False,
                    "is_over": False,
                    "qi": self.qi,
                    "creator_user": self.extra_data.request.user,
                    "editor_user": self.extra_data.request.user,
                    'is_bazar': self.is_bazar,
                    'is_wh': True
                }
                o1_as_o2 = Order.create_with_rel(data_base=data_base)
                o1 = Order.create_with_rel(o2=o1_as_o2, factor_item=self, sepidar_wh_code=int(self.supply_location[4:]))
                self.supply_locations = o1
        elif self.pk:
            if not self.quantity:
                self.is_deleted = True
                for oo in self.supply_locations.order_base_items.all():
                    oo.delete()
                self.supply_locations.is_deleted = True
                self.supply_locations.save()
                super().save(force_insert, force_update, using, update_fields)
                total_quantity, total_quantity_wh = self.qi.total_quantity_in_factor
                if total_quantity >= self.qi.quantity:
                    self.qi.is_over = True
                else:
                    self.qi.is_over = False
                self.qi.save()
                return

            if select_bazar:
                """حذف سفارش هایی میانی و تبدیل سفارش به نوع بازار"""
                for oo in self.supply_locations.order_base_items.all():
                    oo.delete()
                self.supply_locations.cancel = False
                self.supply_locations.is_bazar = True
                self.supply_locations.save()

            elif unselect:
                pass
            elif deselect_bazar:
                self.supply_locations.is_bazar = False
                self.supply_locations.save()

            elif select_order:
                """بروز سفارش کامل"""
                """ایجاد سفارش میانی به اندازه ظرفیت سفارش انتخاب شده"""
                o2 = Order.objects.filter(pk=self.supply_location).first()
                o1 = Order.create_with_rel(o2=o2, factor_item=self)
                # self.supply_locations = o1
            elif select_wh:
                pass

        super().save(force_insert, force_update, using, update_fields)
        total_quantity, total_quantity_wh = self.qi.total_quantity_in_factor
        if total_quantity >= self.qi.quantity:
            self.qi.is_over = True
        else:
            self.qi.is_over = False
        self.qi.save()

        # condition1 = self.is_order and self.select_wh_sepidar
        # condition3 = self.is_wh and self.select_wh_sepidar
        # condition6 = self.is_wh and self.select_order
        # condition7 = self.is_order and self.select_order
        # condition10 = self.pk is None and not self.select_wh_sepidar and not self.select_order
        # condition11 = self.pk is None and self.select_wh_sepidar
        # condition12 = self.pk is None and self.select_order
        # condition_list = [condition1, condition3, condition6, condition7, condition10, condition11, condition12]
        # old = self.__class__.objects.filter(pk=self.pk).first()
        #
        # if not any(condition_list):
        #     if self.supply_locations_id == self.supply_location:
        #         pass
        #     else:
        #         self.supply_locations_id = self.supply_location.split('__')[-1]
        #
        # if not self.pk:
        #     if self.quantity == 0:
        #         return
        #     if condition10:
        #         o1 = Order.create_with_rel(factor_item=self)
        #         self.supply_locations = o1
        #         self.supply_location = o1.pk
        #     if condition12:
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
        #             "is_bazar": self.is_bazar
        #         }
        #         o2 = Order.objects.filter(pk=self.supply_location).first()
        #
        #         o1 = Order.create_with_rel(data_base, o2)
        #         self.supply_locations = o1
        #
        #     elif condition11:
        #         # generate wh order
        #         data_base = {
        #             "order_title": "رزرو انبار (خودکار توسط سیستم)",
        #             "status": "1",
        #             "item": self.qi.goods_code_fk,
        #             "production_lead_time": 10,  # self.qi.lead_time,
        #             "quantity": self.quantity_for_wh_order(),  #self.quantity,
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
        #
        # else:
        #     if self.quantity == 0:
        #         self.is_deleted = True
        #         self.supply_location = self.supply_locations.pk
        #         if self.is_wh:
        #             self.supply_locations.is_deleted = True
        #             self.supply_locations.save()
        #         super().save(force_insert, force_update, using, update_fields)
        #         self.qi.is_over = False
        #         self.qi.save()
        #         return
        #
        #     elif condition1 or condition3:
        #         # generate wh order
        #         data_base = {
        #             "order_title": "رزرو انبار (خودکار توسط سیستم)",
        #             "status": "1",
        #             "item": self.qi.goods_code_fk,
        #             "production_lead_time": 10,  # self.qi.lead_time,
        #             "quantity": self.quantity_for_wh_order(),  # self.quantity,
        #             "cancel": False,
        #             "is_over": False,
        #             "qi": self.qi,
        #             "local_sepidar_wh_code": int(self.supply_location[4:]),
        #             "creator_user": self.extra_data.request.user,
        #             "editor_user": self.extra_data.request.user,
        #         }
        #         o1 = Order.create_with_rel(data_base)
        #         if old and old.supply_locations.local_sepidar_wh_code:
        #             old.supply_locations.is_deleted = True
        #             old.supply_locations.save()
        #         self.supply_locations = o1
        #         self.supply_location = o1.pk
        #
        #     elif condition6:
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
        #             "is_bazar": self.is_bazar
        #         }
        #         o2 = Order.objects.filter(pk=self.supply_location).first()
        #
        #         o1 = Order.create_with_rel(data_base, o2)
        #         self.supply_locations = o1
        #         # self.supply_locations_id = self.supply_location
        #         if old:
        #             old.supply_locations.is_deleted = True
        #             old.supply_locations.save()
        #
        #     elif condition7:
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
        #             "is_bazar": self.is_bazar
        #         }
        #         o2 = Order.objects.filter(pk=self.supply_location).first()
        #
        #         o1 = Order.create_with_rel(data_base, o2)
        #         self.supply_locations = o1
        #
        # if not any(condition_list):
        #     if self.supply_locations_id == self.supply_location:
        #         pass
        #     else:
        #         self.supply_locations_id = self.supply_location.split('__')[-1]
        #
        # super().save(force_insert, force_update, using, update_fields)
        # total_quantity, total_quantity_wh = self.qi.total_quantity_in_factor
        # if total_quantity >= self.qi.quantity:
        #     self.qi.is_over = True
        #     self.qi.save()

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