from django.db import models

from core.models import BaseModel
from translator import get_text as _

# Create your models here.


class Guides(BaseModel):
    title = models.CharField(max_length=255, verbose_name=_('title'))
    description = models.TextField(verbose_name=_("Description"))

    def __str__(self):
        return self.title
