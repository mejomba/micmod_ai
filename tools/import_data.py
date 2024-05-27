import asyncio
from datetime import datetime
import math

from django.db import models
from tools.form_tools import select_cquery
# Create your tests here.
import os

from tools.google_sheet import GSheet

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "_keenthemes.settings")
import django
django.setup()
from tools.utils import read_excel_data
from django.db import connection
from extra_data.models import * #PurchaseGroup,SaleGroup,HS,Item,CustomsGroup,Brand,ItemWeight
from inquiry.models import PriceInquiryResult
from micmod_base.base import Currency
from sepidar.models import APILogs, Item as SepItem
from sepidar.scripts.sepidar_classes import Urls




reps = ["ي", "ی", "ك", "ک"]


def valid_title(title_string):
    try:
        return title_string.replace(reps[0], reps[1]).replace(reps[2], reps[3])
    except Exception as e:
        return title_string
        print(e, title_string)


def import_provience_from_sepidar(extra_data):
    extra_data = extra_data.copy()
    items = SepItem.get_all_provience()
    for item in items:
        try:
            data = extra_data
            data['title'] = valid_title(item.title)
            # data['sepidar_location_id'] = item.location_id
            Province.objects.update_or_create(sepidar_location_id=item.location_id,defaults=data)
        except Exception as e:
            print(str(e))


def import_customer_group_from_sepidar(extra_data):
    extra_data = extra_data.copy()
    items = SepItem.get_all_customer_groups()
    for item in items:
        try:
            data = extra_data
            data['title'] = valid_title(item.Title)
            # data['sepidar_group_id'] = item.GroupingID
            CustomerGroup.objects.update_or_create(sepidar_group_id=item.GroupingID,defaults=data)
        except Exception as e:
            print(str(e))


def import_senf_from_sepidar(extra_data, max_sepidar_party_id=0):
    extra_data = extra_data.copy()
    items = SepItem.get_all_senf(max_sepidar_party_id)
    for item in items:
        try:
            data = extra_data
            # data['title'] = valid_title(item.code)
            Senf.objects.update_or_create(title=valid_title(item.code),defaults=data)
        except Exception as e:
            print(str(e))


def import_sub_senf_from_sepidar(extra_data, max_sepidar_party_id=0):
    extra_data = extra_data.copy()
    items = SepItem.get_all_sub_senf(max_sepidar_party_id)
    for item in items:
        try:
            data = extra_data
            # data['title'] = valid_title(item.code)
            SubSenf.objects.update_or_create(title=valid_title(item.code),defaults=data)
        except Exception as e:
            print(str(e))


def import_introduction_method_from_sepidar(extra_data, max_sepidar_party_id=0):
    extra_data = extra_data.copy()
    items = SepItem.get_all_introduction_method(max_sepidar_party_id)
    for item in items:
        try:
            data = extra_data
            # data['title'] = valid_title(item.code)
            IntroductionMethod.objects.update_or_create(title=valid_title(item.code),defaults=data)
        except Exception as e:
            print(str(e))


def import_introducer_from_sepidar(extra_data, max_sepidar_party_id=0):
    extra_data = extra_data.copy()
    items = SepItem.get_all_introducer(max_sepidar_party_id)
    for item in items:
        try:
            data = extra_data
            # data['title'] = valid_title(item.code)
            Introducer.objects.update_or_create(title=valid_title(item.code),defaults=data)
        except Exception as e:
            print(str(e))


def import_marketer_from_sepidar(extra_data, max_sepidar_party_id=0):
    extra_data = extra_data.copy()
    items = SepItem.get_all_marketer(max_sepidar_party_id)
    for item in items:
        try:
            data = extra_data
            # data['title'] = valid_title(item.code)
            Marketer.objects.update_or_create(title=valid_title(item.code),defaults=data)
        except Exception as e:
            print(str(e))


