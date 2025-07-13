from celery import shared_task
from extra_data.models import Item, ItemPackage
from django.contrib.postgres.aggregates import ArrayAgg
from decimal import Decimal
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


@shared_task
def package_weight_avg():
    items_by_package = Item.objects.values('package').annotate(item_ids=ArrayAgg('id')).order_by('package')

    result = []
    for entry in items_by_package:
        package = entry['package']
        item_ids = entry['item_ids']
        items = Item.objects.filter(id__in=item_ids)
        weights = [item.weight for item in items if item.weight is not None]
        avg_weight = sum(weights) / len(weights)if weights else 0
        result.append({package: round(avg_weight, 4)})

        print(result)
