import asyncio
from datetime import datetime
import math

from django.db import models
# Create your tests here.
import os

from tools.google_sheet import GSheet

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "_keenthemes.settings")
import django
django.setup()
from tools.utils import read_excel_data
from django.db import connection
from extra_data.models import PurchaseGroup,SaleGroup,HS,Item,CustomsGroup,Brand,ItemWeight
from inquiry.models import PriceInquiryResult
from micmod_base.base import Currency
from sepidar.models import APILogs, Item as SepItem
from sepidar.scripts.sepidar_classes import Urls


def import_items_from_sepidar(extra_data):
    max_importet_item = Item.objects.filter(sepidar_id__isnull=False).order_by('sepidar_id').last()
    if max_importet_item:
        max_importet_item = max_importet_item.sepidar_id
    else:
        max_importet_item = 0
    # max_importet_item = 0
    items = SepItem.get_all_items(max_importet_item) #APILogs.new_call(Urls.items.url)[1]
    for item in items:
        extra_data_item = Item.objects.filter(sku=item.Code)[0]
        if extra_data_item:
            if not extra_data_item.sepidar_id:
                extra_data_item.sepidar_id = item.ItemID
                if not extra_data_item.purchase_group or extra_data_item.sale_group:
                    purchase_group = PurchaseGroup.objects.filter(sepidar_id=item.PurchaseGroupRef).first()
                    extra_data_item.sale_group_id = purchase_group.id if purchase_group else None
                if not extra_data_item.purchase_group or extra_data_item.sale_group:
                    sales_group = SaleGroup.objects.filter(sepidar_id=item.SaleGroupRef).first()
                    extra_data_item.sale_group_id = sales_group.id if sales_group else None
                extra_data_item.save()
        else:
            sales_group = SaleGroup.objects.filter(sepidar_id=item.SaleGroupRef).first()
            purchase_group = PurchaseGroup.objects.filter(sepidar_id=item.PurchaseGroupRef).first()
            if purchase_group:
                data = extra_data
                data['sepidar_id'] = item.ItemID
                data['sepidar_id'] = item.ItemID
                data['sku'] = item.Code
                data['id'] = item.Code
                data['part_number'] = item.Title
                data['technical_confirm'] = True
                data['sale_group_id'] = sales_group.id if sales_group else None
                data['purchase_group_id'] = purchase_group.id if purchase_group else None
                Item.objects.create(**data)
            else:
                print(f'id:{item.ItemID}--code:{item.Code} has no purchase group')


def import_purchase_groups_from_sepidar(extra_data):
    items = SepItem.get_all_purchase_groups()
    for item in items:
        extra_data_item = PurchaseGroup.objects.filter(title=item.Title).first()
        if extra_data_item:
            extra_data_item.sepidar_id = item.GroupingID
            extra_data_item.sepidar_code = item.Code
            extra_data_item.save()
        else:
            data = extra_data
            data['sepidar_id'] = item.GroupingID
            data['sepidar_code'] = item.Code
            data['title'] = item.Title
            PurchaseGroup.objects.create(**data)


def import_sales_groups_from_sepidar(extra_data):
    items = SepItem.get_all_sales_groups()
    for item in items:
        extra_data_item = SaleGroup.objects.filter(title=item.Title).first()
        if extra_data_item:
            extra_data_item.sepidar_id = item.GroupingID
            extra_data_item.sepidar_code = item.Code
            extra_data_item.save()
        else:
            data = extra_data
            data['sepidar_id'] = item.GroupingID
            data['sepidar_code'] = item.Code
            data['title'] = item.Title
            SaleGroup.objects.create(**data)



