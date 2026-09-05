import datetime
import time
from decimal import Decimal

import requests
from django.core.cache import cache
from django.contrib.contenttypes.models import ContentType
from django.db.models.functions import Coalesce, Cast
from django.db.models.signals import post_save, m2m_changed
from django.utils import timezone
from django.contrib import messages
from ajax_datatable import AjaxDatatableView
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Sum, Case, When, F, DecimalField, ExpressionWrapper, OuterRef, Subquery, Min
from django.forms import inlineformset_factory
from django.http import JsonResponse, HttpResponseNotAllowed, HttpResponseBadRequest, Http404
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.views import View
from django.views.generic import DetailView
from jalali_date import datetime2jalali
from jalali_date.templatetags.jalali_tags import to_jalali
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from simple_history.models import HistoricalRecords

from comments.forms import CommentsForm
from core.exceptions import StockRefNotFoundError
from core.permissions import HasShopPermission
from extra_data.models import Item, CustomerAddress
from factor.cont import disable_all_signals
from factor.serializers import FactorSerializer
from inquiry.models import CurrencyAmount
from micmod_base.serializers import CustomerRequestSerializer
from notifications.models import Notification
from sepidar.api_call import SepidarApiCall
from sepidar.models import Dl
from services.product.api_call import ProductApiCall
from services.shop.api_call import ShopApiCall
from tools.const import WH_FACTOR_STATES
from translator import get_text as _

from core.views import BaseView, Base
from factor.forms import FactorModelForm, FactorItemFormset, FactorItemModelForm, DeliveryForm, \
    FACTOR_FIELDS_BY_PERMISSION, \
    FACTOR_ITEM_FIELDS_BY_PERMISSION, FactorItemForm, FactorEditForm, FactorItemInlineFormSetBase
from factor.models import Factor, FactorItem, Delivery, FactorItemSupplyLocation
from micmod_base.models import Quotation, QuotationItem, CustomerRequest
from tools.utils import to_jalali_date, show_error, timer, is_ajax, parse_number
import json
from datetime import datetime

from django.db.models import Q, Sum, Case, When, F, DecimalField, ExpressionWrapper, OuterRef, Subquery
from decimal import Decimal
from django.db.models.functions import Coalesce, Cast

from workflow.models import WorkFlow
from .services.supply import SupplyLocationService, attach_supply
from .services.supply_change_checker import SupplyChangeChecker


class FactorView(LoginRequiredMixin, BaseView):
    template_name = 'factor/factor.html'
    conflict_template_name = 'factor/partial/conflict_view.html'
    post_conflict_template_name = 'factor/partial/conflict_post_view.html'
    form_class = FactorModelForm
    model = Factor
    form_struct = {
        'form': FactorModelForm,
        'childes': [
            {
                'form': FactorItemFormset,
                'childes': [{}]
            },
        ]
    }
    flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json', 'Factor')
    has_flow = True
    has_formset = True
    wf_last_step_is_open = True
    formset_form = FactorItemFormset
    formset_model = FactorItem
    formset_fk_field = 'factoritem_set'
    related_name_fk = 'factoritem_set'

    allow_perms = [f'{model._meta.app_label}.view_{model._meta.model_name}',
                f'{model._meta.app_label}.add_{model._meta.model_name}',
                f'{model._meta.app_label}.change_{model._meta.model_name}',
                f'{model._meta.app_label}.delete_{model._meta.model_name}',
                f'{model._meta.app_label}.factor_send_or_delivery_{model._meta.model_name}'
                ]

    def after_sepidar_error(self):
        if 'next' in self.request.POST:
            self.object.last_work_flow = self.object.workflows.all().order_by('-id')[1]
            self.object.final_check = False
            self.object.extra_data.request = self.request
            self.object.save()
            self.object.workflows.all().order_by('id').last().delete()
        else:
            self.object.final_check = False
            self.object.extra_data.request = self.request
            self.object.save()

    def send_factor_to_sepidar(self):
        customer = self.object.q.customer_party_id
        if not customer.active:
            messages.error(self.request, f'مشتری در پرتال غیر فعال است.')
            self.after_sepidar_error()
            return

        res = SepidarApiCall.get_party(customer.sepidar_party_id)
        if not res.get('iscustomer'):
            messages.error(self.request, f'مشتری در سپیدار فعال نیست.')
            self.after_sepidar_error()
            return
        try:
            res = SepidarApiCall.factor_to_sepidar(self.object, self.request)
            if 'errors' not in res:
                self.object.sepidar_number = res.get('number')
                self.object.sepidar_id = res.get('invoiceid')

                self.object.sepidar_inventory_delivery_number = res.get('sepidar_inventory_delivery_number')
                self.object.sepidar_inventory_delivery_id = res.get('sepidar_inventory_delivery_id')
                self.object.sepidar_voucher_number = res.get('sepidar_voucher_number')
                self.object.sepidar_voucher_id = res.get('sepidar_voucher_id')
                self.object.fiscalyearref = settings.SEPIDAR_CONST_DATA.get('fiscalyearref')

                self.object.extra_data.request = self.request
                self.object.final_check = True
                self.object.save()

                """ save sepidar InvoiceItemID for fi """
                fis = list(self.object.factoritem_set.all())
                lookup = {(d["quantity"], d["itemref"]): d["invoiceitemid"] for d in res.get('invoice_items')}

                for item in fis:
                    key = (item.quantity, item.goods_code.sepidar_id_0)
                    if key in lookup:
                        item.sepidar_id = lookup[key]

                FactorItem.objects.bulk_update(fis, ["sepidar_id"])
                messages.success(self.request, f'فاکتور به سپیدار ارسال شد، کد: {self.object.sepidar_number}')

                shop_buy_factor_pk = ShopApiCall.create_shop_buy_factor(self.object, request=self.request)
                if shop_buy_factor_pk:
                    self.object.shop_buy_factor_id = shop_buy_factor_pk
                    self.object.extra_data.request = self.request
                    self.object.save()
                    messages.success(self.request, f'فاکتور خرید برای شاپ ایجاد شد کد: {shop_buy_factor_pk}')
                return
            else:
                self.after_sepidar_error()
                messages.error(self.request, f'خطا در ارسال فاکتور به سپیدار')
                messages.error(self.request, f"{res['errors']}")
                return
        except StockRefNotFoundError as e:
            self.after_sepidar_error()
            messages.error(self.request, f'{e}')
        except Exception as e:
            self.after_sepidar_error()
            messages.error(self.request, f'{e}')

    def save_new_address(self):
        address = self.request.POST.get('new_address')
        customer = self.request.POST.get('customer')
        if address and customer:
            obj = CustomerAddress.objects.create(address=address, customer_id=customer)

            self.request.POST._mutable = True
            self.request.POST['address'] = obj.pk
            self.request.POST._mutable = False

            self.object.extra_data.request = self.request
            self.object.address = obj
            self.object.save()
            return obj

    def get_success_url(self):
        return reverse_lazy('factor:factor.view', kwargs={'pk': self.object.pk})

    def check_last_update(self):
        return True
        fis_last_update = (json.loads(self.request.POST.get('fis_last_update_datetime', "{}"))
                           or self.request.GET.get('fis_last_update_datetime'))
        f_last_update = (self.request.POST.get('last_update_datetime')
                         or self.request.GET.get('last_update_datetime').replace(' ', '+'))
        if is_ajax(self.request):
            fis_last_update = json.loads(fis_last_update)

        if f_last_update and self.object.last_update_date.replace(microsecond=0) != datetime.fromisoformat(f_last_update).replace(microsecond=0):
            return False

        for fi in self.object.factoritem_set.all():
            if fi_last_update := fis_last_update.get(str(fi.pk)):
                fi_last_update = fi_last_update.replace(' ', '+')
                if datetime.fromisoformat(fi_last_update).replace(microsecond=0) != fi.last_update_date.replace(microsecond=0):
                    return False
        return True

    def get(self, request, *args, **kwargs):
        if is_ajax(self.request):
            if not self.check_last_update():
                html = render_to_string(self.conflict_template_name, {'conflict': True, 'obj': self.object})
                return JsonResponse({'res': html}, safe=False)
            else:
                return JsonResponse({'res': ''}, safe=False)
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if not self.check_last_update():
            return render(request, self.post_conflict_template_name, {'conflict': True, 'obj': self.object})
        if self.object is None:
            pass
            # import_customers_from_sepidar(extra_data={"creator_user_id": 1, "editor_user_id": 1})

        if 'new_address' in self.request.POST:
            self.save_new_address()

        try:
            condition = self.object and self.object.last_work_flow.current_state_name == 'چک نهایی' and 'back' in self.request.POST
        except Exception as e:
            condition = False
        if condition:
            self.object.collecting_end_time = None
            self.object.extra_data.request = self.request
            self.object.save()
        return super().post(request, *args, **kwargs)

    def disconnect_history(self, model):
        for (receiver_key, receiver) in post_save.receivers:
            if hasattr(receiver, "__self__") and isinstance(receiver.__self__, HistoricalRecords):
                hist_obj = receiver.__self__
                if 'factor' in str(hist_obj.cls):
                    post_save.disconnect(receiver, sender=model)

        # for receiver in m2m_changed.receivers[:]:
        #     if "update_change_reason" in str(receiver) or "update_change_reason" in str(receiver[1]):
        #         m2m_changed.disconnect(receiver[1], sender=model)

    def form_valid(self, form):
        self.disconnect_history(Factor)
        self.disconnect_history(FactorItem)

        try:
            condition = self.object and self.object.last_work_flow.current_state_name == 'جمع‌‌آوری' and 'next' in self.request.POST
        except Exception as e:
            condition = False
        if condition:
            self.form.instance.collecting_end_time = timezone.now()
        obj_before_save = self.object
        res = super().form_valid(form)

        if 'next' in self.request.POST and not self.object.is_need_sales_admin_confirmation() and self.object.is_all_supplied and self.state_index == 0:
            # "بدون نیاز به تایید مدیر فروش" and "بدون نیاز به تامین کالا" and "در مرحله پیش نویس هستیم" and 'next':
            next = "مرحله تایید مدیر فروش"
            wf_data = {
                'state': self.flow_config.get('flow_state_list')[self.state_index + 1],
                'wf_description': 'بدون نیاز به تایید مدیر فروش',
                'from_user': self.request.user,
                'to_user': get_user_model().objects.filter(groups__name='wh_admin').last(),
                'current_state_name': self.flow_config.get('flow_state_list')[self.state_index + 2],
                'object_id': self.object.pk,
            }
            self.save_flow(self.request, **wf_data)

        elif 'next' in self.request.POST and not self.object.is_need_sales_admin_confirmation() and not self.object.is_all_supplied and self.state_index == 0:
            # "بدون نیاز به تایید مدیر فروش" and "در مرحله پیش نویس هستیم" and "next": و کالا تامیین نشده
            next = "تاید مدیر فروش"
            wf_data = {
                'state': self.flow_config.get('flow_state_list')[self.state_index + 1],
                'wf_description': 'بدون نیاز به تایید مدیر فروش',
                'from_user': self.request.user,
                'to_user': self.object.creator_user, # get_user_model().objects.filter(groups__name='wh_admin').first(),
                'current_state_name': self.flow_config.get('flow_state_list')[self.state_index + 2],
                'object_id': self.object.pk,
            }
            self.save_flow(self.request, **wf_data)

        if 'back' in self.request.POST and not self.object.is_need_sales_admin_confirmation() and self.state_index == 2:
            # "بدون نیاز به تایید مدیر فروش" and "بدون نیاز به تامین کالا" and "در مرحله تخصیص کارشناس انبار هستیم" and 'back':
            back = "مرحله تایید مدیر فروش"
            wf_data = {
                'wf_status': 2,  # back
                'state': self.flow_config.get('flow_state_list')[self.state_index - 1],
                'wf_description': 'کالا موجود در انبار',
                'from_user': self.request.user,
                'to_user': self.object.creator_user, # get_user_model().objects.filter(groups__name='wh_admin').first(),
                'current_state_name': self.flow_config.get('flow_state_list')[self.state_index - 2],
                'object_id': self.object.pk,
            }
            self.save_flow(self.request, **wf_data)

        # self.reconnect_history(Factor)
        # self.reconnect_history(FactorItem)
        self.object.need_financial_approval = True
        if obj_before_save and obj_before_save.accounting_confirm and self.state_index > 1:
            self.object.accounting_confirm = True
        if obj_before_save and obj_before_save.is_official and self.state_index > 1:
            self.object.is_official = True
        if obj_before_save and obj_before_save.official_factor_for_this_factor:
            self.object.official_factor_for_this_factor = obj_before_save.official_factor_for_this_factor

        customer_party_id = getattr(self.object, 'customer_party_id', None) or self.object.q.customer_party_id
        if not self.object.notify_number and customer_party_id.customerexpert_set.filter(send_notification=True, phone__icontains='09').exists():
            self.object.notify_number = customer_party_id.customerexpert_set.filter(send_notification=True, phone__icontains='09').last().phone

        self.object.save()
        if 'send_factor_to_sepidar' in self.request.POST:
            self.send_factor_to_sepidar()

        if 'create_shop_buy_factor' in self.request.POST:
            shop_buy_factor_pk = ShopApiCall.create_shop_buy_factor(self.object, request=self.request)
            if shop_buy_factor_pk:
                self.object.shop_buy_factor_id = shop_buy_factor_pk
                self.object.extra_data.request = self.request
                self.object.save()
                messages.success(self.request, f'فاکتور خرید برای شاپ ایجاد شد کد: {shop_buy_factor_pk}')

        shop_document_id = ShopApiCall.create_or_update_shop_document(self.object)
        self.object.shop_document_id = shop_document_id
        self.object.extra_data.request = self.request
        self.object.save()
        return res

    @timer
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.object:
            context['allow_next'] = False
        context['f_warning'] = []
        if not self.object:
            return context

        customer_party_id = getattr(self.object, 'customer_party_id', None) or self.object.q.customer_party_id
        if not self.object.notify_number and customer_party_id.customerexpert_set.filter(send_notification=True, phone__icontains='09').exists():
            self.object.notify_number = customer_party_id.customerexpert_set.filter(send_notification=True, phone__icontains='09').last().phone

        Notification.notify_customer_for_factor(self.object, self.request)

        last_update_datetime = self.object.last_update_date.isoformat() if self.object else ''
        context['last_update_datetime'] = last_update_datetime
        fi_list = list(self.object.factoritem_set.all())
        fis = {fi.pk: fi.last_update_date.isoformat() for fi in fi_list} if self.object else {}
        context['fis_last_update_datetime'] = json.dumps(fis)
        context['section_id'] = 'factor'
        context['is_need_sales_admin_confirmation'] = self.object.is_need_sales_admin_confirmation() and self.state_index < 2
        context['form'].enable = True if self.wf_access else False
        context['update'] = True if self.object else False
        context['obj'] = self.object
        context['quotation'] = self.object.q if self.object else None
        context['notify_number'] = self.object.notify_number
        qis = self.object.q.quotation.select_related('goods_code_fk') if self.object else None
        FactorItemFormset.extra = context['quotation'].quotation.count() - self.object.factoritem_set.count() if self.object else 0
        fis_qs = FactorItem.objects.filter(factor=self.object)
        if customer_party_id.pk == 2691:  # 2691 is MICMOD SHOP pk in portal extra_data.customer
            skus = ','.join(map(str, fis_qs.values_list('goods_code__id', flat=True)))
            product_map = ProductApiCall.get_product_by_skus(skus, response_function='products_map')
            cache_key = f'{self.request.user.username}__factor__{self.object.pk}'
            cache.set(cache_key, product_map, 6)
        context['form_s'] = FactorItemFormset(instance=self.object, form_kwargs={
                                                  "constraint": {
                                                      "wf_access": self.wf_access,
                                                      'form_state': self.state_index,
                                                      'form_state_name': self.flow_config.get('flow_state_list')[self.state_index],
                                                      'request': self.request,
                                                      'form_constraint': self.flow_config.get("flow_form_constraint"),
                                                      'formset_constraint': self.flow_config.get('flow_formset_constraint')
                                                      }
                                              },
                                              queryset=fis_qs)

        exclude_qi = set()
        context['factoritem_qi_pair'] = []

        ''' the for loop get 2 second of execution time for 30 rows '''

        for factor_item_form in context['form_s'].forms:
            for qi in qis:
                factor_item_form_instance_pk = factor_item_form.instance.pk
                if factor_item_form_instance_pk:
                    exclude_qi.add(factor_item_form.instance.qi.pk)
                if factor_item_form_instance_pk and factor_item_form.instance.qi.pk == qi.pk:
                    if qi.is_over:
                        """(qi is_over, factor item)"""
                        context['factoritem_qi_pair'].append((qi, factor_item_form, False,
                                                              qi.goods_code_fk.appearance_or_real_part_number_(customer=qi.quotation.customer_party_id),
                                                              qi.goods_code_fk.part_number != qi.goods_code_fk.appearance_or_real_part_number(qi.quotation.customer_party_id))
                                                             )
                        break
                    else:
                        """(qi, factor item)"""
                        context['factoritem_qi_pair'].append((qi, factor_item_form, False,
                                                              qi.goods_code_fk.appearance_or_real_part_number_(customer=qi.quotation.customer_party_id),
                                                              qi.goods_code_fk.part_number != qi.goods_code_fk.appearance_or_real_part_number(qi.quotation.customer_party_id))
                                                             )
                        break
        exclude_qi_qs = qis.filter(~Q(id__in=exclude_qi))
        empty_pair = [(qi, context['form_s'][-1], True if idx == 0 else False,
                       qi.goods_code_fk.appearance_or_real_part_number_(customer=qi.quotation.customer_party_id),
                       qi.goods_code_fk.part_number != qi.goods_code_fk.appearance_or_real_part_number(qi.quotation.customer_party_id)) for idx, qi in enumerate(exclude_qi_qs)]
        context['factoritem_qi_pair'].extend(empty_pair)


        if self.object:
            self.object.created_date = datetime2jalali(self.object.created_date).strftime('%y/%m/%d-%H:%M') if self.object.created_date else None
            self.object.last_update_date = datetime2jalali(self.object.last_update_date).strftime('%y/%m/%d-%H:%M') if self.object.last_update_date else None
            self.object.collecting_start_time = datetime2jalali(self.object.collecting_start_time).strftime('%y/%m/%d-%H:%M') if self.object.collecting_start_time else None
        context['data'] = self.object
        context['app_name'] = self.request.resolver_match.app_name
        context['submit_copy'] = False

        # طبق صورت جلسه فاکتور اگه نیاز به تایید مالی باشد اما تایید مالی انجام نشده باشد اجازه عبور از مرحله جمع آوری ندارد
        if self.object and self.state_index == 4 and (self.object.need_financial_approval and not self.object.accounting_confirm):
            context['f_warning'].append('نیاز به تایید مالی دارد.')
            context['allow_next'] = False

        if self.object and self.state_index == 5 and not self.object.sepidar_id:
            context['allow_next'] = False
            context['f_warning'].append('فاکتور به سپیدار ارسال نشده')

        context['is_all_supplied'] = self.object.is_all_supplied

        if self.object:
            if self.object and self.state_index >= 0 and not context['is_all_supplied']:
                context['f_warning'].append('سفارش در راه دارد یا تمام کالاها در انبار موجود نیست')
                if self.state_index == 2:
                    context['allow_next'] = False

            if self.state_index == 6 and not self.object.files.filter(group=3).exists():
                context['allow_next'] = False
                context['f_warning'].append('اسناد تحویل آپلود نشده است')

            if self.object.sepidar_id:
                context['allow_back'] = False
                context['f_warning'].append('فاکتوری که به سپیدار ارسال شده امکان عودت ندارد')

            for fi in fi_list:
                if fi.price == 0:
                    context['f_warning'].append('قیمت برخی از ردیف های فاکتور مشخص نشده')
                    if self.state_index == 4:
                        context['allow_next'] = False
        return context


