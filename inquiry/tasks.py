import os
import datetime, time

from celery import shared_task
from django.core.cache import cache
from django.utils import timezone

from extra_data.models import Item, ItemPrice
from inquiry.models import PriceInquiryResult
from tools.google_sheet import GSheet

from django.conf import settings


def update_price_db(objs):
    # data_list = [
    #     {"item": "A1", "x": 1.1, "y": 2.2, "z": 3.3},
    #     {"item": "A2", "x": 4.4, "y": 5.5, "z": 6.6},
    #     # ...
    # ]

    # 1️⃣ استخراج تمام itemها از داده‌های ورودی
    item_values = [d["item"] for d in objs]

    # 2️⃣ گرفتن تمام رکوردهای موجود از دیتابیس
    existing_qs = ItemPrice.objects.filter(item__in=item_values)
    existing_map = {obj.item: obj for obj in existing_qs}

    to_create = []
    to_update = []

    # 3️⃣ تشخیص رکوردهای جدید و قدیمی
    for data in objs:
        item = data["item"]
        if item in existing_map:
            obj = existing_map[item]
            obj.air = data["air"]
            obj.sea = data["sea"]
            obj.express = data["express"]
            obj.last_update_date = timezone.now()
            to_update.append(obj)
        else:
            data['last_update_date'] = timezone.now()
            data['created_date'] = timezone.now()
            to_create.append(ItemPrice(**data))

    # 4️⃣ ایجاد رکوردهای جدید
    if to_create:
        ItemPrice.objects.bulk_create(to_create, batch_size=500)

    # 5️⃣ آپدیت رکوردهای موجود
    if to_update:
        ItemPrice.objects.bulk_update(to_update, ["air", "sea", "express"], batch_size=500)


@shared_task
def update_components():
    import pandas as pd
    if cache.get('update_components'):
        print('task is running')
        return
    try:
        cache.set('update_components', True, 300)
        print('update_components start')
        components = Item.objects.all().order_by('id')
        components_lst = list()
        c = 0
        for component in components:
            c += 1
            if c % 1000 == 0:
                print("update component", c, "sku=", component.sku)
                print(component.sku)
            component_ = dict()
            component_['sku'] = int(component.sku)
            component_['part_number'] = component.part_number
            component_['purchase_group'] = component.purchase_group.title if component.purchase_group else None
            component_['sale_group'] = component.sale_group.title if component.sale_group else None
            component_['brand'] = component.brand.title if component.brand else None
            component_['is_sea_default'] = component.is_sea_default
            component_['package'] = component.package
            component_['weight'] = component.weight
            component_['hs'] = component.active_hs.code if component.active_hs else None
            # print(component_)
            components_lst.append(component_)

        print('update_components validate')
        update_time = datetime.datetime.now().strftime('%Y/%m/%d  %H:%M')

        df = pd.DataFrame(components_lst)
        # excel_file_path = "components_list.xlsx"
        # df.to_excel(excel_file_path, index=False, sheet_name="Portal_list")
        # print(f"Data written to {excel_file_path}")

        g_sheet = GSheet("1SCuCSTYl4xZpY6aFYy54lMRLFvxX4WLaQRLWirYIKVQ")
        g_sheet.clear_rows('Portal_list')
        g_sheet.update_rows('Portal_list', components_lst, 2)
        g_sheet.wb.worksheet('Portal_list').update_cell(2, 10, update_time)
        print(f'task update_components done at:{update_time}')
        print('update_components done')
        print('count=', c)
    except Exception as e:
        print(str(e))
    finally:
        cache.set('update_components', False, 100)


