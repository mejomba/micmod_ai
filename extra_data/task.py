from celery import shared_task
from extra_data.models import Item, ItemPackage
from django.db import transaction

from django.db import connection


@shared_task
def link_item_packages():
    with connection.cursor() as cursor:
        cursor.execute("SELECT distinct package FROM public.extra_data_item where package is not null;")
        rows = cursor.fetchall()
        for row in rows:
            item_package, created = ItemPackage.objects.get_or_create(title=row[0])
            Item.objects.filter(package=row[0]).update(package2=item_package)
            print('create: ', row[0])
