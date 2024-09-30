from django.db import models
from core.models import BaseModel, BaseModeWF
from extra_data.models import Brand, Item, Customer
# from factor.models import FactorItem
from translator import get_text as _


class Order(BaseModeWF):
    ORDER_STATUS = [(1, _("draft")), (2, _("started")), (3, _("co-conf")), (4, _("supp-sent")), (5, _("sup-conf")),
                    (6, _("pre-paid")), (7, _("gio")), (8, _("has-packing")), (9, _("partial-arrived")),
                    (10, _("total-arrived")), (11, _("has-error")), (12, _("completed")), (13, _("canceled")), ]
    TRANSPORTATION_CHOICE = [("express", _("express")), ("air", _("air")), ("sea", _("sea")), ]
    ORDER_TYPE_CHOICE = [("china", _("china")), ("hong-kong", _("hong-kong")), ]
    title = models.CharField(max_length=255, blank=True, null=True)
    status = models.PositiveSmallIntegerField(verbose_name=_('status'), choices=ORDER_STATUS, default=1)
    item = models.ForeignKey(Item, on_delete=models.DO_NOTHING, null=True)
    customer = models.ForeignKey(Customer, verbose_name=_('customer'), on_delete=models.DO_NOTHING)
    # fi = models.ForeignKey(_('fi'), FactorItem, on_delete=models.DO_NOTHING)
    transportation_method = models.CharField(_('transportation_method'), max_length=64, choices=TRANSPORTATION_CHOICE, default='sea')
    production_lead_time = models.PositiveSmallIntegerField(_('production_lead_time'), null=True, blank=True)
    trade_commitment_date = models.DateField(_('trade_commitment_date'), null=True, blank=True)
    commitment_date_to_customer = models.DateField(_('commitment_date_to_customer'), null=True, blank=True)
    quantity = models.FloatField(_('quantity'), default=0)
    description_sale = models.TextField(_('description_sale'), null=True, blank=True)
    order_type = models.CharField(_('order_type'), max_length=64, choices=ORDER_TYPE_CHOICE, default='china', null=True, blank=True)
    sales_admin_confirmation = models.BooleanField(_("sales_admin_confirmation"), default=False)
    cancel = models.BooleanField(_("cancel"), default=False)
    is_over = models.BooleanField(_('is_over'), default=False)


# class OrderItem(BaseModel):
#     order = models.ForeignKey(Order, on_delete=models.DO_NOTHING, related_name='order_items')
#     quantity = models.FloatField(blank=True, null=True)
#     item = models.ForeignKey(Item, on_delete=models.DO_NOTHING, null=True)
#     price = models.FloatField(null=True, blank=True)
#     factor_item = models.ForeignKey(FactorItem, on_delete=models.DO_NOTHING)

    # fields
    # QUALITY_CHOICES = (('l', 'Low'), ('m', 'Medium'), ('h', 'high'))

    # name = models.CharField(max_length=255, blank=True, null=True)
    # price = models.FloatField(blank=True, null=True)
    # brands = models.ForeignKey(Brand, on_delete=models.DO_NOTHING, related_name='brands')
    # type = models.CharField(max_length=255, blank=True, null=True)
    # quality = models.CharField(max_length=255, choices=QUALITY_CHOICES, blank=True, null=True)

