from celery import shared_task
from django.core.cache import cache
from _keenthemes.settings import CACHES

from micmod_base.models import Quotation,QuotationItem
from dw.models import NewOrder
from tlg.models import Receiver
from _keenthemes.celery_main import app

@shared_task
def add_new_quotation_message():
    qs = QuotationItem.objects.raw("""
    Select * from     
    """)


# @app.task
@shared_task
def add_new_order_receiver():
    print('salammmm')
    new_orders = NewOrder.get_new_order()

    for new_order in new_orders:
        try:
            data = {
                'name': new_order.Title,
                'customer_code': new_order.code,
                'sepidar_phones': f'{new_order.party_phones}\n{new_order.related_phones}',
                'sepidar_email': new_order.related_emails,
             }

            obj = Receiver.objects.get_or_create(**data)
            print(obj)
        except Exception as e:
            print(str(e))
