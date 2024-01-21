from django.db import models
from core.models import BaseContentType
# Create your models here.


class Comments(BaseContentType):
    Comment_CHOICES = (
        ('C', 'کنسلی'),
        ('O','موارد دیگر')
    )
    comment_title = models.CharField(max_length=1, choices=Comment_CHOICES, default='O')
    comment_content = models.TextField(max_length=1000, null=True, blank=True)


