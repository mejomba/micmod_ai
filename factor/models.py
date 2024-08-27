from django.contrib.contenttypes.fields import GenericRelation
from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models import Q

from accounts.models import User
from core.models import BaseModel, BaseManager
from extra_data.models import Item
from micmod_base.base import SLSDoc, DeliveryTime
from micmod_base.models import Quotation, SaleType, QuotationItem
from order.models import Order
from tools.utils import show_error

from translator import get_text as _


class FactorManager(BaseManager):
    def get_queryset(self):
        qs = super().get_queryset()
        return qs.order_by('id')


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


class FactorItem(BaseModel):
    supply_locations_choice = ((1, 'انبار'), (2, 'سفارش داخل'), (3, 'س'), (4, ''), (5, ''))
    factor = models.ForeignKey(Factor, on_delete=models.DO_NOTHING, verbose_name=_('factor'))
    qi = models.ForeignKey(QuotationItem, verbose_name=_('qi'), related_name='qi', on_delete=models.DO_NOTHING)
    goods_code = models.ForeignKey(Item, on_delete=models.DO_NOTHING, related_name='factor_goods_code', verbose_name=_('goods_code'), null=True, blank=True)
    part_number_show = models.CharField(max_length=255, verbose_name=_('part_number_show'), null=True, blank=True)
    price = models.FloatField(verbose_name=_('price'), null=True, blank=True)
    index = models.IntegerField(null=True, blank=True, verbose_name=_("index"))
    quantity = models.BigIntegerField(null=True, blank=True, verbose_name=_("quantity"))
    delivery_time = models.CharField(choices=DeliveryTime, max_length=20, null=True, blank=True,
                                     verbose_name=_('delivery_time'))
    custom_price = models.FloatField(_('custom_price'), null=True, blank=True)
    supply_locations = models.ForeignKey(Order, on_delete=models.DO_NOTHING, related_name='factor_items', null=True, blank=True, verbose_name=_('supply_locations'))

    objects = FactorManager()


    class Meta:
        ordering = ['id']