@shared_task
def update_price_list():
    if cache.get('task_is_running'):
        print('task is running')
        return
    try:
        cache.set('task_is_running', True, 300)
        print('task_started')
        prices = []
        price_for_db = []
        y_rate = None
        chash_rial = None
        grade_a = None
        qty_1_9 = None
        qty_10_99 = None
        qty_100_999 = None
        qty_1000_ = None
        items = Item.objects.all()
        g_sheet = GSheet("1LC3YoRdEbkP9ipxAB_c6k3l05FF7hNsMJ97hllLjXI8")
        print('gsheet created')
        # i=0
        for idx, item in enumerate(items):
            if item.price and item.price.rmb_final_price:
                price = item.price.rmb_final_price
                price = {k: round(v.get('price'), 5) for k, v in price.items()}
                price['sku'] = int(item.sku)
                price['is_sea_default'] = item.is_sea_default
                prices.append(price)
                price_for_db.append(
                    {'item': item, 'air': price.get('air'),
                     'sea':price.get('sea'),
                     'express': price.get('express')}
                )
                if idx % 1000 == 0:
                    print(f'update_price_list count: {idx}: ', item.sku, price)
                if not y_rate:
                    y_rate = item.price.price_settings.free_rmb_rate
                    chash_rial = item.price.price_settings.discount_based_payment_method[0]['rial_percentage']
                    grade_a = item.price.price_settings.discount_based_customer[2]['percentage']
                    qty_1_9 = item.price.price_settings.discount_based_quantity[0]['percentage']
                    qty_10_99 = item.price.price_settings.discount_based_quantity[1]['percentage']
                    qty_100_999 = item.price.price_settings.discount_based_quantity[2]['percentage']
                    qty_1000_ = item.price.price_settings.discount_based_quantity[3]['percentage']
        else:
            update_price_db(price_for_db)
        if not prices:
            g_sheet.clear_rows('portal_prices')
            g_sheet.update_rows('portal_prices', prices, 2)
            update_time = datetime.datetime.now().strftime('%Y/%m/%d  %H:%M')
            print(f'task done at:{update_time}')
            g_sheet.wb.worksheet('portal_prices').update_cell(1, 7, update_time)
            g_sheet.wb.worksheet('portal_prices').update_cell(1, 9, y_rate)
            g_sheet.wb.worksheet('portal_prices').update_cell(2, 10, grade_a)
            g_sheet.wb.worksheet('portal_prices').update_cell(2, 11, qty_1_9)
            g_sheet.wb.worksheet('portal_prices').update_cell(2, 12, qty_10_99)
            g_sheet.wb.worksheet('portal_prices').update_cell(2, 13, qty_100_999)
            g_sheet.wb.worksheet('portal_prices').update_cell(2, 14, qty_1000_)
            g_sheet.wb.worksheet('portal_prices').update_cell(2, 15, chash_rial)
    except Exception as e:
        print(str(e))
    finally:
        cache.set('task_is_running', False, 100)


@shared_task
def deactivate_old_bazar_price(expiration_in_day=3):
    delta = timezone.now() - datetime.timedelta(expiration_in_day, hours=6)
    prices = PriceInquiryResult.objects.filter(inquiry_type__title__icontains='داخل', last_update_date__lt=delta, active=True)
    prices.update({'active': False})
    for price in prices:
        price.active = False



def create_essentials(db_config):
    if db_config is None:
        db_config = settings.DATABASES.get('default')

    db_name = db_config['NAME']
    db_user = db_config['USER']
    db_password = db_config['PASSWORD']
    db_host = db_config['HOST']
    db_port = db_config['PORT']
    backup_path = db_config["BACKUP_PATH"] or 'db_backup'

    filename = f'db_backup__'
    filename = db_name + '__' + filename + time.strftime("%Y_%m_%d__%H_%M_%S") + ".sql"
    command_str = str(db_host) + " -p " + str(db_port) + " -d " + db_name + " -U " + db_user
    import os
    os.environ["PGPASSWORD"] = db_password
    return command_str, backup_path, filename


@shared_task
def db_backup(db, table_names=None):
    command_str, backup_path, filename = create_essentials(db)
    command_str = "pg_dump -h " + command_str

    if table_names is not None:
        for x in table_names:
            command_str = command_str + " -t " + x

    try:
        with open(f'{backup_path}/{filename}', "x") as file:
            pass
        print("Backup File created successfully!")
    except FileExistsError:
        print("Backup File already exists.")

    sep = '\\' if 'nt' in os.name.lower() else '/'
    command_str1 = command_str + " -F t -b -v -f " + '"' + os.getcwd() + sep + backup_path + sep + filename + '"'
    command_str2 = command_str + " -F c -b -v -f " + '"' + os.getcwd() + sep + backup_path + sep + filename + '.tar' + '"'
    try:
        os.system(command_str1)
        os.system(command_str2)
        print("Backup completed")
        return 'OK'
    except Exception as e:
        print("!!Problem occured!!")
        print(e)
        return str(e)


def restore_database(table_names=None):
    command_str, backup_path, filename = create_essentials()
    command_str = "pg_restore -h " + command_str

    if table_names is not None:
        for x in table_names:
            command_str = command_str + " -t " + x

    command_str = command_str + " -v '" + backup_path + "/" + filename + "'"

    try:
        os.system(command_str)
        print("Restore completed")
    except Exception as e:
        print("!!Problem occured!!")
        print(e)


def cleanup_filesystem():

    delete = False
    for_delete = []
    # مسیر دایرکتوری مورد نظر
    directory = settings.BASE_DIR / 'db_backup'

    days = 10
    now = time.time()
    cutoff = now - (days * 86400)

    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)

        if os.path.isfile(filepath):
            file_creation_time = os.path.getctime(filepath)

            if file_creation_time < cutoff:
                os.remove(filepath)
                print(f'{filepath}')
