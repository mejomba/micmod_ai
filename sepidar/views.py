import string

import django.views.defaults
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.humanize.templatetags.humanize import intcomma
from django.db.models import Q
from django.http import JsonResponse
from django.views import View
from django.views.generic.list import ListView
from django.urls import reverse_lazy, reverse

import sepidar.models
from core.views import BaseView
from micmod_base.base import is_valid
from .froms import DeviceForm
from .models import Dl, Item, Device, APILogs, InventoryPurchaseInvoice
from jalali_date.templatetags.jalali_tags import to_jalali
from django.shortcuts import render, redirect
# from tools.google_sheet import price_wb
from micmod_base.base import QTYDis,PMDisY,PMDisR
from accounts.templatetags.accounts_tag import has_group, has_groups
from translator import get_text as _

from ajax_datatable.views import AjaxDatatableView
from django.contrib.auth.models import Permission
from .scripts.sepidar_classes import Urls
import re


from extra_data.models import Customer
# Create your views here.

def test_get(request):
    device = Device.objects.all().first()
    res = APILogs.new_call(device=device,url=Urls.get_customer.url.format(500),method=Urls.get_customers.method)
    print(res)
    return JsonResponse(res[0], safe=False)


def get_customers(request):
    q = request.GET.get('q', None)
    obj = {}
    count = 0
    if q:
      Dls = Dl.get_list(q)
      obj['items'] = []
      for dl in Dls:
          item = {}
          item['id'] = dl.sepidar_dl_code
          item['text'] = dl.title
          item['pid'] = dl.sepidar_party_id
          item['sepidar_party_id'] = dl.sepidar_party_id
          obj['items'].append(item)
          count += 1
    obj['total_count'] = count
    return JsonResponse(obj, safe=False)

def get_customers_for_shop(request):
    q = request.GET.get('q', None)
    obj = {}
    count = 0
    if q:

        if q.isdigit():
            customer_filter = Q(sepidar_dl_id__icontains=q) | Q(sepidar_dl_code__icontains=q) | Q(
                sepidar_party_id__icontains=q)| Q(shop_id__icontains=q)
        else:
            customer_filter = Q(title__icontains=q) | Q(name__icontains=q) | Q(last_name__icontains=q)
        res = Customer.objects.filter(customer_filter).filter(active=True)
        obj['items'] = []
        for dl in res:
            item = {}
            item['id'] = dl.sepidar_dl_code
            item['text'] = dl.title
            item['pid'] = dl.sepidar_party_id
            item['sepidar_party_id'] = dl.sepidar_party_id
            obj['items'].append(item)
            count += 1
    obj['total_count'] = count
    return JsonResponse(obj, safe=False)
    # q = request.GET.get('q', None)
    # map_table = {
    #     '': '',
    #     '': '',
    #     '': '',
    #     '': '',
    #     '': '',
    #     '': '',
    #     '': '',
    #     '': '',
    # }
    # obj = {}
    # count = 0
    # from extra_data.models import Customer
    # if q:
    #     if q.isdigit():
    #         from django.db.models.functions import Cast
    #         from django.db.models import CharField
    #         customer_filter = Q(sepidar_dl_id_str__icontains=q) | Q(sepidar_dl_code_str__icontains=q) | Q(sepidar_party_id_str__icontains=q)
    #         Dls = Customer.objects.annotate(sepidar_dl_id_str=Cast('sepidar_dl_id', CharField()))\
    #             .annotate(sepidar_dl_code_str=Cast('sepidar_dl_code', CharField()))\
    #             .annotate(sepidar_party_id_str=Cast('sepidar_party_id', CharField())).filter(customer_filter)
    #     else:
    #         customer_filter = Q(title__icontains=q) | Q(name__icontains=q) | Q(last_name__icontains=q)
    #         Dls = Customer.objects.filter(customer_filter)
    #     obj['items'] = []
    #     for dl in Dls:
    #         item = {}
    #         item['id'] = dl.sepidar_dl_code or 1
    #         item['text'] = dl.title or 1
    #         item['pid'] = dl.sepidar_party_id or 1
    #         item['sepidar_party_id'] = dl.sepidar_party_id or 1
    #         obj['items'].append(item)
    #         count += 1
    # obj['total_count'] = count
    # return JsonResponse(obj, safe=False)

