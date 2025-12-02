from django.db import models

from core.models import BaseModel
from translator import get_text as _

# Create your models here.


class Reminder(BaseModel):
    title = models.CharField(max_length=255, null=True, blank=True, verbose_name=_('title'))
    short_text = models.TextField(null=True, blank=True, verbose_name=_('Short text'))
    long_text = models.TextField(null=True, blank=True, verbose_name=_('Long text'))

