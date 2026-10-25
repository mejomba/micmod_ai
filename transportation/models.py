import asyncio
import json

from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.contrib.contenttypes.fields import GenericForeignKey
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import UniqueConstraint

from core.models import AbsBaseModel, Q, BaseContentType, BaseModel, CHOICE
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
    ("train", _("train")),
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
    ACCESS_TYPE_CHOICE = (('ALL', _('for_all')), ('QUESTION', _('question')))
    title = models.CharField(max_length=100, null=True, unique=True, verbose_name=_('m-title'))
    origin_area = models.CharField(_('origin_area'), max_length=4, choices=ORIGIN_AREA_CHOICE)
    currency_type = models.ForeignKey(Currency, on_delete=models.DO_NOTHING, verbose_name=_('currency_type'))
    fixed_cost = models.FloatField(_('fixed_cost_kg'))
    variable_cost = models.FloatField(_('variable_cost_kg'))
    method = models.CharField(_('method'), choices=CHOICE.trade_transportation_choice, default=CHOICE.SEA)
    access_type = models.CharField(_('access_type'), max_length=32, choices=ACCESS_TYPE_CHOICE, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    is_public = models.BooleanField(default=True)

    def clean(self):
        qs = TradeTransportationMethod.objects.filter(title__iexact=self.title.strip())
        if self.pk:
            qs = qs.exclude(pk=self.pk)

        if qs.exists():
            raise ValidationError({'title': 'این نام قبلاً ثبت شده است (با حروف بزرگ/کوچک متفاوت).'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.title} ({self.get_origin_area_display()}--{self.currency_type.title})'


class TransportationCalender(BaseModel):
    deliver_to_shipping_company_date = models.DateField(null=True, blank=True)
    estimate_start_shipping_date = models.DateField(null=True, blank=True)
    estimate_arrive_date = models.DateField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    arrive_date = models.DateField(null=True, blank=True)
    capacity_kg = models.DecimalField(max_digits=12, decimal_places=2)
    shipment_type = models.CharField(choices=TransportationMethod)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        start = self.estimate_start_shipping_date or '-'
        arrive = self.estimate_arrive_date or '-'
        return f'{self.get_shipment_type_display()} | {start} → {arrive} | {self.capacity_kg} kg'