def search_factor_view(request, *args, **kwargs):
    q = request.GET.get('q')
    search_by = request.GET.get('search_by')
    search_by = json.loads(search_by)
    q_int = -1
    q_str = ''
    if q.isdigit():
        q_int = int(q)
    q_str = q
    q_filter = Q()
    q_required = {'cancel': False, "is_deleted": False}
    for s in search_by:
        if s == 'search_customer':
            q_filter |= Q(customer_party_id__title__icontains=q_str)
        if s == 'search_id':
            q_filter |= Q(pk=q_int)
        if s == 'search_marketer':
            q_filter |= Q(last_work_flow__creator_user__username__icontains=q_str)
        if s == 'search_sepidar_id':
            q_filter |= Q(sepidar_number__icontains=q_int)
        if s == 'search_sku':
            q_filter |= Q(quotation__goods_code_fk__sku__iexact=q_str)
        if s == 'search_part_number':
            q_filter |= Q(quotation__goods_code_fk__part_number__icontains=q_str)
    q_filter &= Q(last_work_flow__current_state_name='مرحله نهایی')
    if not search_by:
        q_filter = Q(last_work_flow__current_state_name='مرحله نهایی') & \
                   (Q(customer_party_id__title__icontains=q_str) | \
                   Q(customer_party_id__sepidar_dl_id__icontains=q_int) | \
                   Q(customer_code__icontains=q_str) | Q(sepidar_number__icontains=q_int) | \
                   Q(customer_party_id__sepidar_dl_code__icontains=q_int) | Q(customer_party_id__sepidar_party_id__icontains=int) | \
                   Q(pk=q_int) | Q(quotation__goods_code_fk__sku__icontains=q_str) | Q(last_work_flow__creator_user__username__icontains=q_str))
    if 'search_id' in search_by and len(search_by) == 1:  # 1403.12.11 آقای حاجی نژاد گفتن اگر شناسه پیش فاکتور را زد بدون در نظر گرفتن مراحل همه پیش فاکتور ها را نمایش دهد
        quotations = Quotation.objects.get_access_object(request.user, lst=False).filter(pk=q_int, **q_required).order_by('-id').distinct()
    else:
        quotations = Quotation.objects.get_access_object(request.user, lst=False).filter(q_filter, **q_required).order_by('-id').distinct()
    # quotations = Quotation.objects.get_access_object(request.user, lst=False).filter(q_filter, **q_required).order_by('-id').distinct()
    res = dict()
    res['items'] = []
    total_count = 0
    for total_count, q in enumerate(quotations, 1):
        item = dict()
        item['id'] = q.pk
        item['customer_title'] = q.customer_party_id.title if q.customer_party_id else '-'
        item['customer_party_id'] = q.customer_party_id.sepidar_dl_code if q.customer_party_id else '-'
        item['quotation_id'] = q.pk
        item['row_count'] = q.quotation.all().count()
        item['last_work_flow_user'] = q.last_work_flow.creator_user.username if q.last_work_flow and q.last_work_flow.creator_user else '-'
        item['last_work_flow_state'] = q.last_work_flow.current_state_name if q.last_work_flow else '-'
        item['expiration_date'] = to_jalali_date(q.expiration_date)
        item['sale_type'] = q.sale_type.title
        item['payment_method'] = q.payment_method
        item['is_official'] = q.is_official
        res['items'].append(item)
    else:
        res['total_count'] = total_count
    return JsonResponse(res)


