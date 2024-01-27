from django.db import models

from core.models import BaseContentType
from micmod_base.base import Currency


# Create your models here.

class Additions(BaseContentType):
    addition_title = models.CharField(max_length=100)
    addition_description = models.TextField(max_length=1000, blank=True, null=True)
    addition_count = models.IntegerField(default=0)
    addition_currency = models.ForeignKey(Currency, on_delete=models.DO_NOTHING)


