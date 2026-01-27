# your_app/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order


# @receiver(post_save, sender=Order, dispatch_uid='order.order.order_post_save')
# def order_post_save(sender, instance: Order, created, **kwargs):
#     if created:
        # print("Order created:", instance.id)
    # else:
        # print("Order updated:", instance.id)
        # if instance.sepidar_wh_code == 2:
        #     pass