def get_customers_from_pg(request):
    from extra_data.models import Customer
    q = request.GET.get('q', None)
    f = Q(sepidar_party_id=q) | Q(name=q) | Q
    Customer.objects.filter()
    reps = [["ي", "ی"], ["ك", "ک"]]
    obj = {}
    count = 0
    if q:
      for rep in reps:
        q = q.replace(rep[1],rep[0])
      Dls = Dl.get_list(q)
      obj['items']=[]
      for dl in Dls:
          item = {}
          item['id'] = dl.code
          item['text'] = dl.name
          item['pid'] = dl.PartyId
          item['sepidar_party_id'] = dl.PartyId
          obj['items'].append(item)
          count += 1
    obj['total_count'] = count
    return JsonResponse(obj,safe=False)

def get_items(request):
    ...
    # q = request.GET.get('q', None)
    # party_id = request.GET.get('party_id', None)
    # reps = [["ي", "ی"], ["ك", "ک"]]
    # obj = {}
    # count = 0
    # if q:
    #     for rep in reps:
    #         q = q.replace(rep[1], rep[0])
    #     items = Item.get_items(q,party_id)
    #     obj['items'] = []
    #     for item_ in items:
    #         item = {}
    #         try:
    #             item['id'] = item_.code
    #             item['itemid'] = item_.itemid
    #             item['text'] = item_.title
    #             item['f_date_cust'] = to_jalali(item_.f_date_cust, "%Y-%m-%d")
    #             item['f_fee_cust'] = (item_.f_fee_cust) #if is_valid(item_.f_fee_cust) else ''
    #             item['f_qty_cust'] = (item_.f_qty_cust) #if is_valid(item_.f_qty_cust) else ''
    #             item['q_date_cust'] = to_jalali(item_.quotation_date, "%Y-%m-%d")
    #             item['q_fee_cust'] = (item_.quotation_fee)  # if is_valid(item_.f_fee_cust) else ''
    #             item['q_qty_cust'] = (item_.quotation_qty)  # if is_valid(item_.f_fee_cust) else ''
    #             item['f_qty_all'] = (item_.f_qty_all) #if is_valid(item_.f_qty_all) else ''
    #             # item['stock_str'] = item_.stock_str
    #             item['min_price'] = (item_.min_price) #if is_valid(item_.avg_price) else ''
    #             item['avg_price'] = (item_.avg_price) #if is_valid(item_.avg_price) else ''
    #             item['max_price'] = (item_.max_price) #if is_valid(item_.avg_price) else ''
    #             item['stock_qty'] = (item_.stock_qty) #if is_valid(item_.stock_qty) else ''
    #             item['stock_qty_res'] = (item_.stock_res_qty) #if is_valid(item_.stock_qty) else ''
    #             # sh_price = price_wb.get_sheet_price(item_.code)
    #             item['week1'] = sh_price['p']['week1'] if sh_price['p'] else None
    #             item['week2'] = sh_price['p']['week2'] if sh_price['p'] else None
    #             item['week3'] = sh_price['p']['week3'] if sh_price['p'] else None
    #             #print('price_loaded')
    #             item['date'] = to_jalali(sh_price['p'].get('date', None), "%Y-%m-%d") if sh_price['p'] else None
    #             item['m_price'] = sh_price['market']['price'] if sh_price['market'] else None
    #             item['m_date'] = to_jalali(sh_price['market']['date'], "%Y-%m-%d") if sh_price['market'] else None
    #             item['yuan_rate'] = sh_price['yuan_rate'] if sh_price else 0
    #             item['QTYDis'] = QTYDis
    #             item['PMDisY'] = PMDisY
    #             item['PMDisR'] = PMDisR
    #             obj['items'].append(item)
    #             count += 1
    #         except Exception as e:
    #             print(str(e))


    # obj['total_count'] = count
    # return JsonResponse(obj, safe=False)


