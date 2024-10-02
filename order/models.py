from django.db import models
from core.models import BaseModel, BaseModeWF
from extra_data.models import Brand, Item, Customer, WH
from micmod_base.models import Quotation
from translator import get_text as _


class Order(BaseModeWF):
    ORDER_STATUS = [('1', _("draft")), ('2', _("started")), ('3', _("co-conf")), ('4', _("supp-sent")), ('5', _("sup-conf")),
                    ('6', _("pre-paid")), ('7', _("gio")), ('8', _("has-packing")), ('9', _("partial-arrived")),
                    ('10', _("total-arrived")), ('11', _("has-error")), ('12', _("completed")), ('13', _("canceled")), ]
    TRANSPORTATION_CHOICE = [("express", _("express")), ("air", _("air")), ("sea", _("sea")), ]
    ORDER_TYPE_CHOICE = [("china", _("china")), ("hong-kong", _("hong-kong")), ]
    order_title = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=2, verbose_name=_('status'), default=1, choices=ORDER_STATUS)
    item = models.ForeignKey(Item, on_delete=models.DO_NOTHING, null=True)
    customer = models.ForeignKey(Customer, verbose_name=_('customer'), on_delete=models.DO_NOTHING,
                                 to_field='sepidar_party_id', db_column='customer_party_id')
    # fi = models.ForeignKey(_('fi'), FactorItem, on_delete=models.DO_NOTHING)
    transportation_method = models.CharField(_('transportation_method'), max_length=64, choices=TRANSPORTATION_CHOICE,
                                             default='sea')
    production_lead_time = models.PositiveSmallIntegerField(_('production_lead_time'), null=True, blank=True)
    trade_commitment_date = models.DateField(_('trade_commitment_date'), null=True, blank=True)
    commitment_date_to_customer = models.DateField(_('commitment_date_to_customer'), null=True, blank=True)
    quantity = models.FloatField(_('quantity'), default=0)
    description_sale = models.TextField(_('description_sale'), null=True, blank=True)
    order_type = models.CharField(_('order_type'), max_length=64, choices=ORDER_TYPE_CHOICE, default='china',
                                  null=True, blank=True)
    sales_admin_confirmation = models.BooleanField(_("sales_admin_confirmation"), default=False)
    cancel = models.BooleanField(_("cancel"), default=False)
    is_over = models.BooleanField(_('is_over'), default=False)
    qi = models.ForeignKey(Quotation, on_delete=models.DO_NOTHING, null=True)

    order_m2m = models.ManyToManyField('self', through='OrderOrder', related_name='order_items',
                                       null=True, blank=True, verbose_name=_('OrderOrder'))

    @classmethod
    def get_qs_count(cls, user):
        return 0

    @classmethod
    def create_with_rel(cls, data, order_rel):
        o = cls.objects.create(**data)
        oo = OrderOrder.objects.create(order_base=o, order_rel=order_rel, quantity=o.quantity)

    @property
    def remaining_quantity(self):
        total_needed_count = 0
        total_count = self.quantity
        if self.cancel:
            total_count = 0
            for oo in self.order_m2m.all():
                total_count += oo.quantity

        for fi in self.factor_items.all():
            total_needed_count += fi.quantity
        return total_count - total_needed_count


class OrderOrder(BaseModel):
    STATUS_CHOICES = [("-1", _("wh__central__1")), ("-2", _("wh__resalat__1")),
                      ("-3", _("wh__res_chavoshi__1")), ("-4", _("wh__res_chavoshi__2")),
                      ("-5", _("wh__res_moradi__1",)), ]
    order_base = models.ForeignKey(Order, on_delete=models.DO_NOTHING, related_name='order_base_items', null=True, blank=True)
    order_rel = models.ForeignKey(Order, on_delete=models.DO_NOTHING, related_name='order_rel_items', null=True, blank=True)
    quantity = models.FloatField(_('quantity'), null=True, blank=True)
    local_sepidar_wh = models.ForeignKey(WH, on_delete=models.DO_NOTHING, null=True, blank=True)