def update_model_based_excel(datas:list[dict], model:models.Model,update=True,pk=0,truncate=False,
                             extra_data=dict()):
    try:
        pk_field = list(datas[0].keys())[pk]
        if truncate:
            cursor = connection.cursor()
            try:
                cursor.execute('TRUNCATE TABLE "{0}" RESTART IDENTITY'.format(model._meta.db_table))
            except:
                try:
                    model.objects.all().delete()
                except Exception as e:
                    print(str(e))
        for data in datas:
            row = extra_data.copy()
            for field in model._meta.get_fields():
                if field.name in data.keys() and data[field.name]:
                    row[field.name] = data[field.name]
            try:
                if update:
                    obj, created = model.objects.aupdate_or_create(
                        **{pk_field: row[pk_field]},
                        defaults=row,
                    )
                else:
                    # obj = asyncio.run(model.objects.acreate(**row))
                    obj = model.objects.create(**row)
            except Exception as e:
                print(str(e))
    except Exception as e:
        print(str(e))

def convert_data(datas:list[dict],keys=list[str],converts=list[type]):
    for data in datas:
        for key in keys:
            value = data[key]
            if value is not None:
                for convert in converts:
                    value = convert(value)
                data[key] = value
    return datas

def set_foreign_key(datas:list[dict],model:models.Model,key,search_field,converts=[]):
    for data in datas:
        try:
            value = data[key]
            if value:
                for convert in converts:
                    value = convert(value)
                data[key] = model.objects.get(**{search_field: value})
        except Exception as e:
            print(str(e))
            data[key] = None
    return datas

# your imports, e.g. Django models
if __name__ == '__main__':
    extra_data = {"creator_user_id": 1, "editor_user_id": 1}
    import_purchase_groups_from_sepidar(extra_data)
    import_sales_groups_from_sepidar(extra_data)
    import_items_from_sepidar(extra_data)
    wb = GSheet("13TgipUaeLAElR10RXgg8zF8roXEefL4nfbNJWip7lsA")
    print(extra_data)
    datas = [
        {"title":"ریال", "title_en":"Rial"},
        {"title":"یوان", "title_en":"RMB"},
        {"title":"دلار", "title_en":"Dollar"},
        {"title":"یورو", "title_en":"Ero"},
             ]
    update_model_based_excel(datas, Currency,update=True)

    # datas = read_excel_data("sheet data/hs.xlsx",header_row=0)
    datas = wb.read_sheet("hs")
    # update_model_based_excel(datas, HS, extra_data=extra_data,truncate=True)
    #
    # datas = read_excel_data("sheet data/sales_groups.xlsx",header_row=0)
    datas = wb.read_sheet("hs")
    update_model_based_excel(datas, SaleGroup, extra_data=extra_data,update=False)
    #
    # datas = read_excel_data("sheet data/brands.xlsx", header_row=0)
    datas = wb.read_sheet("sales_group")
    update_model_based_excel(datas, Brand, extra_data=extra_data)
    #
    # datas = read_excel_data("sheet data/purchase_groups.xlsx",header_row=0)
    datas = wb.read_sheet("purchase_group")
    datas = set_foreign_key(datas,HS,"hs","code",[int,str])
    update_model_based_excel(datas,PurchaseGroup,extra_data=extra_data,update=True)
    #
    # datas = read_excel_data("sheet data/items.xlsx", header_row=0)
    datas = wb.read_sheet("item")
    datas = convert_data(datas, ['sku'],[int,str])
    datas = set_foreign_key(datas, SaleGroup, "sale_group", "title", )
    datas = set_foreign_key(datas, Brand, "brand", "title", )
    datas = set_foreign_key(datas, PurchaseGroup, "purchase_group", "title", )
    update_model_based_excel(datas, Item, extra_data=extra_data, update=True)
    #
    # datas = read_excel_data("sheet data/item_weight.xlsx",header_row=0)
    datas = wb.read_sheet("weight")
    datas = set_foreign_key(datas,Item,"sku","sku",[int,str])
    update_model_based_excel(datas,ItemWeight,extra_data=extra_data,update=True)
    #
    # datas = read_excel_data("sheet data/price_inquery_results.xlsx",header_row=0)
    datas = wb.read_sheet("price")
    datas = set_foreign_key(datas, Item, "sku", "sku", [int,str])
    for data in datas:
        data['active'] = True
    datas = set_foreign_key(datas, Currency, "currency_type", "title_en", )
    update_model_based_excel(datas, PriceInquiryResult, extra_data=extra_data, update=True,pk=1,truncate=True)