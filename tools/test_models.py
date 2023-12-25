# from datetime import datetime
# import math
#
# from django.db import models
# # Create your tests here.
# import os
#
# from unicodedata import name
#
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dason.settings")
# import django
# django.setup()
# from tools.utils import read_excel_data
# from django.db import connection
# from extra_data.models import PurchaseGroup,SaleGroup,HS,Item,CustomsGroup,Brand,ItemWeight
# from inquiry.models import PriceInquiryResult
# from micmod_base.base import Currency
#
# class AttributeDict(dict):
#     def __getattr__(self, name):
#         return self[name]
#
# if __name__ == "__main__":
#     ddd = {"a":1567567.000,"b":"sdafsdgd"}
#     dd = AttributeDict(ddd)
#     mstr = "{d.a:,.0f}--{d.b:4}"
#     st = mstr.format(d=dd)
#     objs = PriceInquiryResult.objects.filter(purchase_group="Assembly Machine")
#     print(objs)