def import_customers_from_sepidar(extra_data):
    max_sepidar_party_id = int(select_cquery("select max(PartyId) as max_id from GNR.Party where IsCustomer=1","sepidar")['max_id'][0])
    max_local_party = Customer.objects.all().order_by("-sepidar_party_id").first()
    max_local_party_id = max_local_party.sepidar_party_id if max_local_party else 0
    if max_local_party_id >= max_sepidar_party_id:
        return
    extra_data = extra_data.copy()
    # import_provience_from_sepidar(extra_data)
    import_customer_group_from_sepidar(extra_data)
    import_senf_from_sepidar(extra_data, max_local_party_id)
    import_sub_senf_from_sepidar(extra_data, max_local_party_id)
    import_introduction_method_from_sepidar(extra_data, max_local_party_id)
    import_introducer_from_sepidar(extra_data, max_local_party_id)
    import_marketer_from_sepidar(extra_data, max_local_party_id)

    items = SepItem.get_all_customers(max_local_party_id)
    for item in items:
        try:
            data = extra_data
            data['sepidar_dl_code'] = item.sepidar_dl_code
            data['sepidar_party_id'] = item.sepidar_party_id
            data['title'] = valid_title(item.title)
            data['name'] = valid_title(item.name)
            data['last_name'] = valid_title(item.last_name)
            data['national_code'] = item.national_code
            data['email'] = item.email
            data['phone'] = item.phone
            data['customer_group'] = CustomerGroup.objects.filter(sepidar_group_id=item.customer_group).first()
            data['province'] = Province.objects.filter(title=item.province).first()
            data['location'] = Province.objects.filter(title=item.location).first()
            data['address'] = valid_title(item.address)
            data['senf'] = Senf.objects.filter(title=valid_title(item.senf)).first()
            data['sub_senf'] = SubSenf.objects.filter(title=valid_title(item.sub_senf)).first()
            data['introduction_method'] = IntroductionMethod.objects.filter(title=valid_title(item.introduction_method)).first()
            data['introducer'] = Introducer.objects.filter(title=valid_title(item.introducer)).first()
            data['marketer'] = Marketer.objects.filter(title=valid_title(item.marketer)).first()
            data['revival_date'] = item.revival_date
            data['max_credit'] = item.max_credit
            data['credit_with_doc'] = item.credit_with_doc
            Customer.objects.update_or_create(sepidar_dl_id=item.sepidar_dl_id, defaults=data)
            # data['sepidar_dl_id'] = item.sepidar_dl_id
            # Customer.objects.create(**data)
        except Exception as e:
            print(str(e))



def import_items_from_sepidar(extra_data):
    # max_importet_item = Item.objects.filter(sepidar_id__isnull=False).order_by('sepidar_id').last()
    # if max_importet_item:
    #     max_importet_item = max_importet_item.sepidar_id
    # else:
    #     max_importet_item = 0
    max_importet_item = 0
    items = SepItem.get_all_items(max_importet_item) #APILogs.new_call(Urls.items.url)[1]
    for item in items:
        extra_data_item = Item.objects.filter(sku=item.Code).first()
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
                data = extra_data.copy()
                data['sepidar_id'] = item.ItemID
                # data['sepidar_code'] = item.Code
                data['sku'] = item.Code
                data['id'] = item.Code
                data['part_number'] = item.Title
                data['technical_confirm'] = True
                data['sale_group_id'] = sales_group.id if sales_group else None
                data['purchase_group_id'] = purchase_group.id if purchase_group else None
                try:
                    Item.objects.create(**data)
                except Exception as e:
                    print(str(e))
            else:
                print(f'id:{item.ItemID}--code:{item.Code} has no purchase group')
    reset_seq(Item)


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
        reset_seq(PurchaseGroup)

def reset_seq(model):
    cursor = connection.cursor()
    cursor.execute(f'select max(id) from "{model._meta.db_table}"')
    # max_id = select_cquery(f'select max(id) from "{model._meta.db_table}"','default')
    max_id = cursor.fetchall()
    max_id = max_id[0][0] if max_id else 0
    cursor.execute(f'ALTER SEQUENCE "{model._meta.db_table}_id_seq" RESTART WITH {max_id + 1}')

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
    reset_seq(SaleGroup)


