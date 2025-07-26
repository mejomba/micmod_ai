from django.db import models

from core.models import BaseModel
from translator import get_text as _

# Create your models here.


class Guides(BaseModel):
    """write the name of each model in the section id and add the section id to each part"""
    SECTION_CHOICES = (
        ('quotation', 'پیش فاکتور'),
        ('payment_order', 'دستور پرداخت'),
    )
    section_id = models.CharField(max_length=100, choices=SECTION_CHOICES, null=True, blank=True)
    title = models.CharField(max_length=255, verbose_name=_('title'))
    description = models.TextField(verbose_name=_("Description"))

    def __str__(self):
        return self.title