def get_items2(request):
    ...
    # q = request.GET.get('q', None)
    # party_id = request.GET.get('party_id', None)
    # reps = [["ي", "ی"], ["ك", "ک"]]
    # obj = {}
    # count = 0
    # if q:
    #     for rep in reps:
    #         q = q.replace(rep[1], rep[0])
    #     items = Item.get_items(q,party_id)
    #     obj['items'] = []
    #     for item_ in items:
    #         item = {}
    #         try:
    #             item['itemid'] = item_.itemid
    #             item['goods_code'] = item_.code, False
    #             item['goods_name'] = item_.title, False
    #             item['last_sale'] = to_jalali(item_.f_date_cust, "%Y-%m-%d"), True
    #             item['last_price'] = (item_.f_fee_cust), False
    #             item['f_qty_cust'] = (item_.f_qty_cust), False
    #             item['q_last_sale'] = to_jalali(item_.quotation_date, "%Y-%m-%d"), True
    #             item['q_last_price'] = (item_.quotation_fee), False
    #             item['q_total_sales'] = (item_.quotation_qty), False
    #             item['avg_count'] = (item_.f_qty_all), False
    #             item['min_price'] = (item_.min_price), False
    #             item['avg_price'] = (item_.avg_price), False
    #             item['max_price'] = (item_.max_price), False
    #             item['stock_amount'] = (item_.stock_qty), False
    #             item['stock_amount_res'] = (item_.stock_res_qty), False
    #             sh_price = price_wb.get_sheet_price(item_.code)
    #             item['goods_price_sheet1'] = sh_price['p']['week1'] if sh_price['p'] else None, False
    #             item['goods_price_sheet2'] = sh_price['p']['week2'] if sh_price['p'] else None, False
    #             item['goods_price_sheet3'] = sh_price['p']['week3'] if sh_price['p'] else None, False
    #             item['goods_sheet_date'] = to_jalali(sh_price['p'].get('date', None), "%Y-%m-%d") if sh_price[
    #                 'p'] else None, True
    #             item['goods_price_market'] = sh_price['market']['price'] if sh_price['market'] else None, False
    #             item['goods_market_date'] = to_jalali(sh_price['market']['date'], "%Y-%m-%d") if sh_price[
    #                 'market'] else None, True
    #             item['yuan_rate'] = sh_price['yuan_rate'] if sh_price else 0, False
    #             item['QTYDis'] = QTYDis, False
    #             item['PMDisY'] = PMDisY, False
    #             item['PMDisR'] = PMDisR, False
    #             obj['items'].append(item)
    #             count += 1
    #         except Exception as e:
    #             print(str(e))
    #
    #
    # obj['total_count'] = count
    # return JsonResponse(obj, safe=False)


def get_item(request):
    ...
    # q = request.GET.get('q', None)
    # party_id = request.GET.get('party_id', None)
    # reps = [["ي", "ی"], ["ك", "ک"]]
    # obj = {}
    # count = 0
    # if q:
    #     for rep in reps:
    #         q = q.replace(rep[1], rep[0])
    #     items = Item.get_item(q,party_id)
    #     obj['items'] = []
    #     for item_ in items:
    #         item = {}
    #         try:
    #             item['id'] = item_.code
    #             item['itemid'] = item_.itemid
    #             item['text'] = item_.title
    #             item['f_date_cust'] = to_jalali(item_.f_date_cust, "%Y-%m-%d")
    #             item['f_fee_cust'] = (item_.f_fee_cust) #if is_valid(item_.f_fee_cust) else ''
    #             item['f_qty_cust'] = (item_.f_qty_cust) #if is_valid(item_.f_qty_cust) else ''
    #             item['q_date_cust'] = to_jalali(item_.quotation_date, "%Y-%m-%d")
    #             item['q_fee_cust'] = (item_.quotation_fee)  # if is_valid(item_.f_fee_cust) else ''
    #             item['q_qty_cust'] = (item_.quotation_qty)  # if is_valid(item_.f_fee_cust) else ''
    #             item['f_qty_all'] = (item_.f_qty_all) #if is_valid(item_.f_qty_all) else ''
    #             # item['stock_str'] = item_.stock_str
    #             item['min_price'] = (item_.min_price) #if is_valid(item_.avg_price) else ''
    #             item['avg_price'] = (item_.avg_price) #if is_valid(item_.avg_price) else ''
    #             item['max_price'] = (item_.max_price) #if is_valid(item_.avg_price) else ''
    #             item['stock_qty'] = (item_.stock_qty) #if is_valid(item_.stock_qty) else ''
    #             item['stock_qty_res'] = (item_.stock_res_qty) #if is_valid(item_.stock_qty) else ''
    #             sh_price = price_wb.get_sheet_price(item_.code)
    #             item['week1'] = sh_price['p']['week1'] if sh_price['p'] else None
    #             item['week2'] = sh_price['p']['week2'] if sh_price['p'] else None
    #             item['week3'] = sh_price['p']['week3'] if sh_price['p'] else None
    #             #print('price_loaded')
    #             item['date'] = to_jalali(sh_price['p'].get('date', None), "%Y-%m-%d") if sh_price['p'] else None
    #             item['m_price'] = sh_price['market']['price'] if sh_price['market'] else None
    #             item['m_date'] = to_jalali(sh_price['market']['date'], "%Y-%m-%d") if sh_price['market'] else None
    #             item['yuan_rate'] = sh_price['yuan_rate'] if sh_price else 0
    #             item['QTYDis'] = QTYDis
    #             item['PMDisY'] = PMDisY
    #             item['PMDisR'] = PMDisR
    #             obj['items'].append(item)
    #             count += 1
    #         except Exception as e:
    #             print(str(e))
    #
    #
    # obj['total_count'] = count
    # return JsonResponse(obj, safe=False)