def truncate_table(model, cascade=False):
    try:
        cursor = connection.cursor()
        try:
            if cascade:
                cursor.execute('TRUNCATE TABLE "{0}" RESTART IDENTITY CASCADE'.format(model._meta.db_table))
            else:
                cursor.execute('TRUNCATE TABLE "{0}" RESTART IDENTITY'.format(model._meta.db_table))
        except:
            try:
                model.objects.all().delete()
            except Exception as e:
                print(str(e))
    except Exception as e:
        print(str(e))


def update_model_based_excel(datas:list[dict], model:models.Model,update=True,pk=0,truncate=False,
                             extra_data=dict()):
    try:
        cursor = connection.cursor()
        if truncate:
            try:
                cursor.execute('TRUNCATE TABLE "{0}" RESTART IDENTITY CASCADE'.format(model._meta.db_table))
            except:
                try:
                    model.objects.all().delete()
                except Exception as e:
                    print(str(e))
        pk_field = list(datas[0].keys())[pk]
        for data in datas:
            row = extra_data.copy()
            for field in model._meta.get_fields():
                if field.name in data.keys() and field.name != pk_field: #and data[field.name]
                    row[field.name] = data[field.name]
            try:
                if update:
                    obj, created = model.objects.update_or_create(
                        **{pk_field: data[pk_field]},
                        defaults=row,
                    )
                else:
                    # obj = asyncio.run(model.objects.acreate(**row))
                    obj = model.objects.create(**row)
            except Exception as e:
                print(str(e))
        reset_seq(model)
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


def update_sale_type_from_sheet():
    from micmod_base.models import SaleType,Month,Currency
    wb = GSheet("13TgipUaeLAElR10RXgg8zF8roXEefL4nfbNJWip7lsA")
    datas = wb.read_sheet("sale_type")
    datas = convert_data(datas, ['id','month','currency','extra_percentage'], [int])
    datas = set_foreign_key(datas, Month, "month", "id", [int])
    datas = set_foreign_key(datas, Currency, "currency", "id", [int])
    update_model_based_excel(datas, SaleType, extra_data={}, update=False, truncate=True)
    print('IMEI_imeilistreg')


def update_imei_from_sheet():
    from IMEI.models import IMEIListReg,IMEIListRegDetail,IMEINTSWReg,IMEINTSWRegDetail
    wb = GSheet("13TgipUaeLAElR10RXgg8zF8roXEefL4nfbNJWip7lsA")
    datas = wb.read_sheet("IMEI_imeilistreg")
    update_model_based_excel(datas, IMEIListReg, extra_data={}, update=False, truncate=True)
    print('IMEI_imeilistreg')
    datas = wb.read_sheet("IMEI_imeilistregdetail")
    datas = convert_data(datas, ['id','row','imei_list_reg'], [int])
    datas = set_foreign_key(datas, IMEIListReg, "imei_list_reg", "id", [int])
    update_model_based_excel(datas, IMEIListRegDetail, extra_data={}, update=False, truncate=True)
    print('IMEI_imeilistregdetail')

    datas = wb.read_sheet("IMEI_imeintswreg")
    update_model_based_excel(datas, IMEINTSWReg, extra_data={}, update=False, truncate=True)
    print('IMEI_imeintswreg')
    datas = wb.read_sheet("IMEI_imeintswregdetail")
    datas = convert_data(datas, ['id','row','imei_ntsw_reg'], [int])
    datas = set_foreign_key(datas, IMEINTSWReg, "imei_ntsw_reg", "id", [int])
    update_model_based_excel(datas, IMEINTSWRegDetail, extra_data={}, update=False, truncate=True)
    print('IMEI_imeintswregdetail')