def get_quotation_items_for_factor(request, pk, *args, **kwargs):
    from workflow.forms import WorkFlowModelForm
    flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json', 'Factor')
    quotation = Quotation.objects.filter(pk=pk).first()
    qis = QuotationItem.objects.filter(quotation_id=pk).select_related('goods_code_fk', 'quotation')
    form = FactorModelForm(instance=quotation, initial={
                                                  "constraint": {
                                                      "wf_access": True,
                                                      'form_state': 0,
                                                      'request': request,
                                                      'form_constraint': flow_config.get("flow_form_constraint"),
                                                      'formset_constraint': flow_config.get('flow_formset_constraint')
                                                      }
                                              })
    FactorItemFormset.extra = quotation.quotation.count()
    form_s = FactorItemFormset()
    context = {'quotation': quotation, 'form': form, 'form_s': form_s, 'factoritem_qi_pair': [], 'request': request}

    empty_pair = [(qi, context['form_s'][-1], True if idx == 0 else False,
                   qi.goods_code_fk.appearance_or_real_part_number_(customer=qi.quotation.customer_party_id),
                   qi.goods_code_fk.part_number != qi.goods_code_fk.appearance_or_real_part_number(qi.quotation.customer_party_id)) for idx, qi in enumerate(qis)]
    empty_pair.sort(key=lambda x: x[0].is_over)
    context['factoritem_qi_pair'] = empty_pair
    context['flow_state_index'] = 0
    context['flow_state_list'] = flow_config.get('flow_state_list')
    context['flow_state_list'].append('مرحله نهایی')
    """if flow object don't exist select user from group (normally for create step)"""
    group = flow_config.get('flow_users_groups')[1][0]
    flow_belong_to_group = WorkFlowModelForm._meta.model.objects.filter(belong_to_group=group)
    user_list = get_user_model().objects.filter(groups__name__in=[group]).distinct().order_by('id')
    if flow_belong_to_group:
        last_wf_user = flow_belong_to_group.order_by('id').last().from_user
        next_users = user_list.filter(id__gt=last_wf_user.id).order_by('id')
        if next_users:
            to_user = next_users.first()
        else:
            to_user = user_list.first()
    else:
        to_user = user_list.first()
    context['workflow_form'] = WorkFlowModelForm(
        content_type_model=Factor,
        initial={
                    'wf_access': True,
                    'from_user': None,
                    'to_user': to_user, #self.get_flow_user(flow_user_groups[self.state_index + 1]), #request.user.__class__.objects.get(pk=59), #._meta.model.objects.get(pk=21),
                    'state': 'پیش‌نویس',
                    'state_index': 0,
                    'belong_to_group': 'sales_user',
                    'action': 'create',
                    'deadline': None,
                    'flow_config': flow_config,
                    'create': True
                },
        current_user=request.user,
    )

    html = render_to_string('factor/factor_item.html', context)
    return JsonResponse({'res': html})


class FactorsList(LoginRequiredMixin, View):
    def get(self, request):
        q = self.request.GET.get('q')
        factors = Factor.objects.all()

        greeting = {}
        greeting['heading'] = _("factor")
        greeting['pageview'] = _("factor")
        greeting['factor'] = factors

        return render(request, 'factor/partial/list_datatable.html', greeting)


