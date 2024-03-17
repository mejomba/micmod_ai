import asyncio
import json

from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db import models
from core.models import AbsBaseModel, Q, BaseContentType,BaseModel
from accounts.models import User
from translator import get_text as _
from django.template.loader import render_to_string
from django.contrib.contenttypes.models import ContentType
# Create your models here.


class Packing(AbsBaseModel):
    pl_number = models.CharField(_('pl_number'), max_length=30, unique=True)
    orders_accept_until = models.DateField(_('orders_accept_until'))
    payments_until = models.DateField(_('payments_until'))
    deliver_to_mac_until = models.DateField(_('deliver_to_mac_until'))
    deliver_to_transportation_company_at = models.DateField(_('deliver_to_transportation_company_at'))
    transportation_at = models.DateField(_('transportation_at'))
    deliver_to_customs_at = models.DateField(_('deliver_to_customs_at'))
    clearance_until = models.DateField(_('clearance_until'))
    descriptions = models.TextField(_('descriptions'), max_length=2000, null=True, blank=True)

    field_groups = [
        {'fields': ['pl_number'], 'css_class':'row row-cols-4'},
        {'fields': ['orders_accept_until','payments_until','deliver_to_mac_until','deliver_to_transportation_company_at',
                    'transportation_at','deliver_to_customs_at','clearance_until'], 'css_class':'row row-cols-4'},
        {'fields': ['descriptions'], 'css_class': 'row row-cols-1'},
    ]
