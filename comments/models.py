from django.contrib.contenttypes.models import ContentType
from django.db import models
from core.models import BaseContentType, AbsBaseModel
from extra_data.models import Customer, Item
from translator import get_text as _


class Comments(BaseContentType):
    Comment_CHOICES = (
        # cancel
        ('C', 'کنسلی'),
        ('D', 'تاخیر در استعلام بازرگانی'),
        ('E', 'تاخیر در استعلام تدارکات داخل'),
        ('F', 'تاخیر در ارسال پیش فاکتور'),
        ('G', 'قیمت بالای استعلام خارج'),
        ('H', 'قیمت بالای استعلام داخل'),
        ('I', 'زمان تحویل استعلام خارج'),
        ('J', 'پیدا نشدن کالای مد نظر مشتری'),
        ('K', 'عدم پاسخگویی مشتری نسبت به سوالات مطرح شده'),
        ('P', 'برآورد قیمت'),
        # trade
        ('L', 'قیمت کمتر'),
        ('M', 'آیتم جایگزین'),
        ('N', 'زمان تحویل'),
        # for group
        ('Q', 'فقط بازرگانی'),
        # order error
        ('R', 'خطای سفارش'),
        # sales cancel order
        ('U', 'کنسلی سفارش'),
        # trade cancel order approval
        ('T', 'تایید کنسلی سفارش'),
        ('V', 'رد کنسلی سفارش'),
        # factor accounting
        ('S', 'عدم تایید مالی فاکتور'),
        # other
        ('O','کامنت ساده'),
    )
    comment_title = models.CharField(max_length=1, choices=Comment_CHOICES, default='O', verbose_name=_('comment_title'))
    comment_content = models.TextField(max_length=1000, null=True, blank=True, verbose_name=_('comment_content'))
    for_customer = models.BooleanField(default=False, verbose_name=_('for_customer'))
    customer = models.ForeignKey(Customer, null=True, blank=True, verbose_name=_('customer'), on_delete=models.DO_NOTHING)
    for_sku = models.BooleanField(default=False, verbose_name=_('for_sku'))
    sku = models.ForeignKey(Item, null=True, blank=True, verbose_name=_('sku'), on_delete=models.DO_NOTHING)
    is_active = models.BooleanField(default=True, verbose_name=_('is_active'))


class CommentSeen(AbsBaseModel):
    comment = models.ForeignKey(Comments, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('comment', 'creator_user', 'editor_user')