class FactorListDatatable(AjaxDatatableView):
    model = Factor
    title = 'currency_list'
    initial_order = [["id", "desc"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cols = self.base_cols()

    def get_column_defs(self, request):
        if self.request.user.is_superuser:
            self.wh_column_defs(request)
            self.sales_column_defs(request)

        if self.request.user.base_group == 'wh':
            self.wh_column_defs(request)
        elif self.request.user.base_group == 'sales':
            self.sales_column_defs(request)
        elif self.request.user.base_group == 'office':
            self.office_column_defs(request)
        elif self.request.user.base_group == 'accounting':
            self.accounting_column_defs(request)
        else:
            self.cols.append({'name': 'q', 'visible': True, 'title': _('quotation'), 'lookup_field': '__pk__icontains', 'searchable': True, 'className': 'border'})
            self.cols.append({'name': 'q__payment_method', 'visible': True, 'title': _('روش پرداخت'), 'lookup_field': '__icontains', 'className': 'border'})
            self.cols.append({'name': 'sale_type', 'title': _('sale_type'), 'visible': True, 'searchable': False, 'orderable': True, 'lookup_field': '__title__icontains', 'className': 'border'},)
            self.cols.append({'name': 'self_discount', 'title': 'تخفیف', 'visible': True, 'orderable': True, 'searchable': True, 'className': 'border'},)
            self.cols.append({'name': 'delivery_time', 'visible': True, 'searchable': True, 'title': _('delivery_time'), 'orderable': True, 'lookup_field': '__icontains', 'className': 'border'},)
            self.cols.append({'name': 'is_official', 'title': _('is_official'), 'visible': True, 'searchable': True, 'orderable': True, 'className': 'border'},)
            self.cols.append({'name': 'official_value', 'title': _('official_value'), 'visible': True, 'orderable': True, 'searchable': True, 'className': 'border'},)

        self.remove_duplicate_col()
        return self.cols

    def get_initial_queryset(self, request=None):
        q = request.POST.get('q')
        qs = self.model.get_qs(self.request, lst=False)

        if self.request.user.base_group == 'accounting':
            qf = Q()
            f = dict()
            if q == 'all':
                return self.model.objects.all()
            else:
                qf = Q(last_work_flow__current_state_name='تخصیص کارشناس انبار') | Q(last_work_flow__current_state_name='جمع‌‌آوری') | Q(last_work_flow__current_state_name='چک نهایی')
                f = {"need_financial_approval": True, "accounting_confirm": False}
            qs = qs.filter(qf, **f)

        if q == 'include_bazar':
            qs = self.model.objects.filter(factoritem__is_bazar=True).distinct()
            return qs
        elif q == 'include_trade':
            qs = self.model.objects.filter(Q(factoritem__supply_locations__is_bazar=False) & Q(factoritem__supply_locations__is_wh=False)).distinct()
            return qs
        elif q == 'all_wh':
            qs = (self.model.objects
                  .filter(factoritem__isnull=False, last_work_flow__current_state_name__in=['مرحله نهایی', 'تایید تحویل'])
                  .exclude(factoritem__supply_locations__sepidar_wh_code__isnull=True)
                  .distinct())
            return qs
        elif q == 'today':
            user = request.user
            user_groups_name = user.groups.values_list('name', flat=True) if hasattr(request,'user') else request.groups.values_list('name', flat=True)
            if 'sales_admin' in user_groups_name:
                qs = self.model.objects.filter(created_date__date=timezone.now()).distinct()
            elif 'sales_user' in user_groups_name:
                qs = self.model.objects.filter(creator_user=user, created_date__date=timezone.now()).distinct()
                return qs
        elif q == 'not_delivered_items':
            qs = self.model.objects.filter(is_official=True, last_work_flow__current_state_name='چک نهایی',
                                           official_factor_for_this_factor__isnull=True)
        elif q == 'without_accounting_confirm':
            qs = self.model.objects.filter(accounting_confirm=False, last_work_flow__current_state_name__in=WH_FACTOR_STATES)
        elif q == 'not_delivered':
            qs = self.model.objects.filter(accounting_confirm=True, last_work_flow__current_state_name__in=[
                                            "تخصیص کارشناس انبار", "جمع‌‌آوری", "چک نهایی", "ارسال یا تحویل",
                                        ])

        return qs

    def customize_row(self, row, obj):
        if obj.q:
            row['q'] = '<a class="fw-bold" href="%s" target="_blank">%s</a>' % (
                reverse('micmod_base:quotations.view', args=(obj.q.id,)),
                obj.q.id if obj.q else '-'
            )
        else:
            row['q'] = '-'
        if obj.created_date < parse_datetime("2027-07-08 00:00:00.390205+00"):
            row['id'] = '<a class="fw-bold" href="%s" target="_blank">%s</a>' % (
                reverse('factor:factor.view', args=(obj.id,)),
                obj.pk if obj.pk else '-'
            )
        else:
            row['id'] = '<a class="fw-bold" href="%s" target="_blank">%s</a>' % (
                reverse('factor:safe.factor.view', args=(obj.id,)),
                obj.pk if obj.pk else '-'
            )
        row['q__customer_party_id'] = obj.q.customer_party_id.title if obj.q else ''
        row['q__currency_ref'] = obj.q.currency_ref.title if obj.q else ''
        row['creator_user'] = obj.creator_user.username if obj.creator_user else ''
        row['q__payment_method'] = obj.q.get_payment_method_display() if obj.q else ''
        row['last_work_flow__to_user'] = obj.last_work_flow.to_user.username if obj.last_work_flow else ''
        row['wh_user'] = " ".join([x.username for x in obj.wh_user.all()])
        row['checker'] = " ".join([x.username for x in obj.checker.all()])

        row['total_price'] = f'{parse_number(obj.total_price):,}'
        row['created_date'] = '%s' % to_jalali_date(obj.created_date)
        row['comments'] = '<hr>'.join([f"{x.comment_content} <br> ({x.elapsed_time})" for x in
                                       obj.comments.filter(comment_title='S')]) if not obj.accounting_confirm else ''  # "S" is accounting not approve factor

    def office_column_defs(self, request):
        for col in [
            {'name': 'q', 'visible': True, 'title': _('quotation'), 'lookup_field': '__pk__icontains',
             'searchable': True, 'className': 'border'},
            {'name': 'wh_user', 'visible': True, 'title': _('wh_user'), 'lookup_field': '__username__icontains',
             'searchable': True, 'className': 'border'},
            {'name': 'checker', 'visible': True, 'title': _('accounting_user'), 'lookup_field': '__username__icontains',
             'searchable': True, 'className': 'border'},
            {'name': 'creator_user', 'visible': True, 'title': _('کارشناس مربوطه'),
             'lookup_field': '__username__icontains', 'className': 'border'},
            {'name': 'last_work_flow', 'visible': True, 'searchable': True, 'title': "مرحله", 'orderable': True,
             'lookup_field': '__current_state_name__icontains', 'className': 'border'},
            {'name': 'cancel', 'visible': True, 'orderable': True, 'searchable': True, 'className': 'border'},
            {'name': 'description', 'visible': True, 'orderable': True, 'searchable': True,
             'lookup_field': '__icontains', 'className': 'border'},
            {'name': 'is_official', 'title': _('is_official'), 'visible': True, 'searchable': True, 'orderable': True,
             'className': 'border'},
            {'name': 'accounting_confirm', 'visible': True, 'orderable': True, 'searchable': True,
             'className': 'border'},
            {'name': 'comments', 'orderable': True, 'title': '<div>شرح عدم تایید مالی</div>', 'visible': True,
             'lookup_field': '__comment_content__icontains', 'className': 'border'},

        ]:
            self.cols.append(col)
        return self.cols

    def wh_column_defs(self, request):
        for col in [
            {'name': 'q', 'visible': True, 'title': _('quotation'), 'lookup_field': '__pk__icontains',
             'searchable': True, 'className': 'border'},
            {'name': 'wh_user', 'visible': True, 'title': _('wh_user'), 'lookup_field': '__username__icontains',
             'searchable': True, 'className': 'border'},
            {'name': 'checker', 'visible': True, 'title': _('accounting_user'), 'lookup_field': '__username__icontains',
             'searchable': True, 'className': 'border'},
            {'name': 'accounting_confirm', 'visible': True, 'orderable': True, 'searchable': True,
             'className': 'border'},
            {'name': 'creator_user', 'visible': True, 'title': _('کارشناس مربوطه'),
             'lookup_field': '__username__icontains', 'className': 'border'},
            {'name': 'last_work_flow', 'visible': True, 'searchable': True, 'title': "مرحله", 'orderable': True,
             'lookup_field': '__current_state_name__icontains', 'className': 'border'},
            {'name': 'accounting_confirm', 'visible': True, 'orderable': True, 'searchable': True, 'className': 'border'},
            {'name': 'sepidar_number', 'visible': True, 'orderable': True, 'title': 'شماره سپیدار', 'className': 'border'},
            {'name': 'sepidar_inventory_delivery_number', 'visible': True, 'orderable': True, 'title': 'حواله سپیدار', 'className': 'border'},
            {'name': 'cancel', 'visible': True, 'orderable': True, 'searchable': True, 'className': 'border'},
            {'name': 'description', 'visible': True, 'title': '<div style="width:150px;">توضیحات</div>',
             'orderable': True, 'searchable': True,
             'lookup_field': '__icontains', 'className': 'border'},
        ]:
            self.cols.append(col)
        return self.cols

    def sales_column_defs(self, request):
        for col in [
            {'name': 'wh_user', 'visible': True, 'title': _('wh_user'), 'lookup_field': '__username__icontains',
             'searchable': True, 'className': 'border'},
            {'name': 'checker', 'visible': True, 'title': _('accounting_user'), 'lookup_field': '__username__icontains',
             'searchable': True, 'className': 'border'},
            {'name': 'creator_user', 'visible': True, 'title': _('کارشناس مربوطه'),
             'lookup_field': '__username__icontains', 'className': 'border'},
            {'name': 'accounting_confirm', 'visible': True, 'orderable': True, 'searchable': True, 'className': 'border'},
            {'name': 'comments', 'orderable': True, 'title': '<div>شرح عدم تایید مالی</div>', 'visible': True,
             'lookup_field': '__comment_content__icontains', 'className': 'border'},
            {'name': 'q__currency_ref', 'visible': True, 'searchable': True, 'title': "نوع ارز", 'orderable': True,
             'lookup_field': '__title__icontains', 'className': 'border'},
            {'name': 'last_work_flow', 'visible': True, 'searchable': True, 'title': "مرحله", 'orderable': True,
             'lookup_field': '__current_state_name__icontains', 'className': 'border'},
            {'name': 'sepidar_number', 'visible': True, 'orderable': True, 'title': 'شماره سپیدار', 'className': 'border'},
            {'name': 'cancel', 'visible': True, 'orderable': True, 'searchable': True, 'className': 'border'},
            {'name': 'description', 'visible': True, 'orderable': True, 'searchable': True,
             'lookup_field': '__icontains', 'className': 'border'},
            {'name': 'q', 'visible': True, 'title': _('quotation'), 'lookup_field': '__pk__icontains',
             'searchable': True, 'className': 'border'},
            {'name': 'q__payment_method', 'visible': True, 'title': _('payment_method'), 'lookup_field': '__icontains',
             'className': 'border'},
            {'name': 'sale_type', 'title': _('sale_type'), 'visible': True, 'searchable': False, 'orderable': True,
             'lookup_field': '__title__icontains', 'className': 'border'},
            {'name': 'self_discount', 'title': 'تخفیف', 'visible': True, 'orderable': True, 'searchable': True,
             'className': 'border'},
            {'name': 'delivery_time', 'visible': True, 'searchable': True, 'title': _('delivery_time'),
             'orderable': True, 'lookup_field': '__icontains', 'className': 'border'},
            {'name': 'is_official', 'title': _('is_official'), 'visible': True, 'searchable': True, 'orderable': True,
             'className': 'border'},
            {'name': 'official_value', 'title': _('official_value'), 'visible': True, 'orderable': True,
             'searchable': True, 'className': 'border'},
            {'name': 'official_factor_for_this_factor', 'visible': True, 'orderable': True,
             'title': f"<div style='width:60px; text-wrap:auto;'>{_('official_factor_for_this_factor')}</div>",
             'className': 'border'},
            {'name': 'official_factor_send_with_this_factor', 'visible': True, 'orderable': True,
             'title': f"<div style='width:80px; text-wrap:auto;'>{_('official_factor_send_with_this_factor')}</div>",
             'className': 'border'},
        ]:
            self.cols.append(col)
        return self.cols

    def accounting_column_defs(self, request):
        for col in [
            {'name': 'total_price', 'visible': True, 'orderable': True,
             'title': f"<div style='width:80px; text-wrap:auto;'>جمع مبلغ </div>",
             'className': 'border'},
            {'name': 'wh_user', 'visible': True, 'title': _('wh_user'), 'lookup_field': '__username__icontains',
             'searchable': True, 'className': 'border'},
            {'name': 'checker', 'visible': True, 'title': _('accounting_user'), 'lookup_field': '__username__icontains',
             'searchable': True, 'className': 'border'},
            {'name': 'creator_user', 'visible': True, 'title': _('کارشناس مربوطه'),
             'lookup_field': '__username__icontains', 'className': 'border'},
            {'name': 'accounting_confirm', 'visible': True, 'orderable': True, 'searchable': True, 'className': 'border'},
            {'name': 'comments', 'orderable': True, 'title': '<div>شرح عدم تایید مالی</div>', 'visible': True,
             'lookup_field': '__comment_content__icontains', 'className': 'border'},
            {'name': 'q__currency_ref', 'visible': True, 'searchable': True, 'title': "نوع ارز", 'orderable': True,
             'lookup_field': '__title__icontains', 'className': 'border'},
            {'name': 'last_work_flow', 'visible': True, 'searchable': True, 'title': "مرحله", 'orderable': True,
             'lookup_field': '__current_state_name__icontains', 'className': 'border'},
            {'name': 'sepidar_number', 'visible': True, 'orderable': True, 'title': 'شماره سپیدار', 'className': 'border'},
            {'name': 'cancel', 'visible': True, 'orderable': True, 'searchable': True, 'className': 'border'},
            {'name': 'description', 'visible': True, 'title': '<div style="width:150px;">توضیحات</div>',
             'orderable': True, 'searchable': True,
             'lookup_field': '__icontains', 'className': 'border'},
            {'name': 'q', 'visible': True, 'title': _('quotation'), 'lookup_field': '__pk__icontains',
             'searchable': True, 'className': 'border'},
            {'name': 'q__payment_method', 'visible': True, 'title': _('روش پرداخت'), 'lookup_field': '__icontains',
             'className': 'border'},
            {'name': 'sale_type', 'title': _('sale_type'), 'visible': True, 'searchable': True, 'orderable': True,
             'lookup_field': '__title__icontains', 'className': 'border'},
            {'name': 'self_discount', 'title': 'تخفیف', 'visible': True, 'orderable': True, 'searchable': True,
             'className': 'border'},
            {'name': 'is_official', 'title': _('is_official'), 'visible': True, 'searchable': True, 'orderable': True,
             'className': 'border'},
            {'name': 'official_value', 'title': _('official_value'), 'visible': True, 'orderable': True,
             'searchable': True, 'className': 'border'},
            {'name': 'official_factor_for_this_factor', 'visible': True, 'orderable': True,
             'title': f"<div style='width:60px; text-wrap:auto;'>{_('official_factor_for_this_factor')}</div>",
             'className': 'border'},
            {'name': 'official_factor_send_with_this_factor', 'visible': True, 'orderable': True,
             'title': f"<div style='width:80px; text-wrap:auto;'>{_('official_factor_send_with_this_factor')}</div>",
             'className': 'border'},
            {'name': 'total_price', 'visible': True, 'orderable': True,
             'title': f"<div style='width:80px; text-wrap:auto;'>جمع مبلغ </div>",
             'className': 'border'},
        ]:
            self.cols.append(col)
        return self.cols

    def base_cols(self):
        self.cols = [
            AjaxDatatableView.render_row_tools_column_def(),
            {'name': 'pk', 'visible': False, 'className': 'currency-search'},
            {'name': 'id', 'visible': True, 'orderable': True, 'title': _('code'), 'className': 'border'},
            {'name': 'created_date', 'visible': True, 'orderable': True, 'title': "<div style='min-width:60px'>تاریخ</div>", 'className': 'border'},
            {'name': 'q__customer_party_id', 'visible': True, 'title': _('customer'),
             'lookup_field': '__title__icontains', 'searchable': True, 'className': 'border'},
            {'name': 'last_work_flow__to_user', 'visible': True, 'searchable': True, 'title': "متعلق به",
             'orderable': True,
             'lookup_field': '__username__icontains', 'className': 'border'},
            {'name': 'request_cancel', 'visible': True, 'orderable': True, 'title': _('درخواست کنسل'), 'className': 'border'},
        ]
        return self.cols

    def remove_duplicate_col(self):
        seen = set()
        unique_cols = []
        for col in self.cols:
            name = col.get('name')
            if name not in seen:
                unique_cols.append(col)
                seen.add(name)
        self.cols = unique_cols


def print_view(request, id=-1):

    action_ = request.GET.get('action')
    if action_ == 'wh_exit_permit':
        template_name = 'factor/wh_exit_permit.html'
    else:
        template_name = 'factor/factor_print.html'

    location_url_params = '0'
    with_location = '1'
    if request.GET.get('location_url_params') == '1':
        with_location = '1'
        location_url_params = '0'
    elif request.GET.get('location_url_params') == '0':
        with_location = '0'
        location_url_params = '1'

    formset = inlineformset_factory(Factor, FactorItem, form=FactorItemModelForm, extra=0, )
    greeting = {}
    greeting['alt_code_html'] = []
    greeting['heading'] = _("create")
    greeting['pageview'] = _("quotation")
    factor = Factor.objects.filter(id=id).first()
    greeting['form'] = FactorModelForm(instance=factor)
    greeting['with_location'] = with_location
    greeting['location_url_params'] = location_url_params
    greeting['with_location'] = with_location
    greeting['formset'] = formset(instance=factor,
                                  form_kwargs={
                                      "constraint": {
                                          "wf_access": True,
                                          'form_state': 0,
                                          'request': request,

                                      }
                                  }
                                  )

    if factor:
        factor.created_date = datetime2jalali(factor.created_date).strftime('%y/%m/%d-%H:%M')
        factor.last_update_date = datetime2jalali(factor.last_update_date).strftime('%y/%m/%d-%H:%M')
    greeting['data'] = factor
    return render(request, template_name, greeting)


class DirectFactorView(View):
    def get(self, request, *args, **kwargs):
        url = reverse('micmod_base:quotations.create')
        url += '?direct'
        return redirect(url)


class CustomerRequestFactorViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasShopPermission]
    queryset = Factor.objects.all().order_by('-created_date')
    serializer_class = FactorSerializer
    http_method_names = ['get', 'post']

    @action(detail=False, methods=['get'], url_path='by-request/(?P<customer_request_id>[^/.]+)')
    def list_by_request(self, request, customer_request_id=None):
        queryset = self.get_queryset().filter(customer_request_id=customer_request_id)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def list(self, request, *args, **kwargs):
        return JsonResponse({'detail': 'url with "pk" required'})

    @action(detail=False, methods=['post'], url_path='create')
    def create_factor(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                serializer = self.serializer_class(data=request.data, context={'request': request})
                if serializer.is_valid(raise_exception=True):
                    obj = serializer.save()
                    wf = obj.submit_flow(self.request, is_new=True)
                    obj.last_work_flow = wf
                    obj.extra_data.request = self.request
                    obj.save()
                    return Response(serializer.data)
        except Exception as e:
            return Response(show_error(e, __file__, output=True))

    @action(detail=False, methods=['post'], url_path='payment-approve/(?P<factor_id>[^/.]+)')
    def payment_approve(self, request, factor_id, *args, **kwargs):
        try:
            with transaction.atomic():
                approve = request.data.get('approve')
                f = Factor.objects.get(pk=factor_id)
                if approve:
                    f.shop_payment_approved = True
                    f.extra_data.request = request
                    f.save()
                    serializer = self.serializer_class(instance=f)
                    return Response(serializer.data)
                else:
                    for fi in f.factoritem_set.all():
                        fi.quantity = 0
                        fi.extra_data.request = request
                        fi.save()
                    f.is_deleted = True
                    f.extra_data.request = request
                    f.save()
                    return Response(status=204)
        except Exception as e:
            return Response(show_error(e, __file__, output=True))

    # @action(detail=False, methods=['post'], url_path='update')
    # def update_factor(self, request, *args, **kwargs):
    #     try:
    #         with transaction.atomic():
    #             serializer = self.serializer_class(data=request.data, instance=',', context={'request': request})
    #             if serializer.is_valid(raise_exception=True):
    #                 obj = serializer.save()
    #                 wf = obj.submit_flow(self.request, is_new=True)
    #                 obj.last_work_flow = wf
    #                 obj.extra_data.request = self.request
    #                 obj.save()
    #                 return Response(serializer.data)
    #     except Exception as e:
    #         return Response(show_error(e, __file__, output=True))


class DeliveryList(LoginRequiredMixin, BaseView):
    model = Delivery
    template_name = 'factor/delivery.html'
    success_message = 'ذخیره شد'
    form_struct = {
        'form': DeliveryForm,
        'childes': [
            {
                'form': '',
                'childes': [{}]
            },
        ]
    }

    def get_success_url(self):
        return reverse_lazy('factor:delivery.view')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        return context


class DeliveryDatatableView(AjaxDatatableView):
    model = Delivery
    title = 'deliver method'
    initial_order = [["id", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    def get_columns(self, fields):
        res = [AjaxDatatableView.render_row_tools_column_def()]
        for field in fields:
            col = dict()
            col['className'] = 'py-3'
            col['lookup_field'] = '__icontains'
            col['defaultContent'] = ''
            col['orderable'] = True
            col['searchable'] = True
            col['name'] = field if isinstance(field, str) else None
            col['visible'] = True
            if isinstance(field, dict):
                for key in field.keys():
                    col[key] = field[key]
            if not col.get('title'):
                col['title'] = _(col.get('name'))
            res.append(col)
        return res

    def get_column_defs(self, request):
        cols = [
            {'name': 'id', 'title': "<div class='px-3' style='max-width:20px;'>شناسه</div>", 'className': 'guide-search mxw-50px'},
            {'name': 'type', },
            # {'name': 'tracking_number', 'title': "<div class='px-3' style='width:40px;'>کد رهگیری </div>",},
            # {'name': 'delivery_date', 'title': "<div class='px-3' style='width:40px;'>تاریخ ارسال</div>"},
            {'name': 'base_cost', 'title': "<div class='px-3' style='width:40px;'>هزینه پایه</div>"},
            {'name': 'extra_cost', 'title': "<div class='px-3' style='width:40px;'>هزینه اضافی</div>"},
        ]

        return self.get_columns(cols)

    def customize_row(self, row, obj):
        x = super().customize_row(row, obj)
        row['type'] = '<a class="fw-bold" href="%s">%s</a>' % (
            reverse('factor:delivery.update', args=(obj.id,)),
            obj.get_type_display() if obj.type else '_'
        )


class WhPacking(View):
    template_name = 'factor/partial/packing_json.html'

    def get(self, request, *args, **kwargs):
        pk = self.request.GET.get('pk')
        factor = Factor.objects.select_related('q').get(pk=pk)

        # استخراج customer_party_id با یک خط
        factor_customer_party_id = getattr(factor, 'customer_party_id', None) or (
            getattr(factor.q, 'customer_party_id', None) if hasattr(factor, 'q') else None
        )

        if not factor_customer_party_id:
            return JsonResponse({'res': ''})

        # استفاده از Subquery به جای IN برای عملکرد بهتر
        factor_ids = Factor.objects.filter(
            Q(customer_party_id=factor_customer_party_id) |
            Q(q__customer_party_id=factor_customer_party_id),
            sepidar_id__isnull=True,
            sepidar_number__isnull=True
        ).values('id')

        # فقط فیلدهای مورد نیاز رو بگیر
        factor_items = FactorItem.objects.filter(
            factor_id__in=Subquery(factor_ids)
        ).select_related('factor').only(
            'id', 'factor_id', 'goods_code__part_number', 'quantity',  # فیلدهای مورد نیاز
        ).order_by('factor_id').distinct()

        context = {'factor_items': factor_items}
        html = render_to_string(self.template_name, context, request)
        return JsonResponse({'res': html})


def get_supply_locations(request, sku, factor_item_pk, *args, **kwargs):

    item = Item.objects.filter(sku=sku).first()
    context = dict()
    context['locations'] = item.supply_locations_ if item else ['', '']
    context['factor_item'] = FactorItem.objects.filter(pk=factor_item_pk).first()
    html = render_to_string('factor/partial/ajax_supply_locations.html', context)
    return JsonResponse({'res': html})


def show_force_factor(request, *args, **kwargs):
    from tools import const
    user = request.user
    if user.is_authenticated and user.base_group == 'wh' or user.is_superuser:
        force_factor = Factor.objects.filter(force_factor=True, last_work_flow__current_state_name__in=const.WH_FACTOR_STATES)
        force_factors_id = [f.pk for f in force_factor]
        return JsonResponse({'res': force_factors_id, 'count': force_factor.count()})
    return JsonResponse({'res': ''}, safe=False)


def show_all_supplied_factor(request, *args, **kwargs):
    user = request.user
    if user.is_authenticated and user.base_group == 'wh' or user.is_superuser:
        factors = Factor.objects.filter(last_work_flow__current_state_name__in=['تخصیص کارشناس انبار'])
        supplied_factors = [factor.id for factor in factors if factor.is_all_supplied]
        for f in factors:
            x = f.is_all_supplied

        return JsonResponse({'res': supplied_factors, 'count': len(supplied_factors)}, safe=False)
    return JsonResponse({'res': ''}, safe=False)


def empty_checker(request, *args, **kwargs):
    from tools import const
    if request.user.base_group == 'accounting' or request.user.is_superuser:
        factors = list(Factor.objects.filter(checker__isnull=True,
                                             last_work_flow__current_state_name__in=const.ACCOUNTING_FACTOR_STATES).order_by('-id')
                       .values_list('pk', flat=True))
        return JsonResponse({'res': factors, 'count': len(factors)}, safe=False)
    return JsonResponse({'res': ''}, safe=False)


class SafeFactorView(LoginRequiredMixin, BaseView):
    safe_methods = {'get_quotation_items_for_factor_safe'}
    template_name = 'factor/safe_factor.html'
    form_class = FactorEditForm
    model = Factor
    form_struct = {
        'form': FactorEditForm,
        'childes': [
            {
                'form': FactorItemFormset,
                'childes': [{}]
            },
        ]
    }
    flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json', 'Factor')
    has_flow = True
    has_formset = True
    wf_last_step_is_open = True
    formset_form = FactorItemFormset
    formset_model = FactorItem
    formset_fk_field = 'factoritem_set'
    related_name_fk = 'factoritem_set'
    wf_last_step_is_open = True

    allow_perms = [f'{model._meta.app_label}.view_{model._meta.model_name}',
                f'{model._meta.app_label}.add_{model._meta.model_name}',
                f'{model._meta.app_label}.change_{model._meta.model_name}',
                f'{model._meta.app_label}.delete_{model._meta.model_name}',
                f'{model._meta.app_label}.factor_send_or_delivery_{model._meta.model_name}'
                ]

    def after_sepidar_error(self):
        if 'next' in self.request.POST:
            self.object.last_work_flow = self.object.workflows.all().order_by('-id')[1]
            self.object.final_check = False
            self.object.extra_data.request = self.request
            self.object.save()
            self.object.workflows.all().order_by('id').last().delete()
        else:
            self.object.final_check = False
            self.object.extra_data.request = self.request
            self.object.save()

    def send_factor_to_sepidar(self):
        customer = getattr(self.object, 'customer_party_id', None) or self.object.q.customer_party_id
        if not customer.active:
            messages.error(self.request, f'مشتری در پرتال غیر فعال است.')
            self.after_sepidar_error()
            return

        res = SepidarApiCall.get_party(customer.sepidar_party_id)
        if not res.get('iscustomer'):
            messages.error(self.request, f'مشتری در سپیدار فعال نیست.')
            self.after_sepidar_error()
            return
        try:
            res = SepidarApiCall.factor_to_sepidar(self.object, self.request)
            if 'errors' not in res:
                self.object.sepidar_number = res.get('number')
                self.object.sepidar_id = res.get('invoiceid')

                self.object.sepidar_inventory_delivery_number = res.get('sepidar_inventory_delivery_number')
                self.object.sepidar_inventory_delivery_id = res.get('sepidar_inventory_delivery_id')
                self.object.sepidar_voucher_number = res.get('sepidar_voucher_number')
                self.object.sepidar_voucher_id = res.get('sepidar_voucher_id')
                self.object.fiscalyearref = settings.SEPIDAR_CONST_DATA.get('fiscalyearref')

                self.object.extra_data.request = self.request
                self.object.final_check = True
                self.object.save()

                """ save sepidar InvoiceItemID for fi """
                fis = list(self.object.factoritem_set.all())
                lookup = {(d["quantity"], d["itemref"]): d["invoiceitemid"] for d in res.get('invoice_items')}

                for item in fis:
                    key = (item.quantity, item.goods_code.sepidar_id_0)
                    if key in lookup:
                        item.sepidar_id = lookup[key]

                FactorItem.objects.bulk_update(fis, ["sepidar_id"])
                messages.success(self.request, f'فاکتور به سپیدار ارسال شد، کد: {self.object.sepidar_number}')
                cache.delete('all_stock_quantity')
                return
            else:
                self.after_sepidar_error()
                messages.error(self.request, f'خطا در ارسال فاکتور به سپیدار')
                messages.error(self.request, f"{res['errors']}")
                return
        except StockRefNotFoundError as e:
            self.after_sepidar_error()
            messages.error(self.request, f'{e}')
        except Exception as e:
            self.after_sepidar_error()
            messages.error(self.request, f'{e}')

    def save_new_address(self):
        try:
            address = self.request.POST.get('new_address')
            customer = self.request.POST.get('customer') or self.object.customer_party_id.pk
            if address and customer:
                obj = CustomerAddress.objects.create(address=address, customer_id=customer)

                self.request.POST._mutable = True
                self.request.POST['address'] = obj.pk
                self.request.POST._mutable = False

                self.object.extra_data.request = self.request
                self.object.address = obj
                self.object.save()
                return obj
        except Exception as e:
            pass

    def get_success_url(self):
        return reverse_lazy('factor:safe.factor.view', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        if self.object is None:
            is_new = True
        else:
            is_new = False

        self.get_form_kwargs()

        self.object = self.get_object()
        form = self.get_form()
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        form.instance.extra_data.request = self.request
        self.object = form.save()

        if form.file_model and form.file_groups_2:
            self.object.save_file(request=self.request,
                                  file_groups=form.file_groups_2,
                                  file_model=form.file_model,
                                  obj=self.object,
                                  input_prefix='file'
                                  )

        form_set = self._build_item_formset(data=request.POST, instance=self.object)
        if not form_set.is_valid():
            return self.render_to_response(self.get_context_data(form_s=form_set))

        service = SupplyLocationService()
        try:
            with transaction.atomic():
                for f_s in form_set.forms:
                    f_s.instance.extra_data.request = self.request
                instances = form_set.save(commit=False)  # حذف‌ها را خودمان مدیریت می‌کنیم

                # ۱) ردیف‌های حذف‌شده: آزادسازی SL + اعتبارسنجی قفل + حذف ردیف
                for obj in form_set.deleted_objects:
                    service.delete_factor_item(obj, request.user)

                # ۲) ذخیره‌ی ردیف‌های باقی‌مانده
                for instance in instances:
                    instance.extra_data.request = self.request
                    instance.save()
                for fi in self.object.factoritem_set.all():
                    fi.save_comment(self.request, CommentsForm)

                # ۳) save_m2m امن — فقط فرم‌هایی که این متد را دارند
                for form in form_set.saved_forms:
                    if hasattr(form, 'save_m2m'):
                        form.save_m2m()

                # ۳) sync محل تامین فقط برای ردیف‌های غیرحذفی
                if self.state_index < 2:
                    for idx, form in enumerate(form_set.forms):
                        if form.instance.pk and not form.cleaned_data.get('DELETE'):
                            raw = request.POST.get(f'factoritem_set-{idx}-supply_locations')
                            selections = json.loads(raw or '[]')
                            service.sync_factor_item(form.instance, selections, request.user)

                wf_obj = self.submit_flow(is_new=is_new)
                self.object.last_work_flow = wf_obj
                self.object.save_comment(self.request, CommentsForm)
                customer_party_id = getattr(self.object, 'customer_party_id', None)
                if customer_party_id and not self.object.notify_number and customer_party_id.customerexpert_set.filter(send_notification=True, phone__icontains='09').exists():
                    self.object.notify_number = customer_party_id.customerexpert_set.filter(send_notification=True, phone__icontains='09').last().phone

                self.object.save()
                self.tired_q()

                if 'send_factor_to_sepidar' in self.request.POST:
                    self.send_factor_to_sepidar()

                if 'new_address' in self.request.POST:
                    self.save_new_address()

        except ValidationError as e:
            form_set._non_form_errors = form_set.error_class([str(e)])
            form_set.non_form_errors = form_set.error_class([str(e)])
            return self.render_to_response(self.get_context_data(form_s=form_set))

        return redirect(self.get_success_url())


        return super().post(request, *args, **kwargs)

    def submit_flow(self, is_new):
        groups = {
                    0: {"group": "sales_user", "state_name": "پیش‌نویس"},
                    1: {"group": "sales_admin", "state_name": "تایید مدیر فروش"},
                    2: {"group": "wh_admin", "state_name": "تخصیص کارشناس انبار"},
                    3: {"group": "factor_collector", "state_name": "جمع‌‌آوری"},
                    4: {"group": "factor_final_check", "state_name": "چک نهایی"},
                    5: {"group": "factor_send_or_delivery", "state_name": "ارسال یا تحویل"},
                    6: {"group": "factor_delivery_approve", "state_name": "تایید تحویل"},
                    7: {"group": "factor_delivery_approve", "state_name": "مرحله نهایی"},
                }

        last_flow = self.object.last_work_flow
        current_state_index = self.state_index
        if 0 < current_state_index < 7:
            next_state_index = getattr(self, 'state_index') + 1
            previews_state_index = getattr(self, 'state_index') - 1

        if current_state_index == 0:
            next_state_index = getattr(self, 'state_index') + 1
            previews_state_index = 0

        if current_state_index == 7:
            next_state_index = 7
            previews_state_index = getattr(self, 'state_index') - 1

        current_group_name = groups.get(current_state_index).get('group')
        next_group_name = groups.get(next_state_index).get('group')
        previews_group_name = groups.get(previews_state_index).get('group')

        current_state_name = groups.get(current_state_index).get('state_name')
        next_state_name = groups.get(next_state_index).get('state_name')
        previews_state_name = groups.get(previews_state_index).get('state_name')

        if 'next' in self.request.POST:  # 3 next
            current_group_last_wf_obj = self.object.workflows.filter(belong_to_group=next_group_name)
            if current_group_last_wf_obj:
                to_user = current_group_last_wf_obj.latest("pk").from_user
            else:
                next_state_user = get_user_model().objects.filter(groups__name=next_group_name)
                to_user = next_state_user.last()

            wf = WorkFlow.objects.create(action='next', flow_name='factor',creator_user=self.request.user,
                                         editor_user=self.request.user, wf_status=3, from_user=last_flow.to_user,
                                         to_user=to_user,
                                         content_type=self.model.content_type(), object_id=self.object.pk,
                                         belong_to_group=current_group_name, current_state_name=next_state_name,
                                         wf_description=self.request.POST.get('wf_description'),
                                         state=current_state_name)
            return wf
        elif 'draft' in self.request.POST and (is_new or not last_flow):  # 5 first draft
            wf = WorkFlow.objects.create(action='draft', flow_name='factor', wf_status=5,
                                         creator_user=self.request.user,
                                         editor_user=self.request.user,
                                         from_user=self.request.user,
                                         to_user=self.request.user,
                                         content_type=self.model.content_type(), object_id=self.object.pk,
                                         belong_to_group=current_group_name, current_state_name=current_state_name,
                                         wf_description=self.request.POST.get('wf_description'),
                                         state=current_state_name)
            return wf

        elif 'back' in self.request.POST:  # 2 back
            current_group_last_wf_obj = self.object.workflows.filter(belong_to_group=previews_group_name).latest("pk")
            if current_group_last_wf_obj:
                to_user = current_group_last_wf_obj.from_user
            else:
                previews_state_user = get_user_model().objects.filter(groups__name=previews_group_name)
                to_user = previews_state_user.first()

            wf = WorkFlow.objects.create(action='back', flow_name='factor',creator_user=self.request.user,
                                         editor_user=self.request.user, wf_status=2,
                                         from_user=last_flow.to_user,
                                         to_user=to_user,
                                         content_type=self.model.content_type(), object_id=self.object.pk,
                                         belong_to_group=current_group_name, current_state_name=previews_state_name,
                                         wf_description=self.request.POST.get('wf_description'),
                                         state=current_state_name)
            return wf

        elif 'change_user' in self.request.POST:  # 4 change user
            to_user = self.request.POST.get('to_current_group_user')
            wf = WorkFlow.objects.create(action='change user', flow_name='factor', creator_user=self.request.user,
                                         editor_user=self.request.user, wf_status=4,
                                         from_user=last_flow.to_user,
                                         to_user_id=to_user,
                                         content_type=self.model.content_type(), object_id=self.object.pk,
                                         belong_to_group=current_group_name, current_state_name=current_state_name,
                                         wf_description=self.request.POST.get('wf_description'),
                                         state=current_state_name)
            return wf

        return last_flow

    def tired_q(self):
        if not self.object.q:
            return

        try:
            pass
        except Exception as e:
            pass

    def form_valid(self, form):
        try:
            condition = self.object and self.object.last_work_flow.current_state_name == 'جمع‌‌آوری' and 'next' in self.request.POST
        except Exception as e:
            condition = False
        if condition:
            self.form.instance.collecting_end_time = timezone.now()
        obj_before_save = self.object
        res = super().form_valid(form)
        self.factor_service()

        if 'next' in self.request.POST and not self.object.is_need_sales_admin_confirmation() and self.object.is_all_supplied and self.state_index == 0:
            # "بدون نیاز به تایید مدیر فروش" and "بدون نیاز به تامین کالا" and "در مرحله پیش نویس هستیم" and 'next':
            next = "مرحله تایید مدیر فروش"
            wf_data = {
                'state': self.flow_config.get('flow_state_list')[self.state_index + 1],
                'wf_description': 'بدون نیاز به تایید مدیر فروش',
                'from_user': self.request.user,
                'to_user': get_user_model().objects.filter(groups__name='wh_admin').last(),
                'current_state_name': self.flow_config.get('flow_state_list')[self.state_index + 2],
                'object_id': self.object.pk,
            }
            self.save_flow(self.request, **wf_data)

        elif 'next' in self.request.POST and not self.object.is_need_sales_admin_confirmation() and not self.object.is_all_supplied and self.state_index == 0:
            # "بدون نیاز به تایید مدیر فروش" and "در مرحله پیش نویس هستیم" and "next": و کالا تامیین نشده
            next = "تاید مدیر فروش"
            wf_data = {
                'state': self.flow_config.get('flow_state_list')[self.state_index + 1],
                'wf_description': 'بدون نیاز به تایید مدیر فروش',
                'from_user': self.request.user,
                'to_user': self.object.creator_user, # get_user_model().objects.filter(groups__name='wh_admin').first(),
                'current_state_name': self.flow_config.get('flow_state_list')[self.state_index + 2],
                'object_id': self.object.pk,
            }
            self.save_flow(self.request, **wf_data)

        if 'back' in self.request.POST and not self.object.is_need_sales_admin_confirmation() and self.state_index == 2:
            # "بدون نیاز به تایید مدیر فروش" and "بدون نیاز به تامین کالا" and "در مرحله تخصیص کارشناس انبار هستیم" and 'back':
            back = "مرحله تایید مدیر فروش"
            wf_data = {
                'wf_status': 2,  # back
                'state': self.flow_config.get('flow_state_list')[self.state_index - 1],
                'wf_description': 'کالا موجود در انبار',
                'from_user': self.request.user,
                'to_user': self.object.creator_user, # get_user_model().objects.filter(groups__name='wh_admin').first(),
                'current_state_name': self.flow_config.get('flow_state_list')[self.state_index - 2],
                'object_id': self.object.pk,
            }
            self.save_flow(self.request, **wf_data)

        if 'send_factor_to_sepidar' in self.request.POST:
            self.send_factor_to_sepidar()

        self.object.need_financial_approval = True
        if obj_before_save and obj_before_save.accounting_confirm:
            self.object.accounting_confirm = True
        self.object.save()
        return res

    @timer
    def get_context_data(self, **kwargs):
        print('get context data')
        context = super().get_context_data(**kwargs)
        context['f_warning'] = []

        if self.request.method == "POST":
            for f in context['form_s'].forms:
                f.initial['supply_locations'] = self.request.POST.get(f'{f.prefix}-supply_locations')
            # [self.request.POST.get(f'{x.prefix}-supply_locations') for x in context['form_s'].forms]
            context["form_s"] = context['form_s']
            context["form"] = self._build_factor_form(
                data=self.request.POST,
                instance=self.object,
            )
        else:
            initial = dict()
            if self.object:
                Notification.notify_customer_for_factor(self.object, self.request)
                if self.object.last_work_flow and (self.object.last_work_flow.to_user == self.request.user or self.object.last_work_flow.to_user.team == self.request.user):
                    context['allow_cancel'] = self.object.last_work_flow.to_user
                if self.request.user.is_superuser:
                    context['allow_cancel'] = self.object.last_work_flow.to_user

                if not self.object.is_all_supplied2:
                    context['f_warning'].append('همه ردیف ها تامین نشده یا سفارش در راه دارد')
                    if self.state_index >= 4:
                        context['allow_next'] = False

                if self.object.is_reserve:
                    context['allow_next'] = False
                    context['f_warning'].append('فاکتور های رزرو امکان خروج از پیش نویس را ندارند.')

                if self.object and self.state_index == 4 and (self.object.need_financial_approval and not self.object.accounting_confirm):
                    context['f_warning'].append('نیاز به تایید مالی دارد.')
                    context['allow_next'] = False

                if self.object and self.state_index == 5 and not self.object.sepidar_id:
                    context['allow_next'] = False
                    context['f_warning'].append('فاکتور به سپیدار ارسال نشده')

                if self.object.sepidar_id:
                    context['allow_back'] = False
                    context['f_warning'].append('فاکتوری که به سپیدار ارسال شده امکان عودت ندارد')

                exclude_qi_id = self.object.factoritem_set.values_list('qi')
                other_qi = QuotationItem.objects.filter(quotation=self.object.q).exclude(pk__in=exclude_qi_id)
                initial = [
                    {
                        'goods_code': row.goods_code_fk.pk,  # FK → فقط pk بده
                        'part_number_show': row.goods_code_fk.part_number or "",
                        'quantity': row.quantity or 0,
                        'price': row.final_price or 0,
                        'discount_per_item': row.discount_per_item or 0,
                        'qi': row.pk,
                        'DELETE': True,
                        # ... سایر فیلدهای FactorItem
                    }
                    for row in other_qi
                ]
            else:
                context['allow_next'] = False
            context["form_s"] = self._build_item_formset(
                instance=self.object, initial=initial
            )
            if not self.object:
                self.template_name = 'factor/safe_factor_create.html'

        context["factor"] = self.object
        context["object"] = self.object
        context["app_name"] = 'factor'


        return context

    @timer
    def dispatch(self, request, *args, **kwargs):
        view_name = self.request.GET.get('view_name', None)
        if view_name in self.__class__.safe_methods and hasattr(self, view_name):
            method = getattr(self, view_name)
            return method(request, *args, **kwargs)

        return super().dispatch(request, *args, **kwargs)

    def _get_factor_allowed_fields(self):
        permissions = self.request.user.get_all_permissions()
        user_exist_perm = []
        allowed_hidden = []
        allowed_edit = []
        allowed_show = []
        for p in permissions:
            exist_perm = FACTOR_FIELDS_BY_PERMISSION.get(p, None)
            if exist_perm:
                user_exist_perm.append(exist_perm)

        for perm in user_exist_perm:
            if perm:
                data = perm.get(self.state_index or 0)
                if data:
                    allowed_hidden += data['hidden']
                    allowed_edit += data['edit']
                    allowed_show += data['show']

        if not allowed_edit and not allowed_show:
            raise PermissionDenied("شما دسترسی لازم برای ویرایش این فاکتور را ندارید.")
        hidden = []
        edit = []
        show = []
        for h in allowed_hidden:
            if h not in hidden:
                hidden.append(h)

        for e in allowed_edit:
            if e not in edit:
                edit.append(e)

        for s in allowed_show:
            if s not in show:
                show.append(s)
        # allowed_hidden = list(set(allowed_hidden))
        # allowed_edit = list(set(allowed_edit))
        # allowed_show = list(set(allowed_show))
        return edit, hidden, show
        return allowed_edit, allowed_hidden, allowed_show

    def _get_factor_item_allowed_fields(self):
        # permissions = _get_permission_list(self.request.user)
        permissions = self.request.user.get_all_permissions()
        user_exist_perm = []
        allowed_hidden = []
        allowed_edit = []
        allowed_show = []
        for p in permissions:
            exist_perm = FACTOR_ITEM_FIELDS_BY_PERMISSION.get(p, None)
            if exist_perm:
                user_exist_perm.append(exist_perm)

        for perm in user_exist_perm:
            if perm:
                data = perm.get(self.state_index or 0)
                if data:
                    allowed_hidden += data['hidden']
                    allowed_edit += data['edit']
                    allowed_show += data['show']

        if not allowed_edit and not allowed_show:
            raise PermissionDenied("شما دسترسی لازم برای ویرایش این فاکتور را ندارید.")
        return allowed_edit, allowed_hidden, allowed_show

    @timer
    def _get_factor_item_formset(self, user, data=None, instance=None, initial=None, *args, **kwargs):
        """
        یک inline formset برای FactorItem با فیلدهای محدودشده بر اساس گروه کاربر برمی‌گرداند.
        """
        if initial and data is None:
            extra = len(initial)
        else:
            extra = 0
        edit, hidden, show = self._get_factor_item_allowed_fields()

        # یک فرم پویا با فیلدهای مجاز می‌سازیم
        class _FactorItemForm(FactorItemForm):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, allowed_fields=edit, allowed_hidden=hidden, **kwargs)

        FactorItemInlineFormset = inlineformset_factory(
            Factor,
            FactorItem,
            form=_FactorItemForm,
            formset=FactorItemInlineFormSetBase,
            extra=extra,  # ردیف خالی اضافه نمی‌شود؛ در template با JS مدیریت کنید
            can_delete=True,
        )

        kwargs = {
            'data': data,
            'instance': instance,
            'prefix': 'factoritem_set',
            'form_kwargs': kwargs,  # هرچه الان پاس می‌دهی
            # 'form_kwargs': {'user': self.request.user},  # هرچه الان پاس می‌دهی
        }
        if initial and data is None:
            kwargs['initial'] = initial
        return FactorItemInlineFormset(*args, **kwargs)

    @timer
    def _build_factor_form(self, data=None, instance=None, initial=None, **kwargs):
        allowed, hidden, show = self._get_factor_allowed_fields()
        return FactorEditForm(allowed_fields=allowed, allowed_hidden=hidden, only_show=show, data=data, instance=instance, initial=initial, **kwargs)

    @timer
    def _build_item_formset(self, data=None, instance=None, initial=None, **kwargs):
        return self._get_factor_item_formset(self.request.user, data=data, instance=instance, initial=initial, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        source_pk = self.request.GET.get('pk')  # /factor/create/?from=123

        # فقط در GETِ حالت create
        if source_pk and self.request.method == 'GET':
            quotation = Quotation.objects.filter(pk=source_pk).first()
            initial.update({
                'customer': quotation.customer_party_id.sepidar_party_id,  # FK → فقط pk
                'currency': quotation.currency_ref.pk,
                'description': quotation.description,
                'sale_type': quotation.sale_type,
                'self_discount': quotation.self_discount,
                'is_official': quotation.is_official,
                'official_value': quotation.official_value,
            })
        return initial
    # ── django UpdateView hooks ───────────────────────────────────────────────

    def get_form(self, form_class=None):
        return self._build_factor_form(**self.get_form_kwargs())

    def get_quotation_items_for_factor_safe(self, request, *args, **kwargs):
        pk = self.request.GET.get('pk')
        from workflow.forms import WorkFlowModelForm
        flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json', 'Factor')
        quotation = Quotation.objects.filter(pk=pk).first()
        qis = QuotationItem.objects.filter(quotation_id=pk).select_related('goods_code_fk', 'quotation')
        context = self.get_context_data()

        qis_data = [
                        {
                            'goods_code': row.goods_code_fk.pk,  # FK → فقط pk بده
                            'quantity': row.quantity,
                            'price': row.final_price,
                            'discount_per_item': row.discount_per_item,
                            'part_number_show': row.goods_code_fk.part_number,
                        }
                        for row in qis
                    ]

        def num(v):
            return v if v is not None else 0

        return JsonResponse({
            "id": quotation.pk,
            # ── فیلدهای ساده‌ی فاکتور ──
            "description": quotation.description or "",
            "date": quotation.date.isoformat() if getattr(quotation, "date", None) else "",
            # ── فیلدهای Select2 فاکتور (id + برچسب) ──
            "customer_id": quotation.customer_party_id.sepidar_party_id,
            "customer_name": str(quotation.customer_party_id) if quotation.customer_party_id else "",
            "currency_id": quotation.currency_ref.pk,
            "currency_name": str(quotation.currency_ref) if quotation.currency_ref else "",
            # ── ردیف‌ها ──
            "rows": [
                {
                    "goods_code_id": r.goods_code_fk.pk,
                    "part_number_show": str(r.goods_code_fk.part_number) if r.goods_code_fk else "",
                    "quantity": num(r.quantity),
                    "price": num(r.final_price),
                    "discount_per_item": num(getattr(r, "discount_per_item", 0)),
                }
                for r in quotation.q.all()
            ],
        })

        # form = FactorModelForm(instance=quotation, initial={
        #                                               "constraint": {
        #                                                   "wf_access": True,
        #                                                   'form_state': 0,
        #                                                   'request': self.request,
        #                                                   'form_constraint': flow_config.get("flow_form_constraint"),
        #                                                   'formset_constraint': flow_config.get('flow_formset_constraint')
        #                                                   }
        #                                           })
        # FactorItemFormset.extra = quotation.quotation.count()
        # form_s = FactorItemFormset()
        # context = {'quotation': quotation, 'form': form, 'form_s': form_s, 'factoritem_qi_pair': [], 'request': request}
        #
        # empty_pair = [(qi, context['form_s'][-1], True if idx == 0 else False,
        #                qi.goods_code_fk.appearance_or_real_part_number_(customer=qi.quotation.customer_party_id),
        #                qi.goods_code_fk.part_number != qi.goods_code_fk.appearance_or_real_part_number(qi.quotation.customer_party_id)) for idx, qi in enumerate(qis)]
        # empty_pair.sort(key=lambda x: x[0].is_over)
        # context['factoritem_qi_pair'] = empty_pair
        # context['flow_state_index'] = 0
        # context['flow_state_list'] = flow_config.get('flow_state_list')
        # context['flow_state_list'].append('مرحله نهایی')
        # """if flow object don't exist select user from group (normally for create step)"""
        # group = flow_config.get('flow_users_groups')[1][0]
        # flow_belong_to_group = WorkFlowModelForm._meta.model.objects.filter(belong_to_group=group)
        # user_list = get_user_model().objects.filter(groups__name__in=[group]).distinct().order_by('id')
        # if flow_belong_to_group:
        #     last_wf_user = flow_belong_to_group.order_by('id').last().from_user
        #     next_users = user_list.filter(id__gt=last_wf_user.id).order_by('id')
        #     if next_users:
        #         to_user = next_users.first()
        #     else:
        #         to_user = user_list.first()
        # else:
        #     to_user = user_list.first()
        # context['workflow_form'] = WorkFlowModelForm(
        #     content_type_model=Factor,
        #     initial={
        #                 'wf_access': True,
        #                 'from_user': None,
        #                 'to_user': to_user, #self.get_flow_user(flow_user_groups[self.state_index + 1]), #request.user.__class__.objects.get(pk=59), #._meta.model.objects.get(pk=21),
        #                 'state': 'پیش‌نویس',
        #                 'state_index': 0,
        #                 'belong_to_group': 'sales_user',
        #                 'action': 'create',
        #                 'deadline': None,
        #                 'flow_config': flow_config,
        #                 'create': True
        #             },
        #     current_user=request.user,
        # )

        html = render_to_string('factor/safe_factor_create.html', context, request=self.request)
        return JsonResponse({'res': html})


def cancel_factor(request, pk):
    try:
        # raise ValueError('kdfjsldfj')
        service = SupplyLocationService()
        factor = Factor.objects.get(pk=pk)
        service.cancel_factor(factor, request.user)

        # success_url = reverse_lazy('factor:safe.factor.view', kwargs={'pk': factor.pk})
        messages.success(request, 'فاکتور کنسل شد')
        return JsonResponse({'res': 'فاکتور کنسل شد'})
    except Exception as e:
        factor = Factor.objects.get(pk=pk)
        # success_url = reverse_lazy('factor:safe.factor.view', kwargs={'pk': factor.pk})
        messages.error(request, str(e))
        return JsonResponse({'res': str(e)})


# factor/views.py
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required


@login_required
def prefactor_json(request, pk):
    quotation = get_object_or_404(
        Quotation.objects.prefetch_related('q'), pk=pk
    )

    def num(v):
        return v if v is not None else 0

    return JsonResponse({
        "id": quotation.pk,
        # ── فیلدهای ساده‌ی فاکتور ──
        "description": quotation.description or "",
        "self_discount": quotation.self_discount or 0,
        # "date": quotation.date.isoformat() if getattr(quotation, "date", None) else "",
        # ── فیلدهای Select2 فاکتور (id + برچسب) ──
        "customer_party_id": quotation.customer_party_id.sepidar_party_id,
        "customer_name": str(quotation.customer_party_id) if quotation.customer_party_id else "",
        "currency_ref": quotation.currency_ref.pk,
        "currency_name": str(quotation.currency_ref) if quotation.currency_ref else "",
        "sale_type": quotation.sale_type.pk,
        "sale_type_name": str(quotation.sale_type) if quotation.sale_type else "",
        # ── ردیف‌ها ──
        "rows": [
            {
                "goods_id": r.goods_code_fk.pk,
                "part_number_show": str(r.goods_code_fk.part_number) if r.goods_code_fk else "",
                "quantity": num(r.quantity),
                "price": num(r.final_price),
                "discount_per_item": num(getattr(r, "discount_per_item", 0)),
                "qi": r.pk,
            }
            for r in quotation.quotation.all()
        ],
    })


@login_required
def supply_fragment(request):
    sku = request.GET.get('sku')                       # = goods_id (pk کالای پورتال)
    quantity = float(request.GET.get('quantity') or 0)
    form_index = request.GET.get('form_index')
    if not sku:
        return HttpResponseBadRequest('sku required')

    item = get_object_or_404(Item, pk=sku)

    # ردیف موقتِ ذخیره‌نشده فقط برای ساخت supply
    fi = FactorItem(goods_code=item, quantity=quantity, discount_per_item=0)
    attach_supply([fi])                                # همان تابع موجود تو
    # idx = 0
    # fi.prefix = f'factoritem_set-{idx}'

    return render(request, 'factor/partial/_supply_panel_content_create.html', {
        'supply': fi.supply,
        'quantity': quantity,
        'form_index': form_index
    })


def supply_fragment_view(request, pk):
    """
    AJAX endpoint برای دریافت محتوای پنل محل تامین بر اساس کد کالا.

    GET پارامترها:
      goods_code: مقدار sku کالای جدید
      quantity: تعداد فعلی ردیف
      factor_item_id: شناسه ردیف فاکتور (خالی برای ردیف جدید)

    خروجی:
      200 + HTML  : محتوای داخل sp-panel (سازگار با partial)
      403 + JSON  : permission denied با پیام
    """
    # factor = get_object_or_404(Factor, pk=pk)
    factor = Factor.objects.filter(pk=pk).first()
    sku = request.GET.get('goods_code', '').strip()
    try:
        quantity = float(request.GET.get('quantity', 0) or 0)
    except (TypeError, ValueError):
        quantity = 0
    factor_item_id = request.GET.get('factor_item_id', '').strip() or None

    factor_item = None
    if factor_item_id:
        try:
            factor_item = FactorItem.objects.get(pk=factor_item_id, factor=factor)
        except FactorItem.DoesNotExist:
            raise Http404("ردیف فاکتور یافت نشد")

    # permission check
    allowed, msg = SupplyChangeChecker.run_all(factor_item, sku, request.user)
    if not allowed:
        return JsonResponse({'message': msg or 'تغییر مجاز نیست'}, status=403)

    # واکشی کالا
    item = Item.objects.filter(sku=sku).first()

    if item is None:
        # کد کالا نامعتبر — پنل خالی برمی‌گردانیم
        return render(request, 'factor/partial/_supply_panel_content.html', {
            'supply': {'warehouses': [], 'market_orders': [], 'foreign_orders': []},
            'quantity': quantity,
        })

    # FactorItem موقت (unsaved) — pk=None یعنی هیچ SL ای ندارد
    # پس attach_supply به‌طور خودکار preselection خالی برمی‌گرداند
    tmp_fi = FactorItem(factor=factor, goods_code=item, quantity=quantity, discount_per_item=0)
    attach_supply([tmp_fi])

    return render(request, 'factor/partial/_supply_panel_content.html', {
        'supply': tmp_fi.supply,
        'quantity': quantity,
    })

from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.edit import UpdateView
from django.urls import reverse_lazy
from django.core.exceptions import PermissionDenied, ValidationError
from django.forms import inlineformset_factory
from django.db import transaction

from .models import Factor, FactorItem




# ─── View ─────────────────────────────────────────────────────────────────────

# class FactorEditView(LoginRequiredMixin, UpdateView):
#     """
#     ویرایش فاکتور + ردیف‌های FactorItem به صورت inline.
#
#     URL:
#         path('factors/<int:pk>/edit/', FactorEditView.as_view(), name='factor_edit'),
#     """
#
#     model = Factor
#     template_name = "factor/factor_edit.html"
#
#     # ── helpers ──────────────────────────────────────────────────────────────
#
#     def _get_factor_allowed_fields(self):
#         group = _get_group_key(self.request.user)
#         allowed = FACTOR_FIELDS_BY_PERMISSION.get(group, [])
#         if not allowed:
#             raise PermissionDenied("شما دسترسی لازم برای ویرایش این فاکتور را ندارید.")
#         return allowed
#
#     def _build_factor_form(self, **kwargs):
#         allowed = self._get_factor_allowed_fields()
#         return FactorEditForm(allowed_fields=allowed, **kwargs)
#
#     def _build_item_formset(self, **kwargs):
#         return get_factor_item_formset(self.request.user, **kwargs)
#
#     # ── django UpdateView hooks ───────────────────────────────────────────────
#
#     def get_form(self, form_class=None):
#         return self._build_factor_form(**self.get_form_kwargs())
#
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         if self.request.method == "POST":
#             context["item_formset"] = self._build_item_formset(
#                 data=self.request.POST,
#                 instance=self.object,
#             )
#         else:
#             context["item_formset"] = self._build_item_formset(
#                 instance=self.object,
#             )
#         context["factor"] = self.object
#         return context
#
#     def form_valid(self, form):
#         context = self.get_context_data()
#         item_formset = context["item_formset"]
#
#         if not item_formset.is_valid():
#             return self.form_invalid(form)
#
#         with transaction.atomic():
#             form.instance.editor_user = self.request.user
#             self.object = form.save()
#
#             items = item_formset.save(commit=False)
#             for item in items:
#                 item.editor_user = self.request.user
#                 item.save()
#             for deleted in item_formset.deleted_objects:
#                 deleted.delete()
#
#         return super().form_valid(form)
#
#     def get_success_url(self):
#         return reverse_lazy("safe_factor.view", kwargs={"pk": self.object.pk})


def factor_today_total_price(request, *args, **kwargs):
    user = request.user
    q = request.GET.get('q')
    APPROVAL_STATE = 'تایید مدیر فروش'
    if q == 'my_today_factor_price':
        today = timezone.now().date()
        all_approved_today = (Factor.objects.filter(Q(is_deleted=False) & ~Q(last_work_flow__current_state_name='پیش‌نویس')).annotate(first_approval_data=Min(
            'workflows__created_date',
            filter=Q(workflows__current_state_name=APPROVAL_STATE)
        )).filter(first_approval_data__date=today).values_list('pk', flat=True)
        )
        # qry = (Q(created_date__date=today) & ~Q(last_work_flow__current_state_name='پیش‌نویس') & Q(is_deleted=False))
        factors = Factor.objects.filter(pk__in=all_approved_today)
        user_groups_name = user.groups.values_list('name', flat=True)\
            if hasattr(request, 'user') else request.groups.values_list('name', flat=True)
        if user.is_superuser:
            qs = factors.filter().distinct()
        elif 'sales_admin' in user_groups_name or user.pk == 52: # خانم زند
            qs = factors.filter().distinct()
        elif 'sales_user' in user_groups_name:
            qs = factors.filter(creator_user=user).distinct()
        else:
            qs = Factor.objects.none()
        # total = qs.aggregate(total=Sum('total_price'))['total'] or 0
        rate_subquery = CurrencyAmount.objects.filter(
            currency=OuterRef('currency_ref')
        ).order_by('-id').values('open_rate')[:1]  # یا بر اساس تاریخ

        qs = qs.annotate(
            o_rate=Coalesce(
                F('currency_amount'),
                Subquery(rate_subquery))
        ).annotate(
            calculated_price=Case(
                When(currency_ref=1, then=F('total_price')),
                default=ExpressionWrapper(
                    F('total_price') * F('o_rate'),
                    output_field=DecimalField(max_digits=20, decimal_places=2)
                ),
                output_field=DecimalField(max_digits=20, decimal_places=2)
            )
        )

        total = qs.aggregate(
            total=Coalesce(Sum('calculated_price'), Decimal('0'))
        )['total']
        return JsonResponse({'total_price': total})
