from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from extra_data.models import Item
from micmod_base.models import BaseModel
from translator import get_text as _


class Receipt(BaseModel):
    register_date = models.DateField(verbose_name=_('register date'), null=True, blank=True)
    pack_number = models.CharField(verbose_name=_('pack number'), max_length=255, null=True, blank=True)
    sepidar_code = models.CharField(verbose_name=_('sepidar code'), max_length=255, null=True, blank=True)
    description = models.TextField(verbose_name=_('description'), max_length=1000, null=True, blank=True)
    stock_id = models.PositiveIntegerField(verbose_name=_('stock id'), null=True, blank=True)

    class Meta:
        ordering = 'id',

    def __str__(self):
        return f'{self.pack_number}'


class ReceiptDetail(BaseModel):
    BATCH_TYPE = (('box', _('box')), ('rol', _('rol')))
    receipt_id = models.ForeignKey('Receipt', verbose_name=_('receipt'), on_delete=models.DO_NOTHING)
    sku = models.ForeignKey(Item, verbose_name=_('sku'), on_delete=models.DO_NOTHING)
    quantity = models.PositiveIntegerField(verbose_name=_('quantity'), null=True, blank=True)
    batch_count = models.FloatField(verbose_name=_('batch count'), null=True, blank=True)
    item_in_batch = models.FloatField(verbose_name=_('item in batch'), null=True, blank=True)
    batch_type = models.CharField(verbose_name=_('batch type'), choices=BATCH_TYPE, max_length=16, null=True, blank=True)
    location = models.CharField(verbose_name=_('location'), max_length=64, null=True, blank=True)
    active = models.BooleanField(verbose_name=_('active'), default=False)

    class Meta:
        ordering = 'id',

    def __str__(self):
        return f'{self.sku}'


@receiver(post_save, sender=ReceiptDetail)
def deactivate_prev_receipt_detail(sender, instance, created, **kwargs):
    try:
        if instance.id and instance.active:
            for item in ReceiptDetail.objects.filter(sku=instance.sku):
                if item != instance:
                    item.active = False
                    item.save()
    except Exception as e:
        print(e)
