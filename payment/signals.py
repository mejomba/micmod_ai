from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import GenericPaymentItem


@receiver(post_save, sender=GenericPaymentItem)
def customer_created_handler(sender, instance, created, **kwargs):
    endpoint = 'api2/accounting-payment/226/?struct_name=online_payment'
    url = f'{settings.SHOP_PROTOCOL}://{settings.SHOP_HOST}:{settings.SHOP_PORT}/{endpoint}'
    if created:
        # فقط در زمان ایجاد اجرا میشه
        print(f"پرداخت جدید ساخته شد: {instance}")