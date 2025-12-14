from django.db import models

from accounts.models import User
from core.models import BaseModel
from translator import get_text as _

# Create your models here.


class Reminder(BaseModel):
    TIME_UNIT_CHOICES = [
        ('day', 'روز'),
        ('month', 'ماه'),
        ('year', 'سال'),
    ]
    REMINDER_TYPE_CHOICES = [
        ('SMS', 'پیامک'),

    ]

    title = models.CharField(max_length=255, verbose_name=_('title'))
    short_text = models.CharField(max_length=100, null=True, blank=True, verbose_name=_('Short text'))
    long_text = models.TextField(null=True, blank=True, verbose_name=_('Long text'))
    time_value = models.PositiveIntegerField(verbose_name="مقدار")
    time_unit = models.CharField(max_length=10, choices=TIME_UNIT_CHOICES, verbose_name="نوع زمان")
    repeat_interval_value = models.PositiveIntegerField(verbose_name="مقدار", null=True, blank=True)
    repeat_interval_unit = models.CharField(max_length=10, choices=TIME_UNIT_CHOICES, verbose_name="نوع زمان", null=True, blank=True)
    user = models.ManyToManyField(User, verbose_name="user")
    start_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateTimeField(null=True, blank=True)
    reminder_type = models.CharField(max_length=10, choices=REMINDER_TYPE_CHOICES)

    def __str__(self):
        return self.title





