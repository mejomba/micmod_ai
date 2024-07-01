from django.db import models

from accounts.models import User
from core.models import AbsBaseModel
from translator import get_text as _


class BIReport(AbsBaseModel):
    url = models.TextField(max_length=1000, verbose_name=_('url'), null=True, blank=True)
    name = models.TextField(max_length=200, verbose_name=_('name'), null=True, blank=True)
    user_list = models.ManyToManyField(User, related_name='BIReport_rel')
