import asyncio
import json

from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db import models
from core.models import AbsBaseModel, Q, BaseContentType,BaseModel
from accounts.models import User
from micmod_base.base import Currency
from translator import get_text as _
from django.template.loader import render_to_string
from django.contrib.contenttypes.models import ContentType
# Create your models here.

TransportationMethod = (
    ("express", _("express")),
    ("air", _("air")),
    ("sea", _("sea")),
)


class Packing(AbsBaseModel):
    pl_number = models.CharField(_('pl_number'), max_length=30, unique=True)
    transportation_method = models.CharField(_('transportation_method'), choices=TransportationMethod, default='air', max_length=20,)
    orders_accept_until = models.DateField(_('orders_accept_until'))
    payments_until = models.DateField(_('payments_until'))
    deliver_to_mac_until = models.DateField(_('deliver_to_mac_until'))
    deliver_to_transportation_company_at = models.DateField(_('deliver_to_transportation_company_at'))
    transportation_at = models.DateField(_('transportation_at'))
    deliver_to_customs_at = models.DateField(_('deliver_to_customs_at'))
    clearance_until = models.DateField(_('clearance_until'))
    descriptions = models.TextField(_('descriptions'), max_length=2000, null=True, blank=True)

    field_groups = [
        {'fields': ['pl_number', 'transportation_method'], 'css_class':'row row-cols-4'},
        {'fields': ['orders_accept_until','payments_until','deliver_to_mac_until','deliver_to_transportation_company_at',
                    'transportation_at','deliver_to_customs_at','clearance_until'], 'css_class':'row row-cols-4'},
        {'fields': ['descriptions'], 'css_class': 'row row-cols-1'},
    ]


class TradeTransportationMethod(BaseModel):
    ORIGIN_AREA_CHOICE = (('CHN', 'china'), ('HNG', 'hong-kong'))
    origin_area = models.CharField(_('origin_area'), max_length=4)
    currency_type = models.ForeignKey(Currency, on_delete=models.DO_NOTHING, verbose_name=_('currency_type'))
    fixed_cost = models.FloatField(_('fixed_cost_kg'))
    variable_cost = models.FloatField(_('variable_cost_kg'))