def get_item2(request):
    ...
    # q = request.GET.get('q', None)
    # party_id = request.GET.get('party_id', None)
    # reps = [["ي", "ی"], ["ك", "ک"]]
    # obj = {}
    # count = 0
    # if q:
    #     for rep in reps:
    #         q = q.replace(rep[1], rep[0])
    #     items = Item.get_items(q, party_id)
    #     obj['items'] = []
    #     for item_ in items:
    #         item = {}
    #         try:
    #             item['goods_code'] = item_.code
    #             item['goods_name'] = item_.title
    #             item['last_sale'] = to_jalali(item_.f_date_cust, "%Y-%m-%d")
    #             item['last_price'] = (item_.f_fee_cust)
    #             item['f_qty_cust'] = (item_.f_qty_cust)
    #             item['q_last_sale'] = to_jalali(item_.quotation_date, "%Y-%m-%d")
    #             item['q_last_price'] = (item_.quotation_fee)
    #             item['q_total_sales'] = (item_.quotation_qty)
    #             item['avg_count'] = (item_.f_qty_all)
    #             item['min_price'] = (item_.min_price)
    #             item['avg_price'] = (item_.avg_price)
    #             item['max_price'] = (item_.max_price)
    #             item['stock_amount'] = (item_.stock_qty)
    #             item['stock_amount_res'] = (item_.stock_res_qty)
    #             sh_price = price_wb.get_sheet_price(item_.code)
    #             item['goods_price_sheet1'] = sh_price['p']['week1'] if sh_price['p'] else None
    #             item['goods_price_sheet2'] = sh_price['p']['week2'] if sh_price['p'] else None
    #             item['goods_price_sheet3'] = sh_price['p']['week3'] if sh_price['p'] else None
    #             item['goods_sheet_date'] = to_jalali(sh_price['p'].get('date', None), "%Y-%m-%d") if sh_price['p'] else None
    #             item['goods_price_market'] = sh_price['market']['price'] if sh_price['market'] else None
    #             item['goods_market_date'] = to_jalali(sh_price['market']['date'], "%Y-%m-%d") if sh_price['market'] else None
    #             item['yuan_rate'] = sh_price['yuan_rate'] if sh_price else 0
    #             item['QTYDis'] = QTYDis
    #             item['PMDisY'] = PMDisY
    #             item['PMDisR'] = PMDisR
    #             obj['items'].append(item)
    #             count += 1
    #         except Exception as e:
    #             print(str(e))
    #
    #
    # obj['total_count'] = count
    # return JsonResponse(obj, safe=False)


