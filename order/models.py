from django.db import models
from core.models import BaseModel, BaseModeWF
from extra_data.models import Brand, Item


class Order(BaseModeWF):
    title = models.CharField(max_length=255, blank=True, null=True)


class OrderItem(BaseModel):
    order = models.ForeignKey(Order, on_delete=models.DO_NOTHING, related_name='order_items')
    quantity = models.FloatField(blank=True, null=True)
    item = models.ForeignKey(Item, on_delete=models.DO_NOTHING, null=True)

    # fields
    QUALITY_CHOICES = (('l', 'Low'), ('m', 'Medium'), ('h', 'high'))

    # name = models.CharField(max_length=255, blank=True, null=True)
    # price = models.FloatField(blank=True, null=True)
    # brands = models.ForeignKey(Brand, on_delete=models.DO_NOTHING, related_name='brands')
    # type = models.CharField(max_length=255, blank=True, null=True)
    # quality = models.CharField(max_length=255, choices=QUALITY_CHOICES, blank=True, null=True)

