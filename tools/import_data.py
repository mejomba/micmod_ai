import asyncio
from datetime import datetime
import math

from django.db import models
# Create your tests here.
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dason.settings")
import django
django.setup()
from tools.utils import read_excel_data
from django.db import connection
from extra_data.models import PurchaseGroup,SaleGroup,HS,Item,CustomsGroup,Brand,ItemWeight
from inquiry.models import PriceInquiryResult
from micmod_base.base import Currency

def update_model_based_excel(datas:list[dict], model:models.Model,update=True,pk=0,truncate=False,
                             extra_data=dict()):
    try:
        pk_field = list(datas[0].keys())[pk]
        if truncate:
            cursor = connection.cursor()
            try:
                cursor.execute('TRUNCATE TABLE "{0}"'.format(model._meta.db_table))
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
    extra_data = {"creator_user_id":1, "editor_user_id":1}
    print(extra_data)
    # datas = [
    #     {"title":"ریال", "title_en":"Rial"},
    #     {"title":"یوان", "title_en":"RMB"},
    #     {"title":"دلار", "title_en":"Dollar"},
    #     {"title":"یورو", "title_en":"Ero"},
    #          ]
    # update_model_based_excel(datas, Currency,update=True)
    # datas = read_excel_data("sheet data/hs.xlsx",header_row=0)
    # update_model_based_excel(datas, HS, extra_data=extra_data,truncate=True)
    #
    datas = read_excel_data("sheet data/sales_groups.xlsx",header_row=0)
    update_model_based_excel(datas, SaleGroup, extra_data=extra_data,update=False)
    #
    # datas = read_excel_data("sheet data/brands.xlsx", header_row=0)
    # update_model_based_excel(datas, Brand, extra_data=extra_data)
    #
    # datas = read_excel_data("sheet data/purchase_groups.xlsx",header_row=0)
    # datas = set_foreign_key(datas,HS,"hs","code",[int,str])
    # update_model_based_excel(datas,PurchaseGroup,extra_data=extra_data,update=True)
    #
    # datas = read_excel_data("sheet data/items.xlsx", header_row=0)
    # datas = convert_data(datas, ['sku'],[int,str])
    # datas = set_foreign_key(datas, SaleGroup, "sale_group", "title", )
    # datas = set_foreign_key(datas, Brand, "brand", "title", )
    # datas = set_foreign_key(datas, PurchaseGroup, "purchase_group", "title", )
    # update_model_based_excel(datas, Item, extra_data=extra_data, update=True)
    #
    # datas = read_excel_data("sheet data/item_weight.xlsx",header_row=0)
    # datas = set_foreign_key(datas,Item,"sku","sku",[int,str])
    # update_model_based_excel(datas,ItemWeight,extra_data=extra_data,update=True)
    #
    # datas = read_excel_data("sheet data/price_inquery_results.xlsx", header_row=0)
    # datas = set_foreign_key(datas, Item, "sku", "sku", [int,str])
    # for data in datas:
    #     data['active'] = True
    # datas = set_foreign_key(datas, Currency, "currency_type", "title_en", )
    # update_model_based_excel(datas, PriceInquiryResult, extra_data=extra_data, update=True,pk=1,truncate=True)