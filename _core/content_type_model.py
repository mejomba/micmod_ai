from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from _core.models import AbsBaseModel

from translator import get_text as _


class BaseContentType(AbsBaseModel):

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name=_("content_type"))
    object_id = models.PositiveIntegerField(verbose_name=_("object_id"))
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]


