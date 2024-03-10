import os
from datetime import datetime

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from core.models import BaseContentType, BaseAbsContentType
from translator import get_text as _


def uploaded_image_path(instance, filename: str):
    """generate file path for image"""
    content_type = ContentType.objects.filter(id=instance.content_type_id).first()
    now = datetime.now()
    name = '_'.join(filename.split(' '))
    name = f"{content_type.app_label}_{content_type.model}_{now.date()}_{now.hour}_{now.minute}_{now.microsecond}_{name}"

    return os.path.join('uploads/image/', name)


def uploaded_file_path(instance, filename: str):
    """generate file path for image"""
    content_type = ContentType.objects.filter(id=instance.content_type_id).first()
    now = datetime.now()
    name = '_'.join(filename.split(' '))
    name = f"{content_type.app_label}_{content_type.model}_{now.date()}_{now.hour}_{now.minute}_{now.microsecond}_{name}"

    return os.path.join('uploads/file/', name)


class Image(BaseAbsContentType):
    path = models.FileField(verbose_name=_('image'), upload_to=uploaded_image_path)
    alt = models.CharField(verbose_name=_('alt'), max_length=64, null=True, blank=True)
    group = models.SmallIntegerField(verbose_name=_('image group'), null=True, blank=True)

    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return f'{str(self.path).split("_")[-1]}'

    def __repr__(self):
        return f'{str(self.path).split("_")[-1]}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def class_name(self):
        return f'{self.__class__.__name__}'


class File(BaseAbsContentType):
    path = models.FileField(verbose_name=_('file'), upload_to=uploaded_file_path)
    group = models.SmallIntegerField(verbose_name=_('file group'), null=True, blank=True)

    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    def __str__(self):
        return f'{str(self.path).split("_")[-1]}'

    def __repr__(self):
        return f'{str(self.path).split("_")[-1]}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def name(self):
        name = self.path.url.split('/')[-1]
        return f'{name}'

    def class_name(self):
        return f'{self.__class__.__name__}'