def set_items_sepidar_id_from_sepidar():
    max_importet_item = 0
    items = SepItem.get_all_items(max_importet_item)
    items_code = []
    items_id = []
    for item in items:
        print(item)

        items_code.append(item.Code)
        items_id.append(item.ItemID)
    extra_data_items = Item.objects.filter(sku__in=items_code)

    for extra_data_item in extra_data_items:
        if not extra_data_item.sepidar_id_0:
            x = extra_data_item.sepidar_id

    # for extra_data_item, item_id in zip(extra_data_items, items_id):
    #     if extra_data_item.sku == '12899' or extra_data_item.pk == 12899:
    #         print(extra_data_item)
    #     if not extra_data_item.sepidar_id:
    #         extra_data_item.sepidar_id = item_id
    #         extra_data_item.save()
    # reset_seq(Item)

    # for extra_data_item, item_id in zip(extra_data_items, items_id):
    #     if extra_data_item.sku == '12899' or extra_data_item.pk == 12899:
    #         print(extra_data_item)
    #     if not extra_data_item.sepidar_id:
    #         extra_data_item.sepidar_id = item_id
    #         extra_data_item.save()
    # reset_seq(Item)


# your imports, e.g. Django models
if __name__ == '__main__':
    extra_data = {"creator_user_id": 1, "editor_user_id": 1}
    import_customers_from_sepidar(extra_data)
    update_sale_type_from_sheet()
    update_imei_from_sheet()
    wb = GSheet("13TgipUaeLAElR10RXgg8zF8roXEefL4nfbNJWip7lsA")
    # print(extra_data)
    datas = [
        {"title":"ریال", "title_en":"Rial"},
        {"title":"یوان", "title_en":"RMB"},
        {"title":"دلار", "title_en":"Dollar"},
        {"title":"یورو", "title_en":"Ero"},
             ]
    update_model_based_excel(datas, Currency,update=True)

    datas = wb.read_sheet("hs")
    update_model_based_excel(datas, HS, extra_data=extra_data,truncate=True)
    print('HS')
    #
    datas = wb.read_sheet("sales_group")
    update_model_based_excel(datas, SaleGroup, extra_data=extra_data,update=False, truncate=True)
    print('SaleGroup')
    #
    datas = wb.read_sheet("brand")
    update_model_based_excel(datas, Brand, extra_data=extra_data, truncate=True)
    print('Brand')
    #
    datas = wb.read_sheet("purchase_group")
    datas = set_foreign_key(datas,HS,"hs","code",[int,str])
    update_model_based_excel(datas,PurchaseGroup,extra_data=extra_data,update=False, truncate=True)
    print('PurchaseGroup')
    #
    datas = wb.read_sheet("item")
    datas = convert_data(datas, ['sku'],[int,str])
    datas = set_foreign_key(datas, SaleGroup, "sale_group", "title", )
    datas = set_foreign_key(datas, Brand, "brand", "title", )
    datas = set_foreign_key(datas, PurchaseGroup, "purchase_group", "title", )
    update_model_based_excel(datas, Item, extra_data=extra_data, update=False, truncate=True)
    print('Item')
    #
    datas = wb.read_sheet("weight")
    datas = set_foreign_key(datas,Item,"sku","sku",[int,str])
    update_model_based_excel(datas,ItemWeight,extra_data=extra_data,update=False, truncate=True)
    print('ItemWeight')

    cursor = connection.cursor()
    cursor.execute(f'select max(id) from {PriceInquiryResult._meta.db_table}')
    datas = wb.read_sheet("price")
    datas = set_foreign_key(datas, Item, "sku", "sku", [int,str])
    for data in datas:
        data['active'] = True
    datas = set_foreign_key(datas, Currency, "currency_type", "title_en", )
    update_model_based_excel(datas, PriceInquiryResult, extra_data=extra_data, update=False,pk=0,truncate=True)
    print('PriceInquiryResult')

    import_purchase_groups_from_sepidar(extra_data)
    print('import_purchase_groups_from_sepidar')
    import_sales_groups_from_sepidar(extra_data)
    print('import_sales_groups_from_sepidar')
    import_items_from_sepidar(extra_data)
    print('import_items_from_sepidar')



