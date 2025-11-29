from django.db import models

from accounts.models import User
from core.models import BaseModel
from translator import get_text as _

# Create your models here.


class Guides(BaseModel):
    """write the name of each model in the section id and add the section id to each part"""
    SECTION_CHOICES = (
        ('quotation', 'پیش فاکتور'),
        ('payment_order', 'دستور پرداخت'),
        ('shenasname_farayand', 'شناسنامه فرآیند'),
        ('inquiry', 'استعلام'),
        ('factor', 'فاکتور'),
        ('order', 'سفارش'),
    )
    TEAM_CHOICES = (
        ('trade', 'بازرگانی'),
        ('sales', 'فروش'),
        ('bazar', 'بازار'),
        ('wh', 'انبار'),
        ('accounting', 'مالی')
    )
    section_id = models.CharField(max_length=100, choices=SECTION_CHOICES, null=True, blank=True)
    title = models.CharField(max_length=255, verbose_name=_('title'))
    description = models.TextField(verbose_name=_("Description"), null=True, blank=True)
    team = models.CharField(max_length=15, choices=TEAM_CHOICES, verbose_name=_("تیم"), null=True, blank=True)

    def __str__(self):
        return self.title