class SuppliersAccountingList(LoginRequiredMixin,View):
    def get(self, request):
        if not has_groups(request.user,'trade_user,accounting_user'):
            return django.views.defaults.page_not_found(request,{},template_name="pages/pages-404.html")
        item_list = []
        mylist = (Dl.get_accounting_list(self.request.GET.get('q')))
        for item in mylist:
            if self.has_only_latin_letters(item.dl_title):
                item_list.append(item)
        # p = Paginator(quotations_record, 10)
        # page = request.GET.get('page')
        # if p == None:
        #    page = int(1)
        # page_obj = p.get_page(page)
        greeting = {}
        greeting['heading'] = ("سپیدار")
        greeting['pageview'] = ("گزارش مانده حساب های پرداختنی")
        greeting['list'] = item_list
        # greeting['page_obj'] = page_obj

        return render(request,'sepidar/suppliers_accounting.html',greeting)

    @staticmethod
    def has_only_latin_letters(m_str):
        char_set = string.printable
        return all((True if x in char_set else False for x in m_str))


class SalesHistory(LoginRequiredMixin, View):
    def get(self, requset):
        # if not has_groups(request.user,['trade_user','accounting_user']):
        #     return django.views.defaults.page_not_found(request,{},template_name="pages/pages-404.html")
        context = {}
        context['customer_code'] = requset.GET.get('customer_code',"")
        context['item_code'] = requset.GET.get('item_code',"")
        context['part'] = requset.GET.get('part',"")
        context['g_p'] = requset.GET.get('g_p',"")
        context['doc_type'] = requset.GET.get('doc_type',"")
        context['fisicalyearref'] = requset.GET.get('fisicalyearref')
        print(context)
        context['list'] = Dl.get_sales_history_list(self.request.GET)
        if context['list']:
            context['total_price'] = sum([(x.Fee*x.Quantity) for x in context['list']]) if len(context['list']) < 3000 else None
        return render(self.request,'sepidar/sales_history.html',context)


class BuyHistory(LoginRequiredMixin, View):
    def get(self, requset):
        # if not has_groups(request.user,['trade_user','accounting_user']):
        #     return django.views.defaults.page_not_found(request,{},template_name="pages/pages-404.html")
        context = {}
        context['customer_code'] = requset.GET.get('customer_code',"")
        context['item_code'] = requset.GET.get('item_code',"")
        context['part'] = requset.GET.get('part',"")
        context['g_p'] = requset.GET.get('g_p',"")
        context['doc_type'] = requset.GET.get('doc_type',"")
        print(context)
        context['list'] = InventoryPurchaseInvoice.get_buy_history_list(self.request.GET)
        return render(self.request,'sepidar/buy_history.html', context)


class MessageView(BaseView):
    form_class = DeviceForm
    # main_form = ReceiptCreateForm2
    model = Device
    # formset = inlineformset_factory(Receipt, ReceiptDetail, form=ReceiptDetailCreateForm2, extra=1, )
    # formset_model = ReceiptDetail
    # formset_form = ReceiptDetailCreateForm2
    template_name = 'sepidar/deivce_view.html'
    # formset_fk_field = 'receipt_id'
    # related_name_fk = 'receiptdetail_set'
    success_url = reverse_lazy('sepidar:device.list')

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs)


class DeviceList(ListView):
    template_name = 'sepidar/device_list.html'
    model = Device


class BaseList(AjaxDatatableView):
    model = None
    title = 'base_list'
    # initial_order = [["last_update_date", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sepidar/device_list.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'abstract_text', 'visible': True, 'title': _('abstract_text'), 'className': 'py-1 border'},
        {'name': 'text', 'visible': True, 'title': _('text'), 'className': 'py-1 border'},
        {'name': 'reply_to', 'visible': True, 'title': _('reply to'), 'className': 'py-1 border'},
        {'name': 'sender_type', 'visible': True, 'title': _('sender type'), 'className': 'py-1 border'},
        {'name': 'sender', 'visible': True, 'title': _('sender'), 'className': 'py-1 border'},
        {'name': 'automation_status', 'visible': True, 'title': _('automation status'), 'className': 'py-1 border'},
        {'name': 'id', 'visible': False, },
    ]

    def get_initial_queryset(self, request=None):
        return self.model.objects.all()
        # param = self.request.POST.get('q', 'all').strip('/')
        # if param == 'all':
        #     qs = self.model.objects.all()

    def customize_row(self, row, obj):
        row['abstract_text'] = '<a class="fw-bold" href="%s">%s</a>' % (
                      reverse('tlg:message.create_update', args=(obj.id,)),
                      obj.abstract_text if obj.abstract_text else '_'
                    )





