from django.contrib.contenttypes.models import ContentType
from django.db import models
from core.models import BaseContentType, AbsBaseModel
from translator import get_text as _


class Comments(BaseContentType):
    Comment_CHOICES = (
        ('C', 'کنسلی'),
        ('D', 'تاخیر در استعلام بازرگانی'),
        ('E', 'تاخیر در استعلام تدارکات داخل'),
        ('F', 'تاخیر در ارسال پیش فاکتور'),
        ('G', 'قیمت بالای استعلام خارج'),
        ('H', 'قیمت بالای استعلام داخل'),
        ('I', 'زمان تحویل استعلام خارج'),
        ('J', 'پیدا شدن کالای مد نظر مشتری'),
        ('K', 'عدم پاسخگویی مشتری نسبت به سوالات مطرح شده'),
        ('O','موارد دیگر')
    )
    comment_title = models.CharField(max_length=1, choices=Comment_CHOICES, default='O', verbose_name=_('comment_title'))
    comment_content = models.TextField(max_length=1000, null=True, blank=True, verbose_name=_('comment_content'))


class CommentSeen(AbsBaseModel):
    comment = models.ForeignKey(Comments, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('comment', 'creator_user', 'editor_user')
