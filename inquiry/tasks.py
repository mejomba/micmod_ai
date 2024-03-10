import datetime

from celery import shared_task
from django.core.cache import cache

from extra_data.models import Item
from tools.google_sheet import GSheet

@shared_task
def update_price_list():
    if cache.get('task_is_running'):
        print('task is running')
        return
    try:
        cache.set('task_is_running', True, 300)
        print('task_started')
        prices = []
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
        for item in items:
            if item.price and item.price.rmb_final_price:
                price = item.price.rmb_final_price
                price['sku'] = int(item.sku)
                price['is_sea_default'] = item.is_sea_default
                prices.append(price)
                if not y_rate:
                    y_rate = item.price.price_settings.free_rmb_rate
                    chash_rial = item.price.price_settings.discount_based_payment_method[0]['rial_percentage']
                    grade_a = item.price.price_settings.discount_based_customer[2]['percentage']
                    qty_1_9 = item.price.price_settings.discount_based_quantity[0]['percentage']
                    qty_10_99 = item.price.price_settings.discount_based_quantity[1]['percentage']
                    qty_100_999 = item.price.price_settings.discount_based_quantity[2]['percentage']
                    qty_1000_ = item.price.price_settings.discount_based_quantity[3]['percentage']
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