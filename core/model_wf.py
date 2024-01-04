from .models import BaseModel
from django.db import models

class BaseModelWF(BaseModel):
    _workflows = models.ManyToManyField('workflow.WorkFlow', related_name='workflows')

    class Meta:
        abstract = True
