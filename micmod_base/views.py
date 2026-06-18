import ast
import json

import jdatetime
from django.apps import apps
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.template import TemplateDoesNotExist, loader
from django.template.loader import render_to_string
from django.db.models import Q, QuerySet, CharField, Count, Sum, Prefetch
from django.db.models.functions import Cast
from django.utils import timezone
from django.views.generic import DetailView, UpdateView
from jalali_date.templatetags.jalali_tags import to_jalali
from datetime import timedelta, datetime

from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from werkzeug.exceptions import MethodNotAllowed

from comments.forms import CommentsForm
from core.models import BaseModelAuto
from core.permissions import HasShopPermission
from dw.models import DimCustomer
from extra_data.models import Item, PriceSettings, Customer
from factor.forms import FactorItemModelForm, FactorModelForm
from factor.models import FactorItem
from order.models import Order
from sepidar.models import APILogs
from sepidar.models import Dl, Device
from sepidar.scripts.sepidar_classes import Urls
import uuid
from ajax_datatable import AjaxDatatableView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.forms import inlineformset_factory, modelformset_factory
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.conf import settings
from jalali_date import datetime2jalali

from changelog.models import ChangeLog
from inquiry.forms import InquiryResultForm
from micmod_base.base import CurrencyExchange
from micmod_base.forms import QuotationForm, QuotationItemForm2, CurrencyExchangeForm, QuotationItemFormset, \
    QuotationItemFormset, InquiryResultFormset, TimeForm, CustomerRequestForm, CustomerRequestItemForm, qi_fields
from sepidar.models import Dl
from tlg.scripts.sms import send_sms
from tools import const
from tools.datatable import CustomAjaxDatatableView
from tools.import_data import import_customers_from_sepidar
from tools.utils import show_error, to_jalali_date, export_to_excel, is_ajax
from translator import get_text as _
from django.views import View

from micmod_base.models import Quotation, QuotationItem, SaleType, CustomerRequestItem
from core.views import BaseView, Base, DynamicViewRouter
from django.contrib.contenttypes.models import ContentType

from workflow.forms import WorkFlowModelForm
from workflow.models import WorkFlow
from .forms import PendingFormFilter
from django.urls import reverse
import re
from rest_framework import viewsets, status
from .models import CustomerRequest
from .serializers import CustomerRequestSerializer, QuotationSerializer, CustomerQuotationSerializer, \
    QuotationGroupSerializer, QuotationItemGroupSerializer


def generate_direct_factor(request, quotation: Quotation):
    with transaction.atomic():
        factor_data = {
            'q': quotation,
            'delivery_time': quotation.delivery_time,
            'description': 'فاکتور مستقیم',
            'guid': uuid.uuid4(),
            'sepidar_number': quotation.sepidar_number,
            'is_official': quotation.is_official,
            'official_value': quotation.official_value,
            'sale_type': quotation.sale_type,
            'self_discount': quotation.self_discount,
            "creator_user": request.user,
            "editor_user": request.user,
        }
        factor_form = FactorModelForm(data=factor_data)
        if factor_form.is_valid():
            factor = factor_form.save()
            flow_data = {
                "wf_status": 5,
                "action": 'فاکتور مستقیم',
                "flow_name": 'فاکتور',
                "state": const.WF__FACTOR__FIRST_STATE,
                "wf_description": 'فاکتور مستقیم',
                "belong_to_group": 'sales_user',
                "object_id": factor.pk,
                "content_type": ContentType.objects.get_for_model(factor),
                "creator_user": request.user,
                "editor_user": request.user,
                "from_user": request.user,
                "to_user": request.user,
                "current_state_name": const.WF__FACTOR__FIRST_STATE,
            }
            wf = WorkFlow.objects.create(**flow_data)
            factor.last_work_flow = wf
            factor.save()

            count = 0
            for idx, qi in enumerate(quotation.quotation.all()):
                factor_item_data = {
                    'factor': factor,
                    'qi': qi,
                    'goods_code': qi.goods_code_fk,
                    'part_number_show': qi.goods_code_fk.part_number,
                    'price': qi.fee,
                    'quantity': qi.quantity,
                    'delivery_time': qi.delivery_time,
                    'discount_per_item': qi.discount_per_item,
                    # 'supply_locations': order,
                    "creator_user": request.user,
                    "editor_user": request.user,
                    'supply_location': request.POST.get(f'quotation-{idx}-{idx}-supply_location'),
                    'index': count,
                    'reserve_count': request.POST.get(f'quotation-{idx}-reserve_count')
                }
                count += 1
                factor_item_form = FactorItemModelForm(data=factor_item_data, instance=FactorItem(factor=factor, qi=qi,), internal_call=True)
                if factor_item_form.is_valid():
                    factor_item_form.instance.extra_data.request = request
                    factor_item_form.instance.extra_data.idx = idx
                    factor_item = factor_item_form.save()
            return redirect(reverse('factor:factor.view', kwargs={'pk': factor.pk}))


class QuotationsList(LoginRequiredMixin,View):
    def get(self, request):
        q = self.request.GET.get('q')
        greeting = {}
        greeting['heading'] = _("quotation")
        greeting['pageview'] = _("micmod_base")
        greeting['time_form'] = TimeForm()
        # greeting['quotations'] = quotations_record
        # greeting['quotations'] = quotations_record_lst
        return render(request,'micmod-base/quotation/list_datatable.html',greeting)


class QuotationsView(LoginRequiredMixin, BaseView):
    template_name = 'micmod-base/quotation/view.html'
    conflict_template_name = 'micmod-base/quotation/conflict_view.html'
    post_conflict_template_name = 'micmod-base/quotation/conflict_post_view.html'
    form_class = QuotationForm
    model = Quotation
    wf_last_step_is_open = True
    has_flow = True
    form_struct = {
        'form': QuotationForm,
        'childes': [
            {
                'form': QuotationItemFormset,
                'childes': [{'form': InquiryResultForm}]
            },
        ]
    }
    flow_config = Base.get_flow_config(settings.BASE_DIR/'_keenthemes/view_config.json', 'QuotationsView')

    has_formset = True
    formset_form = QuotationItemForm2
    formset_model = QuotationItem
    formset_fk_field = 'quotation'
    related_name_fk = 'quotation'

    def get_success_url(self):
        return reverse_lazy('micmod_base:quotations.view', kwargs={'pk': self.object.pk})

    def get(self, request, *args, **kwargs):
        if is_ajax(self.request):
            if not self.check_last_update():
                html = render_to_string(self.conflict_template_name, {'conflict': True, 'obj': self.object})
                return JsonResponse({'res': html}, safe=False)
            else:
                return JsonResponse({'res': ''}, safe=False)
        if 'direct' in request.GET:
            self.template_name = 'factor/direct_factor.html'
        return super().get(request, *args, **kwargs)

    def check_last_update(self):
        qis_last_update = (json.loads(self.request.POST.get('qis_last_update_datetime', "{}"))
                           or self.request.GET.get('qis_last_update_datetime'))
        q_last_update = (self.request.POST.get('last_update_datetime')
                         or self.request.GET.get('last_update_datetime').replace(' ', '+'))
        if is_ajax(self.request):
            qis_last_update = json.loads(qis_last_update)

        if q_last_update and self.object.last_update_date.replace(microsecond=0) != datetime.fromisoformat(q_last_update).replace(microsecond=0):
            return False

        for qi in self.object.quotation.all():
            if qi_last_update := qis_last_update.get(str(qi.pk)):
                qi_last_update = qi_last_update.replace(' ', '+')
                if datetime.fromisoformat(qi_last_update).replace(microsecond=0) != qi.last_update_date.replace(microsecond=0):
                    return False
        return True

    def post(self, request, *args, **kwargs):
        if not self.check_last_update():
            return render(request, self.post_conflict_template_name, {'conflict': True, 'obj': self.object})
        if 'duplicate' in self.request.POST:
            obj = duplicate_quotation(self.request, self.object.pk)
            if obj:
                return HttpResponseRedirect(reverse('micmod_base:quotations.view', kwargs={'pk': obj.pk}))
        # if self.object is None:
        #     import_customers_from_sepidar(extra_data={"creator_user_id": 1, "editor_user_id": 1})
        if self.object and self.object.last_work_flow.current_state_name in ['تایید پیش فاکتور'] and 'back' in self.request.POST:
            self.request.POST._mutable = True
            # self.request.POST['sales_admin_confirm'] = ''
            self.object.sales_admin_confirm = False
            self.request.POST._mutable = False
            self.object.save()
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        """ run import customer from sepidar before object create"""
        # if self.object is None:
        #     import_customers_from_sepidar(extra_data={"creator_user_id": 1, "editor_user_id": 1})

        res = super().form_valid(form)
        if 'direct' in self.request.GET:
            return generate_direct_factor(self.request, self.object)
        if 'back' in self.request.POST or 'change_user' in self.request.POST:
            return res
        if not self.object.is_official and not self.request.POST.get('official_value'):
            self.object.official_value = 0

        new_quotation = None
        try:

            device = Device.objects.all().first()
            if not self.object.guid:
                self.object.guid = uuid.uuid4()
            elif (sepidar_pk := self.object.sepidar_quotation_id) and self.state_index == 2 and 'next' in self.request.POST:
                APILogs.new_call(device=device, url=Urls.del_quotation.url.format(sepidar_pk),
                                 method=Urls.del_quotation.method, save=True)

            if (self.state_index == 1 or self.state_index == 1) and 'submit/copy_q' in self.request.POST:
                flow_copy = False

                """copy quotation"""
                for qi in self.object.quotation.all():
                    if bool(qi.local_price_inquiry_done) != bool(qi.need_local_price_inquiry) or \
                            bool(qi.foreign_price_inquiry_done) != bool(qi.need_foreign_price_inquiry):
                        """عبور به مرحله بعد غیر مجاز می‌باشد"""
                        """create new quotation"""
                        quotation_data = dict()
                        pop_quotation_item = ['id', 'guid', 'created_date', 'last_update_date', 'creator_user',
                                              'editor_user']
                        for field in self.model._meta.fields:
                            quotation_data[field.name] = getattr(self.object, field.name, None)
                        [quotation_data.pop(k) for k in pop_quotation_item]

                        quotation_data['quotation_self'] = self.object
                        quotation_data['guid'] = uuid.uuid4()
                        if not new_quotation:
                            new_quotation = self.model.objects.create(**quotation_data)

                            """تمام change log ها کپی بشن (فقط یک بار)"""
                            logs = ChangeLog.get_log(self.object)
                            for log in logs:
                                log.pk = None
                                log.content_type = ContentType.objects.get_for_model(Quotation)
                                log.object_id = new_quotation.pk
                                log.save()

                            """تمام wf ها کپی بشن (فقط یک بار)"""
                            if not flow_copy:
                                flows = self.get_flow(self.object)
                                for idx, flow in enumerate(flows):
                                    if idx == len(flows) - 1:
                                        break
                                    flow.pk = None
                                    flow.object_id = new_quotation.pk
                                    flow.save()
                                    flow_copy = True
                                    new_quotation.last_work_flow = flow

                            """ این آیتم در مرحله استعلام می ماند و wf ثبت نمیکند """
                            # """ این آیتم به مرحله قبل میرود و wf برگشت ثبت میکند """

                            new_quotation.quotation_self = self.object
                            new_quotation.extra_data.request = self.request
                            new_quotation.save()
                            # new_quotation.save_user(self.request)

                        qi.quotation = new_quotation
                        qi.save()

                    else:
                        """به مرحله بعد میرود"""
                        """یک wf به مرحله بعد ثبت میکند"""
                        flow_user_groups = self.flow_config.get('flow_users_groups', [])

            if self.state_index == 2 and ('submit/copy' in self.request.POST or 'next' in self.request.POST or 'submit/copy_q' in self.request.POST):
                """ثبت در سپیدار"""
                quotation_items = []
                for idx, qi in enumerate(self.object.quotation.all(), 1):
                    qi_dict = {
                        'RowID': idx,
                        'ItemRef': qi.goods_code_fk.sepidar_id_0,  # itemid,  # optional
                        'StockRef': 2,  # optional
                        'Quantity': qi.quantity,
                        'SecondaryQuantity': 0,
                        # 'Fee': qi.fee or 1,
                        'Fee': qi.sepidar_fee or 1,
                        'Price': qi.net_price or 1,
                        'Description': qi.description or '',
                        'PriceInfoPercentDiscount': 0,
                        'PriceInfoDiscountRate': 0,
                        'AggregateAmountPercentDiscount': 0,
                        'AggregateAmountPriceDiscount': 0,
                        'AggregateAmountDiscountRate': 0,
                        'CustomerDiscount': 0,
                        'CustomerDiscountRate': 0,
                        'Discount': qi.discount_value or 0, #qi.sepidar_discount * qi.quantity or 0,
                       # 'DiscountParentRef': 1,  # optional
                        'Tax': qi.tax or 0,
                        'Duty': qi.duty or 0,
                        'Addition': self.object.addition if (idx == 1 and self.object.addition) else  0,
                    }
                    quotation_items.append(qi_dict)
                #
                q = Quotation()
                quotation_data = {
                    'GUID': str(self.object.guid),
                    'CurrencyRef': self.object.sale_type.currency.sepidar_id or 1,
                    'Rate': self.object.sale_type.currency.current_rate() or 1,
                    'ExpirationDate': str(self.object.expiration_date),
                    'CustomerRef': self.object.customer_party_id.sepidar_party_id,  # 11
                    'SaleTypeRef': self.object.sale_type.pk,
                  #  'AddressRef': '1',  # optional
                    'DiscountOnCustomer': 0,
                    'Price': self.object.price or 1,
                    'Discount': self.object.total_discount or 0, #self_discount or 0,
                    'Tax': self.object.tax_amount or 0,
                    'Duty': self.object.duty_amount or 0,
                    'Addition': 0, # self.object.addition or 0, TODO sepidar dont save addition for quotation(main form)
                    'items': quotation_items,
                }
                d = json.dumps(quotation_data)
                #
                api_res = APILogs.new_call(device=device, url=Urls.pos_quotations.url,
                                           method=Urls.pos_quotations.method, data=d)
                api_log_obj = api_res[2]
                api_log_obj.extra_data.request = self.request if api_log_obj else ''
                api_log_obj.save()

                self.object.sepidar_quotation_id = api_res[1].get('ID') if api_res[0] == 201 else None
                self.object.sepidar_number = api_res[1].get('Number') if api_res[0] == 201 else None

                sepidar_qis = api_res[1].get('Items')

                if sepidar_qis:
                    """ save sepidar QuotationItemID for qi """
                    lookup = {(d["Quantity"], d["ItemRef"]): d["QuotationItemID"] for d in sepidar_qis}
                    items = list(self.object.quotation.all())

                    for item in items:
                        key = (item.quantity, item.goods_code_fk.sepidar_id_0)
                        if key in lookup:
                            item.sepidar_id = lookup[key]

                    QuotationItem.objects.bulk_update(items, ["sepidar_id"])

                if api_res[0] >= 400:
                    from django.contrib import messages

                    messages.add_message(self.request, messages.ERROR, api_res[1].get('Message'))
                    print('rol back .... for status 400')
                    content_type = ContentType.objects.filter(model=self.object._meta.model_name,
                                                              app_label=self.object._meta.app_label).first()
                    flow_object = self.flow_model.objects.filter(object_id=self.object.id,
                                                                 content_type=content_type).first()
                    if flow_object:
                        flow_object.is_deleted = True
                        flow_object.save()
            if ((self.state_index == 0 and 'next' in self.request.POST) or (self.state_index == 2 and 'back' in self.request.POST)):
                ...
            self.object.save()
        except Exception as e:
            pass
            print('rol back ....')
            content_type = ContentType.objects.filter(model=self.object._meta.model_name, app_label=self.object._meta.app_label).first()
            flow_object = self.flow_model.objects.filter(object_id=self.object.id, content_type=content_type).first()
            if flow_object:
                flow_object.is_deleted = True
                flow_object.save()
        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['heading'] = _('create')
        context['pageview'] = _('quotation')

        context['section_id'] = 'quotation'
        last_update_datetime = self.object.last_update_date.isoformat() if self.object else ''

        context['last_update_datetime'] = last_update_datetime
        qis = {qi.pk: qi.last_update_date.isoformat() for qi in self.object.quotation.all()} if self.object else {}
        context['qis_last_update_datetime'] = json.dumps(qis)
        user_groups = self.request.user.groups.values_list('name', flat=True)
        if self.object:
            for qi in self.object.quotation.all():
                if not qi.price_json:
                    qi.create_price_json_for_old_qi()
            self.object.created_date = datetime2jalali(self.object.created_date).strftime('%y/%m/%d-%H:%M')
            self.object.last_update_date = datetime2jalali(self.object.last_update_date).strftime('%y/%m/%d-%H:%M')
        context['data'] = self.object
        context['app_name'] = self.request.resolver_match.app_name
        context['duplicate'] = True

        if self.object:
            qis = self.object.quotation.all()
            counter = 0
            for qi in qis:
                if (self.state_index == 1 or self.state_index == 1) and (bool(qi.local_price_inquiry_done) != bool(qi.need_local_price_inquiry) or \
                        bool(qi.foreign_price_inquiry_done) != bool(qi.need_foreign_price_inquiry)):
                    counter += 1
                    context['allow_next'] = False
                    context['submit_copy_q'] = True
            if counter == len(qis):
                context['submit_copy_q'] = False
        if self.object and self.object.cancel:
            context['comment_form'] = CommentsForm(initial={'submit_type': 'uncanceled'})
        else:
            context['comment_form'] = CommentsForm(initial={'submit_type': 'cancel'})
        for f in context['formset']:
            if f.instance.comments.filter(comment_title__in=['L', 'M', 'N']):
                f.has_alt_code = True
        factors = self.object.q.all() if self.object else None
        if factors and factors.exists():
            context['form'].enable = False
            context['factors'] = factors

        ps = PriceSettings.objects.none()
        for user_group in self.request.user.groups.values_list('name', flat=True):
            ps |= PriceSettings.objects.filter(Q(permission_json__group__icontains=user_group))
        ps |= PriceSettings.objects.filter(
            Q(permission_json__user__icontains='all') | Q(permission_json__user__icontains=self.request.user.username))
        context['q_price_settings'] = ps
        return context


def print_view(request,id=-1):
    customer_print = reverse("micmod_base:print_customer", args=[id])
    if request.META.get('PATH_INFO') == customer_print:
        template_name = 'micmod-base/quotation/view-print-raw.html'
    else:
        template_name = 'micmod-base/quotation/view-print.html'
    comments_url_params = '0'
    with_comments = '1'
    with_alt_code = '0'
    alt_code = '1'
    with_customer_goods_code = '0'
    customer_goods_code_url_param = '1'
    if request.GET.get('comments_url_params') == '1':
        with_comments = '1'
        comments_url_params = '0'
    elif request.GET.get('comments_url_params') == '0':
        with_comments = '0'
        comments_url_params = '1'
    if request.GET.get('alt_code') == '1':
        with_alt_code = '1'
        alt_code = '0'
    elif request.GET.get('alt_code') == '0':
        with_alt_code = '0'
        alt_code = '1'
    if request.GET.get('customer_goods_code_url_param') == '1':
        with_customer_goods_code = '1'
        customer_goods_code_url_param = '0'
    elif request.GET.get('customer_goods_code_url_param') == '0':
        with_customer_goods_code = '0'
        customer_goods_code_url_param = '1'

    formset = inlineformset_factory(Quotation, QuotationItem, form=QuotationItemForm2, extra=0, )
    greeting = {}
    greeting['alt_code_html'] = []
    greeting['heading'] = _("create")
    greeting['pageview'] = _("quotation")
    greeting['with_comments'] = with_comments
    greeting['comments_url_params'] = comments_url_params
    greeting['with_alt_code'] = with_alt_code
    greeting['alt_code'] = alt_code
    greeting['customer_goods_code_url_param'] = customer_goods_code_url_param
    greeting['with_customer_goods_code'] = with_customer_goods_code
    quotation = Quotation.objects.filter(id=id).first()
    greeting['form'] = QuotationForm(instance=quotation)
    greeting['formset'] = formset(instance=quotation,
                                  form_kwargs={
                                      "constraint": {
                                          "wf_access": True,
                                          'form_state': 0,
                                          'request': request,

                                      }
                                  }
                                  )
    for f in greeting['formset']:
        if f.instance.sales_description:
            greeting['has_sales_description'] = True
        f.alt_codes_html = []
        if alt_qs := f.instance.comments.filter(comment_title__in=['L', 'M', 'N']):
            for alt_comment in alt_qs:
                comment_str_lower = alt_comment.comment_content.lower()
                pattern_pk = r'sku_(\d+)'
                pks = re.findall(pattern_pk, comment_str_lower)
                sku_item = Item.objects.filter(pk__in=pks).first()
                try:
                    if sku_item:
                        item = dict()
                        item['obj'] = sku_item
                        item['quotation'] = f.instance.quotation
                        price_inquiry_result = sku_item.price if sku_item else None
                        price_inquiry_result_bazar = sku_item.bazar_price if sku_item else None
                        id_currency_ref = f.instance.quotation.currency_ref.pk
                        id_customer_grade = f.instance.quotation.customer_grade
                        id_customer_grade = id_customer_grade.split(',')[-1] if id_customer_grade else None
                        id_payment_method = f.instance.quotation.payment_method
                        id_payment_method = id_payment_method.split(',')[-1] if id_payment_method else None
                        quantity = f.instance.quantity
                        if price_inquiry_result:
                            price_setting = price_inquiry_result.price_settings
                            price_inquiry_result.set_discount_params(
                                quantity=quantity,
                                customer_grade=id_customer_grade,
                                payment_method=id_payment_method,
                                currency=id_currency_ref,
                                price_setting=price_setting
                            )
                            item["price_settings"] = price_setting.pk
                            if str(id_currency_ref) == str(1):  # rial
                                item["rial_final_price"] = price_inquiry_result.rial_final_price
                                item["rial_final_price_new_order"] = price_inquiry_result.rial_final_price_new_order
                            elif str(id_currency_ref) == str(2):  # rmb
                                item['rmb_final_price'] = price_inquiry_result.rmb_final_price
                            item["price_update_date"] = to_jalali(price_inquiry_result.price_update_date, "%Y-%m-%d")
                        else:
                            item["rial_final_price"] = {'express': None, 'air': None, 'sea': None}
                            item["rial_final_price_new_order"] = {'express': None, 'air': None, 'sea': None}

                        if price_inquiry_result_bazar:
                            price_setting = price_inquiry_result_bazar.price_settings
                            price_inquiry_result_bazar.set_discount_params(
                                quantity=quantity,
                                customer_grade=id_customer_grade,
                                payment_method=id_payment_method,
                                currency=id_currency_ref,
                                price_setting=price_setting
                            )
                            item["goods_price_market"] = price_inquiry_result_bazar.bazar_price
                            item["goods_market_date"] = to_jalali(price_inquiry_result_bazar.price_update_date, "%Y-%m-%d")
                            item["price_update_date"] = to_jalali(price_inquiry_result_bazar.price_update_date, "%Y-%m-%d")
                        else:
                            item["goods_price_market"] = None
                            item["goods_market_date"] = None
                        # render html
                        html = render_to_string('micmod-base/quotation/partial/alt_code_print.html', context=item)
                        f.alt_codes_html.append(html)
                except Exception as e:
                    show_error(e, __file__)
    if quotation:
        quotation.created_date = datetime2jalali(quotation.created_date).strftime('%y/%m/%d-%H:%M')
        quotation.last_update_date = datetime2jalali(quotation.last_update_date).strftime('%y/%m/%d-%H:%M')
    greeting['data'] = quotation
    return render(request, template_name, greeting)


class CurrencyExchangeView(LoginRequiredMixin, BaseView):
    model = CurrencyExchange
    form_class = CurrencyExchangeForm
    template_name = 'micmod-base/currency_exchange_list_or_create.html'
    success_url = reverse_lazy('micmod_base:currency_exchange')

    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class CurrencyExchangeDataTableView(AjaxDatatableView):
    model = CurrencyExchange
    title = 'currency_list'
    initial_order = [["last_update_date", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'currency', 'visible': True, 'title': _('currency'), 'className': 'py-1 border currency-search', 'lookup_field': '__title__icontains'},
        {'name': 'buy_exchange', 'visible': True, 'title': _('buy_exchange'), 'className': 'py-1 border'},
        {'name': 'sell_exchange', 'visible': True, 'title': _('sell_exchange'), 'className': 'py-1 border'},
        {'name': 'id', 'visible': False, },
        {'name': 'last_update_date', 'visible': False, 'orderable': True},
    ]

    def get_initial_queryset(self, request=None):
        param: str = self.request.POST.get('sku')
        try:
            if param and param.isdigit():
                param = int(param)
            else:
                param = ''
        except TypeError as e:
            show_error(e, __file__)
        if param:
            qs = self.model.objects.filter(sku=param)
        else:
            qs = self.model.objects.all()
        return qs.order_by('last_update_date')

    def customize_row(self, row, obj):
        row['currency'] = '<a class="fw-bold" href="%s">%s</a>' % (
                      reverse('micmod_base:currency_exchange', args=(obj.id,)),
                      obj.currency if obj.currency else '_'
                    )


class QuotationItemPending(LoginRequiredMixin, View):
    def get(self, request):
        q = self.request.GET.get('q')

        if q == 'local':
            quotations_record_lst = QuotationItem.objects.filter(Q(local_price_inquiry_done=True) &
                                         Q(need_local_price_inquiry=False) |
                                         Q(local_price_inquiry_done=False) &
                                         Q(need_local_price_inquiry=True)
                                         )
        elif q == 'foreign':
            quotations_record_lst = QuotationItem.objects.filter(Q(foreign_price_inquiry_done=True) &
                                         Q(need_foreign_price_inquiry=False) |
                                         Q(foreign_price_inquiry_done=False) &
                                         Q(need_foreign_price_inquiry=True))
        else:
            quotations_record_lst = QuotationItem.objects.filter(
                Q(local_price_inquiry_done=True) & Q(need_local_price_inquiry=False) |
                Q(local_price_inquiry_done=False) & Q(need_local_price_inquiry=True) |
                Q(foreign_price_inquiry_done=True) & Q(need_foreign_price_inquiry=False) |
                Q(foreign_price_inquiry_done=False) & Q(need_foreign_price_inquiry=True)
            )


        greeting = {}
        greeting['heading'] = _("quotation")
        greeting['pageview'] = _("micmod_base")
        greeting['quotationitems'] = quotations_record_lst

        return render(request,'micmod-base/quotation/pending_list.html',greeting)


class QuotationItemFormPending(LoginRequiredMixin, View):
    template_name = 'micmod-base/quotation/form_pending_list.html'
    form_struct = {
        'form': QuotationItemForm2,
        'childes': [
            {
                'form': InquiryResultForm,
                'childes': [{}]
            },
        ]
    }
    flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json', 'QuotationItemsFormPendingView')

    def get(self, request):
        from django.core.paginator import Paginator
        context = dict()
        context['heading'] = _("quotation")
        context['pageview'] = _("micmod_base")
        forms = list()
        form_list = list()

        quotation = request.GET.get('quotation')
        customer_code = request.GET.get('customer_code')
        my_quotations = request.GET.get('my_quotations')
        search_sku = request.GET.get('search_sku')

        if quotation:
            quotations_record_lst = Quotation.quotation_pending(self.request, filter={'pk': quotation})
        elif customer_code:
            quotations_record_lst = Quotation.quotation_pending(self.request, filter={'customer_code': customer_code})

        elif self.request.GET.get('choice') == 'my_quotations':
            quotations_record_lst = Quotation.quotation_pending(self.request, extra_filter={'my_quotations': True})
        elif search_sku:
            quotations_record_lst = Quotation.quotation_pending(self.request,
                                                                extra_filter={'goods_code': search_sku})
        elif self.request.GET.get('choice') == 'my_inquiry_not_started':
            quotations_record_lst = Quotation.quotation_pending(self.request,
                                                                extra_filter={'my_inquiry_not_started': True})
        elif self.request.GET.get('choice') == 'inquiry_not_assigned':
            quotations_record_lst = Quotation.quotation_pending(self.request,
                                                                extra_filter={'inquiry_not_assigned': True})

        else:
            quotations_record_lst = Quotation.quotation_pending(self.request)

        for qi_qs in quotations_record_lst:
            for qi in qi_qs:
                form = QuotationItemForm2(instance=qi, initial={
                    "constraint": {
                        "wf_access": True,
                        'form_state': 0,
                        'request': self.request,
                        'form_constraint': self.flow_config.get('flow_form_constraint'),
                        'formset_constraint': self.flow_config.get('flow_formset_constraint')
                    }
                })
                form.nested = InquiryResultForm(instance=qi.quotation_item_rel.first())
                form.enable = False
                forms.append(form)
            form_list.append(forms)
            forms = []

        paginator = Paginator(form_list, 10)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)
        context['page_obj'] = page_obj
        context['forms'] = form_list
        form_filter = PendingFormFilter()
        context['form_filter'] = form_filter
        return render(request, self.template_name, context)

    def post(self, request):
        if obj_pk := self.request.POST.get('obj_pk'):
            obj_qs = QuotationItem.objects.filter(pk=obj_pk)
            obj = obj_qs.first()
            obj.save_comment(self.request)

            new_goods_code = self.request.POST.get('goods_code')
            if new_goods_code and new_goods_code != obj.goods_code:
                obj.old_goods_code = obj.goods_code
                obj.goods_code = new_goods_code
                obj.old_goods_name = obj.goods_name
                obj.item_editor_user = self.request.user
                obj.save()

            if self.request.POST.get('foreign_price_inquiry_done'):
                obj.foreign_price_inquiry_done = True
                obj.save()
            if self.request.POST.get('local_price_inquiry_done'):
                obj.local_price_inquiry_done = True
                obj.save()

            data = {
                'lead_time': request.POST.get('lead_time'),
                'goods_code': request.POST.get('goods_code'),
                'goods_name': request.POST.get('goods_name'),
            }
            obj_qs.update(**data)

            iqr_obj = obj.quotation_item_rel.first()
            iqr_form = InquiryResultForm(self.request.POST, instance=iqr_obj)
            if iqr_form.is_valid():
                iqr_obj = iqr_form.save()
                iqr_obj.quotation_item = obj
                iqr_obj.save()
        redirect_path = self.request.META.get('HTTP_REFERER', None) or reverse('micmod_base:quotationitem.form.pending')
        return redirect(redirect_path)


class QuotationItemFormPending2(LoginRequiredMixin, View):
    template_name = 'micmod-base/quotation/form_pending_list2.html'
    form_struct = {
        'form': QuotationItemForm2,
        'childes': [
            {
                'form': InquiryResultForm,
                'childes': [{}]
            },
        ]
    }
    flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json', 'QuotationItemsFormPendingView')

    def get(self, request):
        from django.core.paginator import Paginator
        filter_form = PendingFormFilter(self.request.GET)
        filter_form.is_valid()
        context = dict()
        context['heading'] = _("quotation")
        context['pageview'] = _("micmod_base")
        forms = list()

        quotation = request.GET.get('quotation')
        customer_code = request.GET.get('customer_code')
        customer_name = request.GET.get('customer_name')
        my_quotations = request.GET.get('my_quotations')
        my_inquiry_not_started = request.GET.get('my_inquiry_not_started')
        inquiry_not_assigned = request.GET.get('inquiry_not_assigned')
        search_sku = request.GET.get('search_sku')
        search_part_number = request.GET.get('search_part_number')
        force_inquiry = request.GET.get('force_inquiry')
        time_range = request.GET.get('time_range')
        from_time = self.request.GET.get('from_time')
        to_time = self.request.GET.get('to_time')

        quotations_record_lst = QuotationItem.objects.none()

        if self.request.user.is_superuser:
            quotations_record_lst = QuotationItem.quotation_item_all_pending(inquiry_type=None, path=self.request.path)
        if self.request.user.base_group and 'trade' in self.request.user.base_group:
            quotations_record_lst = QuotationItem.quotation_item_all_pending(inquiry_type='trade', path=self.request.path)
        if self.request.user.base_group and 'bazar' in self.request.user.base_group:
            quotations_record_lst = QuotationItem.quotation_item_all_pending(inquiry_type='bazar', path=self.request.path)
        if quotation:
            quotations_record_lst = quotations_record_lst.filter(quotation=quotation)
        elif customer_code:
            quotations_record_lst = quotations_record_lst.filter(quotation__customer_code=customer_code)
        elif self.request.GET.get('choice') == 'my_quotations' or my_quotations:
            f = Q(assigned_trade_user=request.user) | Q(assigned_trade_user2=request.user)
            quotations_record_lst = quotations_record_lst.filter(f)
        elif search_sku:
            quotations_record_lst = quotations_record_lst.filter(goods_code=search_sku)
        elif self.request.GET.get('choice') == 'my_inquiry_not_started' or my_inquiry_not_started:
            f = (Q(assigned_trade_user=request.user) & Q(task_start=False)) | \
                (Q(assigned_trade_user2=request.user) & Q(task_start2=False))
            quotations_record_lst = quotations_record_lst.filter(f)
        elif self.request.GET.get('choice') == 'inquiry_not_assigned' or inquiry_not_assigned:
            f = Q(assigned_trade_user__isnull=True) & Q(assigned_trade_user2__isnull=True)
            quotations_record_lst = quotations_record_lst.filter(f)
        elif force_inquiry:
            f = {'quotation__force_inquiry': True}
            quotations_record_lst = quotations_record_lst.filter(**f)
        elif self.request.GET.get('item_in_china'):
            quotations_record_lst = quotations_record_lst.filter(item_in_china=True)

        elif self.request.GET.get('from_time') or self.request.GET.get('to_time'):
            quotations_record_lst = quotations_record_lst.filter(quotation__created_date__range=[filter_form.cleaned_data.get('from_time'),filter_form.cleaned_data.get('to_time')])
        elif self.request.GET.get('choice') == 'search_part_number' or search_part_number:
            quotations_record_lst = quotations_record_lst.filter(goods_code_fk__part_number__icontains=search_part_number)
        elif self.request.GET.get('choice') == 'customer_name' or customer_name:
            customer_filter = (Q(quotation__customer_party_id__title__icontains=customer_name) |
                               Q(quotation__customer_party_id__name__icontains=customer_name) |
                               Q(quotation__customer_party_id__last_name__icontains=customer_name))
            quotations_record_lst = quotations_record_lst.filter(customer_filter)
        else:
            quotations_record_lst = quotations_record_lst

        quotations_record_lst = quotations_record_lst.order_by('-quotation_id', 'id')

        paginator = Paginator(quotations_record_lst, 10)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        for qi in page_obj.object_list:
        #for qi in quotations_record_lst:
            form = QuotationItemForm2(instance=qi, initial={
                "constraint": {
                    "wf_access": True,
                    'form_state': 0,
                    'request': self.request,
                    'form_constraint': self.flow_config.get('flow_form_constraint'),
                    'formset_constraint': self.flow_config.get('flow_formset_constraint')
                }
            })
            form.nested = InquiryResultForm(instance=qi.quotation_item_rel.order_by('id').first())
            form.enable = False
            forms.append(form)

        d = dict()
        for item in forms:
            if not d.get(item.instance.quotation.pk):
                d[item.instance.quotation.pk] = []
            repeated_goods_code = quotations_record_lst.filter(goods_code_fk=item.instance.goods_code_fk).aggregate(Sum('quantity'), Count('id'))
            count = repeated_goods_code.get('id__count')
            if count > 1:
                html = f"""<div class="mt-3 py-2 px-1 rounded hover_light_primary"><a href="/micmod_base/quotationitem/list/form/pending/?choice=search_sku&search_sku={item.instance.goods_code_fk}">
                <span class="">{count}</span> 
                <span class="me-3"> درخواست تکراری</span>
                <span> جمع کل </span>
                :
                <span>{repeated_goods_code.get('quantity__sum')}<span>
                </a></div>"""
                item.repeated_goods_code_count = html
            d[item.instance.quotation.pk].append(item)

        inquiry = QuotationItem.inquiry_not_started(request.user)
        # my_inquiry_not_started = inquiry[0]
        # inquiry_not_started_count = inquiry[1]

        per_page = page_obj.paginator.per_page
        context['page_obj'] = page_obj
        context['item_count'] = page_obj.number * per_page - (per_page - len(page_obj.object_list))
        context['forms'] = forms
        context['d'] = d
        context['zip_data'] = zip(page_obj, d)
        form_filter = PendingFormFilter()
        context['form_filter'] = form_filter
        context['app_name'] = self.request.resolver_match.app_name
        context['section_id'] = 'inquiry'
        # context['my_inquiry_not_started'] = my_inquiry_not_started
        # context['inquiry_not_started_count'] = inquiry_not_started_count
        return render(request, self.template_name, context)

    def post(self, request):
        if obj_pk := self.request.POST.get('obj_pk'):
            obj_qs = QuotationItem.objects.full_queryset(pk=obj_pk)
            obj = obj_qs.first()
            # obj.save_comment(self.request, CommentsForm)
            obj.save_comment_(self.request)

            new_goods_code = self.request.POST.get('goods_code')
            if new_goods_code and new_goods_code != obj.goods_code:
                obj.old_goods_code = obj.goods_code
                obj.goods_code = new_goods_code
                obj.old_goods_name = obj.goods_name
                obj.goods_code_fk = Item.objects.filter(sku=new_goods_code).first()

                from sepidar.models import Item as sepidar_item
                items = sepidar_item.get_item(new_goods_code)
                for item_ in items:
                    try:
                        obj.itemid = item_.itemid
                        obj.stock_amount = item_.stock_qty
                        obj.stock_amount_res = item_.stock_res_qty
                    except Exception as e:
                        pass
                obj.item_editor_user = self.request.user
                # obj.extra_data.request = self.request
                # obj.save()

            if self.request.POST.get('foreign_price_inquiry_done'):
                obj.foreign_price_inquiry_done = True
                obj.foreign_price_inquiry_done_date = timezone.now()
                # obj.extra_data.request = self.request
                # obj.save()
            # elif obj.need_foreign_price_inquiry and not self.request.POST.get('foreign_price_inquiry_done'):
                # obj.foreign_price_inquiry_done = False
                # obj.save()
            if self.request.POST.get('local_price_inquiry_done'):
                obj.local_price_inquiry_done = True
                obj.local_price_inquiry_done_date = timezone.now()
                # obj.extra_data.request = self.request
                # obj.save()
            # elif self.request.POST.get('need_local_price_inquiry') and not self.request.POST.get('local_price_inquiry_done'):
                # obj.local_price_inquiry_done = False
                # obj.extra_data.request = self.request
                # obj.save()

            if self.request.user.base_group == 'trade':
                data = {
                    'lead_time': request.POST.get('lead_time') or obj.lead_time,
                    'goods_code': request.POST.get('goods_code'),
                    'goods_name': request.POST.get('goods_name'),
                    'has_delay': True if request.POST.get('has_delay') else False,
                    'delay_reason': request.POST.get('delay_reason') or '',
                    'delay_time': request.POST.get('delay_time') or '',
                }
                obj_for_update = obj_qs.first()
                if obj_for_update:
                    obj.lead_time = data['lead_time']
                    obj.goods_code = data['goods_code']
                    obj.goods_name = data['goods_name']
                    obj.has_delay = data['has_delay']
                    obj.delay_reason = data['delay_reason']
                    obj.delay_time = data['delay_time']
                    # obj_for_update.extra_data.request = self.request
                    # obj_for_update.save()
            obj.extra_data.request = self.request
            obj.save()

            iqr_obj = obj.quotation_item_rel.first()
            iqr_form = InquiryResultForm(self.request.POST, instance=iqr_obj)
            if iqr_form.is_valid():
                iqr_obj = iqr_form.save()
                iqr_obj.quotation_item = obj
                iqr_obj.extra_data.request = self.request
                iqr_obj.save()
        redirect_path = self.request.META.get('HTTP_REFERER', None) or reverse('micmod_base:quotationitem.form.pending')
        return redirect(redirect_path)


class MyQuotationItemFormPendingToday(LoginRequiredMixin, View):
    template_name = 'micmod-base/quotation/form_pending_list.html'
    form_struct = {
        'form': QuotationItemForm2,
        'childes': [
            {
                'form': InquiryResultForm,
                'childes': [{}]
            },
        ]
    }
    flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json',
                                       'QuotationItemsFormPendingView')

    def get(self, request):
        from django.core.paginator import Paginator
        context = dict()
        context['heading'] = _("quotation")
        context['pageview'] = _("micmod_base")
        forms = list()
        form_list = list()

        quotation = request.GET.get('quotation')
        customer_code = request.GET.get('customer_code')
        my_quotations = request.GET.get('my_quotations')
        search_sku = request.GET.get('search_sku')

        if quotation:
            quotations_record_lst = Quotation.quotation_pending(self.request, filter={'pk': quotation})
        elif customer_code:
            quotations_record_lst = Quotation.quotation_pending(self.request, filter={'customer_code': customer_code})

        elif self.request.GET.get('choice') == 'my_quotations':
            quotations_record_lst = Quotation.quotation_pending(self.request, extra_filter={'my_quotations': True})
        elif search_sku:
            quotations_record_lst = Quotation.quotation_pending(self.request,
                                                                extra_filter={'goods_code': search_sku})
        elif self.request.GET.get('choice') == 'my_inquiry_not_started':
            quotations_record_lst = Quotation.quotation_pending(self.request,
                                                                extra_filter={'my_inquiry_not_started': True})
        else:
            quotations_record_lst = Quotation.quotation_pending(self.request)

        for qi_qs in quotations_record_lst:
            for qi in qi_qs:
                form = QuotationItemForm2(instance=qi, initial={
                    "constraint": {
                        "wf_access": True,
                        'form_state': 0,
                        'request': self.request,
                        'form_constraint': self.flow_config.get('flow_form_constraint'),
                        'formset_constraint': self.flow_config.get('flow_formset_constraint')
                    }
                })
                form.nested = InquiryResultForm(instance=qi.quotation_item_rel.first())
                form.enable = False
                forms.append(form)
            form_list.append(forms)
            forms = []

        paginator = Paginator(form_list, 10)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)
        context['page_obj'] = page_obj
        context['forms'] = form_list
        form_filter = PendingFormFilter()
        context['form_filter'] = form_filter
        return render(request, self.template_name, context)

    def post(self, request):
        if obj_pk := self.request.POST.get('obj_pk'):
            obj_qs = QuotationItem.objects.filter(pk=obj_pk)
            obj = obj_qs.first()
            obj.save_comment(self.request)

            new_goods_code = self.request.POST.get('goods_code')
            if new_goods_code and new_goods_code != obj.goods_code:
                obj.old_goods_code = obj.goods_code
                obj.goods_code = new_goods_code
                obj.old_goods_name = obj.goods_name
                obj.item_editor_user = self.request.user
                obj.save()

            if self.request.POST.get('foreign_price_inquiry_done'):
                obj.foreign_price_inquiry_done = True
                obj.save()
            if self.request.POST.get('local_price_inquiry_done'):
                obj.local_price_inquiry_done = True
                obj.save()

            data = {
                'lead_time': request.POST.get('lead_time'),
                'goods_code': request.POST.get('goods_code'),
                'goods_name': request.POST.get('goods_name'),
            }
            obj_qs.update(**data)

            iqr_obj = obj.quotation_item_rel.first()
            iqr_form = InquiryResultForm(self.request.POST, instance=iqr_obj)
            if iqr_form.is_valid():
                iqr_obj = iqr_form.save()
                iqr_obj.quotation_item = obj
                iqr_obj.save()
        redirect_path = self.request.META.get('HTTP_REFERER', None) or reverse('micmod_base:quotationitem.form.pending')
        return redirect(redirect_path)

def get_sku(request):
    sku = request.GET.get('sku')
    sku_qs = Item.objects.filter(sku=sku).first()
    if sku_qs:
        return JsonResponse({'res': sku_qs.sku, 'id': sku_qs.pk, 'part_number': sku_qs.part_number})
    else:
        return JsonResponse({})


class QuotationListDatatable(CustomAjaxDatatableView):
    model = Quotation
    title = 'currency_list'
    initial_order = [["pk", "desc"], ]
    length_menu = [[6, 10, 15, 50, -1], [6, 10, 15, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    # def get_render_row_details_template_name(self, request, *args, **kwargs):
    #     return 'quotation_quik_edit.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'factor_create', 'orderable': False, 'visible': True, 'searchable': False, 'title': '<div class="px-0">ایجاد فاکتور</div>', 'className': 'py-1 border currency-search'},
        {'name': 'pk', 'visible': True, 'title': _('code'), 'className': 'py-1 border currency-search'},
        {'name': 'id', 'visible': False, },
        {'name': 'title', 'visible': True, 'title': _('title'), 'className': 'py-1 border', 'lookup_field': '__icontains', 'searchable': False},
        {'name': 'customer_party_id', 'visible': True, 'title': _('customer_name'), 'className': 'py-1 border', 'orderable': False, 'lookup_field': '__title__icontains'},
        {'name': 'created_date', 'title': '<div class="px-2">تاریخ ایجاد</div>', 'visible': True, 'orderable': True, 'searchable': False},
        {'name': 'expiration_date', 'title': '<div class="px-2">تاریخ انقضا</div>', 'visible': True, 'orderable': True, 'searchable': False},
        {'name': 'creator_user', 'visible': True, 'orderable': True, 'lookup_field': '__profile__first_name__icontains'},
        {'name': 'last_work_flow__to_user', 'title': 'متعلق به', 'visible': True, 'orderable': True, 'lookup_field': '__profile__first_name__icontains'},
        {'name': 'description', 'visible': True, 'orderable': True, 'searchable': False, 'title': '<div style="width:100px;">توضیحات</div>'},
        {'name': 'inquiry_status', 'title': 'وضعیت استعلام', 'visible': True, 'orderable': False, 'searchable': False},
        {'name': 'not_over', 'title': 'وضعیت استهلاک','visible': True, 'orderable': False, 'searchable': False},
        {'name': 'last_work_flow','title': 'آخرین وضعیت', 'visible': True, 'orderable': True, 'lookup_field': '__current_state_name__icontains'},
        {'name': 'sepidar_number', 'title': "کد سپیدار", 'visible': True, 'orderable': True},
        {'name': 'cancel', 'visible': True, 'orderable': True},
        {'name': 'comment', 'visible': True, 'title': '<div class="px-10">نظرات</div>', 'searchable': False},
        {'name': 'description_sales', 'visible': True, 'title': '<div class="px-10">توضیحات فروش</div>', 'searchable': True},
        {'name': 'quotation__goods_code_fk', 'visible': True, 'title': '<div class="px-1">جستجوی کالا</div>', 'searchable': True, 'lookup_field': '__sku__iexact'},
        {'name': 'sales_admin_confirm', 'visible': True, 'orderable': True},
    ]

    def get_initial_queryset(self, request=None):
        if request.user.base_group == 'trade':
            qs = Quotation.objects.filter(cancel=True, is_deleted=False,
                                          quotation__need_foreign_price_inquiry=True,
                                          quotation__foreign_price_inquiry_done=True)
        else:
            qs = Quotation.get_qs(request)
        qs = self.model.objects.filter(pk__in=[i.pk for i in qs])
        return qs

    # @timer
    def customize_row(self, row, obj):
        qi_comments = [x.comments.all() for x in obj.quotation.all()]
        c = 0
        for qs in qi_comments:
            for comment in qs:
                if not comment.commentseen_set.all():
                    c += 1
        for comment in obj.comments.all():
            if not comment.commentseen_set.all():
                c += 1
        if c > 0:
            row['comment'] = f'<span class="bg-success rounded px-2">{c} کامنت جدید</span>'
        else:
            row['comment'] = f'{c} کامنت جدید'

        out = ''
        # for idx, item in enumerate(obj.quotation.all()):
        #     out += str(item.goods_code_fk.sku) + ", "
        #     if idx == 2:
        #         break
        row['quotation__goods_code_fk'] = '-'

        row['last_work_flow__to_user'] = obj.last_work_flow.to_user.profile.first_name if obj.last_work_flow else ''
        row['customer_party_id'] = '<a class="fw-bold" href="%s" target="_blank">%s</a>' % (
            reverse('extra_data:customer.update', args=(obj.customer_party_id.id,)),
            obj.customer_party_id.title if obj.customer_party_id else '-'
        )

        counter = obj.get_inquiry_result_count
        over = obj.not_over_q

        local_color_condition = counter[1] == counter[2] and counter[1] != 0
        foreign_color_condition = counter[3] == counter[4] and counter[3] != 0
        out = f'''<span> کل: {counter[0]} </span > <br>''' \
              + f'''<p {'class="bg-success rounded mb-1"' if local_color_condition else 'class="mb-1"'}>
              داخلی
              {counter[1]} /  {counter[2]} </p>''' \
              + f''' <p {'class="bg-success rounded mb-1"' if foreign_color_condition else 'class="mb-1"'}>
              خارجی
              {counter[3]} / {counter[4]} </p> '''
        row['inquiry_status'] = out

        row['title'] = '<a class="fw-bold" href="%s" target="_blank">%s</a>' % (
            reverse('micmod_base:quotations.view', args=(obj.id,)),
            obj.title if obj.title else '_'
        )
        row['factor_create'] = f'<a class="fw-bold" href="{reverse("factor:factor.view")}?q_id={obj.id}" target="_blank"><i class="ki-duotone ki-plus-circle fs-2"><span class="path1"></span><span class="path2"></span></i></a>'

        row['created_date'] = '%s' % to_jalali_date(obj.created_date)
        row['expiration_date'] = '%s' % to_jalali_date(obj.expiration_date)
        result = f'''<span class="mb-1">
        <span class="font-size-10">فاکتور شده</span>
        <span class="badge badge-success rounded font-size-10">{over[0]}</span><br>
        <span class="font-size-10">مستهلک شده</span>
        <span class="badge badge-warning rounded font-size-10">{over[1]}</span>
        <span class="font-size-10 pt-2">سفارش</span>
        <span class="badge badge-info rounded font-size-10">10</span><br>
        <span class="font-size-10 pt-2">انبار</span>
        <span class="badge badge-warning rounded font-size-10">30</span>
         </span>'''

        res = f'''
        <div class="d-flex flex-column">
            <div class="d-flex justify-content-between">
                <span>
                    <i class="ki-duotone ki-cross text-danger">
                     <span class="path1"></span>
                     <span class="path2"></span>
                    </i>
                </span>
                <span class="">
                    <i class="ki-duotone ki-information-5 text-warning">
                     <span class="path1"></span>
                     <span class="path2"></span>
                     <span class="path3"></span>
                    </i>
                </span>
                <span>
                    <i class="ki-duotone ki-check text-success"></i>
                </span>
            </div>
            <div class="d-flex justify-content-between">
                <span>{over[5]}</span>
                <span>{over[1]}</span>
                <span>{over[0]}</span>
            </div>
            <!--
            <hr>
            <div class="d-flex justify-content-between">
                <span>{over[2]}</span>
                <span>{over[3]}</span>
                <span>{over[4]}</span>
            </div>
            -->
        </div>
        '''
        row['not_over'] = res
        cancel_obj = obj.comments.filter(~Q(comment_title='O')).order_by('id').last()
        if obj.cancel:
            row['cancel'] = f'''<span class="text-danger">{cancel_obj.get_comment_title_display() if cancel_obj else 'cancel'} </span><span>{cancel_obj.comment_content if cancel_obj else 'علت کنسلی نیاز به بررسی دارد!!!' }</span>'''
        else:
            row['cancel'] = '-'


def inquiry_report(request):
    from .models import QuotationItem
    inquiry_report_call = QuotationItem.get_inquiry_report()
    res = render_to_string('micmod-base/quotation/partial/inquiry_report_filter.html', context={'quotationitem_filters':inquiry_report_call})
    return JsonResponse({'res': res}, safe=False)


def repeated_goods_code_view(request):
    from collections import Counter
    base_group = request.user.base_group
    qi = QuotationItem.quotation_item_all_pending(base_group)

    # repeated_goods_code_qi = qi.order_by('goods_code_fk_id').values('goods_code').annotate(goods_code_count=Count('goods_code')).filter(
    #     goods_code_count__gt=1)
    # repeated_goods_code = repeated_goods_code_qi.values_list('goods_code', 'goods_code_count')
    # repeated_codes = list(repeated_goods_code)
    repeated_codes = filter(lambda x: x[1] > 1, Counter([i.goods_code_fk.sku for i in qi]).items())
    res = render_to_string('micmod-base/quotation/partial/repeated_goods_code.html',
                           context={'repeated_goods_code': repeated_codes})
    return JsonResponse({'res': res}, safe=False)


def save_parent_item(request):
    import json
    data = json.loads(request.body)
    item_sku = data.get('item')
    parent_sku = data.get('parent')

    item = Item.objects.filter(sku=item_sku).first()
    parent_item = Item.objects.filter(sku=parent_sku).first()

    if request.method == 'DELETE' and item:
        item.parent = None
        item.save()
        return JsonResponse({'res': 'delete'}, status=200)

    if item and parent_item:
        item.parent = parent_item
        item.save()
        return JsonResponse({'res': 'ok'})
    return JsonResponse({'res': 'کد نامعتبر'}, status=400)


def sale_user_report(request):
    from .models import Quotation
    wf_states = ['پیش فاکتور اولیه', 'استعلام قیمت', 'تایید پیش فاکتور', 'تایید مشتری', 'تایید کارشناس', 'مرحله نهایی']
    from_date = request.GET.get('from_time')
    to_date = request.GET.get('to_time')
    sale_user_report_call = Quotation.sale_user_report(request.user, wf_states, from_date, to_date)
    res = render_to_string('micmod-base/quotation/partial/sale_user_report.html',
                           context={'sale_user_report_call': sale_user_report_call, 'wf_states': wf_states,
                                    'from_date': from_date, 'to_date': to_date})
    return JsonResponse({'res': res}, safe=False)

  
def inquiry_not_started(request):
    trade_user = request.user
    inquiry = QuotationItem.inquiry_not_started(trade_user)
    res = {'my_inquiry_not_started': inquiry[0],
           'inquiry_not_started_count': inquiry[1],
           'item_in_china': inquiry[2],
           'new_inquiry': inquiry[3]
           }

    return JsonResponse(res)


from django.db import transaction


def duplicate_quotation(request, quotation_id):
    with transaction.atomic():
        # Get the original quotation
        quotation = Quotation.objects.get(pk=quotation_id)

        wf_initial = {
            'wf_access': True,
            'from_user': None,
            'to_user': request.user,
            'state': 'پیش فاکتور اولیه',
            'state_index': 0,
            'belong_to_group': 'sales_user',
            'action': 'create',
            'deadline': None,
            'flow_config': Base.get_flow_config(settings.BASE_DIR/'_keenthemes/view_config.json', 'QuotationsView'),
            'create': True
        }
        wfform = WorkFlowModelForm(data=request.POST, initial=wf_initial, content_type_model=Quotation,
                                   current_user=request.user)
        if wfform.is_valid():
            quotation.pk = None
            quotation.guid = uuid.uuid4()
            quotation.sepidar_number = None
            quotation.sepidar_quotation_id = None
            quotation.cancel = False

            wf_obj = wfform.save()
            wf_obj.from_user = request.user
            wf_obj.to_user = request.user

            wf_obj.content_type = ContentType.objects.filter(app_label=quotation._meta.app_label,
                                                             model=quotation._meta.model_name).first()
            wf_obj.wf_status = 5  # first draft
            wf_obj.extra_data.request = request
            wf_obj.current_state_name = 'پیش فاکتور اولیه'
            wf_obj.save()

            # Duplicate the quotation
            quotation.last_work_flow = wf_obj

            quotation.extra_data.request = request
            quotation.save()
            wf_obj.object_id = quotation.pk
            wf_obj.save()

            # Duplicate each related QuotationItem
            quotation_items = QuotationItem.objects.filter(quotation=quotation_id)
            for item in quotation_items:
                # goods_price_market, goods_market_date, goods_avg_price, goods_min_price, goods_max_price, goods_avg_count,
                # goods_code_alt, goods_name_alt, goods_last_sale, goods_last_price, goods_total_sales, goods_q_last_sale,
                # goods_q_last_price, goods_q_total_sales, , , , ,
                # quotation_id, is_deleted, , itemid, , ,
                # , description, , , , ,
                # , , , , , ,
                # , , , , , , ,
                # , price_target, goods_code_fk_id, final_price_sh, discount_per_item, , 
                item.need_foreign_price_inquiry = False
                item.need_local_price_inquiry = False
                item.foreign_price_inquiry_done = False
                item.local_price_inquiry_done = False
                item.assigned_trade_user = None
                item.assigned_trade_user2 = None
                item.assigned_trade_user_date = None
                item.assigned_trade_user_date2 = None
                item.task_start = False
                item.task_start2 = False
                item.task_start_date = None
                item.task_start_date2 = None
                item.item_editor_user = None
                item.old_goods_code = None
                item.old_goods_name = None
                item.delay_reason = None
                item.delay_time = None
                item.has_delay = False
                item.selected_price_code_id = None
                item.creator_user = None
                item.editor_user = None
                item.bazar_price_code = None
                item.trade_price_code = None
                item.lead_time = None
                item.item_in_china = False
                item.is_over = False
                #item.price_method = 'last_sale'
                #item.final_price = None

                item.pk = None  # Create a new record
                item.quotation = quotation  # Assign the new quotation
                item.extra_data.request = request
                item.save()

        return quotation


class QuotationsSalesHistoryList(LoginRequiredMixin,View):
    def get(self, request):
        q = self.request.GET.get('q')
        greeting = {}
        greeting['heading'] = _("quotation")
        greeting['pageview'] = _("micmod_base")
        greeting['time_form'] = TimeForm()
        # greeting['quotations'] = quotations_record
        # greeting['quotations'] = quotations_record_lst
        return render(request,'micmod-base/quotation/sales_history_list_datatable.html',greeting)


class QuotationSalesHistoryDatatable(AjaxDatatableView):
    model = QuotationItem
    title = 'sales history'
    initial_order = [["pk", "desc"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'quotation__pk', 'visible': True, 'title': _('شماره پیش‌فاکتور'), 'className': 'py-1 border currency-search', 'searchable': True,
         'orderable': True, 'lookup_field': '__icontains'},
        {'name': 'pk', 'visible': True, 'title': _('شماره سند'), 'className': 'py-1 border currency-search'},
        {'name': 'id', 'visible': False, },
        {'name': 'created_date', 'visible': True, 'orderable': True, 'searchable': False},
        {'name': 'quotation', 'visible': True, 'title': _('عنوان مشتری'), 'className': 'py-1 border', 'orderable': False, 'lookup_field': '__customer_party_id__title__icontains'},
        {'name': 'quotation__customer_party_id', 'visible': True, 'title': _('کد مشتری'), 'className': 'py-1 border', 'orderable': False, 'lookup_field': '__pk__icontains'},
        {'name': 'creator_user', 'visible': True, 'title': 'کارشناس', 'orderable': True, 'lookup_field': '__profile__first_name__icontains'},
        {'name': 'goods_code_fk', 'visible': True, 'title': 'کد کالا', 'orderable': True, 'lookup_field': '__sku__icontains'},
        {'name': 'goods_code_fk__part_number', 'visible': True, 'title': 'کالا', 'orderable': True, 'lookup_field': '__icontains'},
        {'name': 'goods_code_fk__purchase_group', 'visible': True, 'title': _('گروه خرید'), 'orderable': True, 'searchable': True, 'lookup_field': '__title__icontains'},
        {'name': 'goods_code_fk__sale_group', 'visible': True, 'title': _('گروه فروش'), 'orderable': True, 'searchable': True, 'lookup_field': '__title__icontains'},
        {'name': 'quotation__sale_type', 'title': 'نوع فروش', 'visible': True, 'orderable': True, 'lookup_field': '__title__icontains'},
        {'name': 'quantity', 'visible': True, 'orderable': True, 'searchable': True},
        {'name': 'fee', 'title': 'فی', 'visible': True, 'orderable': False, 'searchable': False, },
        {'name': 'quotation__currency_ref', 'title': 'ارز', 'visible': True, 'orderable': True, 'searchable': True, 'lookup_field': '__title__icontains'},
    ]

    def get_initial_queryset(self, request=None):
        q = request.POST.get('q')
        # if q == 'portal':
        #     qs = self.model.objects.all()
        # elif q == 'sepidar':
        #
        #     ...
        qs = self.model.objects.all()
        return qs

    # @timer
    def customize_row(self, row, obj):

        row['quotation__pk'] = obj.quotation.pk if obj.quotation else ''
        row['goods_code_fk'] = obj.goods_code_fk.sku if obj.goods_code_fk else ''
        row['goods_code_fk__part_number'] = obj.goods_code_fk.part_number if obj.goods_code_fk else ''
        row['quotation'] = obj.quotation.customer_party_id.title if obj.quotation.customer_party_id else ''
        row['quotation__customer_party_id'] = obj.quotation.customer_party_id.pk if obj.quotation.customer_party_id else ''
        row['goods_code_fk__purchase_group'] = obj.goods_code_fk.purchase_group.title if obj.goods_code_fk.purchase_group else ''
        row['goods_code_fk__sale_group'] = obj.goods_code_fk.sale_group.title if obj.goods_code_fk.sale_group else ''
        row['quotation__sale_type'] = obj.quotation.sale_type.title if obj.goods_code_fk else ''
        row['quotation__currency_ref'] = obj.quotation.currency_ref.title if obj.quotation else ''
        row['fee'] = obj.fee if obj else ''


def get_model_fields_config(request):
    if request.method == "POST":
        data = json.loads(request.body)
        app_label = data.get('app_label')
        model_name = data.get('model_name')
        filter_str = data.get('filter_str')
        model_class = apps.get_model(app_label, model_name)

        config = model_class.get_model_config(app_label=app_label, model_name=model_name, filter_str=filter_str)
        return JsonResponse(config)
    return JsonResponse({'error': 'Only POST method is allowed'}, status=405)


def export_quotation_items_to_excel(request, quotation_id):
    q = Quotation.objects.filter(id=quotation_id).first()

    qis = q.quotation.all()

    if request.method == 'POST':
        body = json.loads(request.body)
        # body.get('selected_fields').append('lead_time')
        # body.get('selected_labels').append('زمان تامین')

        excel_buffer = export_to_excel(qis, body)

        response = HttpResponse(
            excel_buffer,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        filename = f'quotation_{quotation_id}.xlsx'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    return HttpResponseBadRequest('Only POST method allowed.')


# from custom_base_django.views import DynamicAPIView


# class ExportQuotation(DynamicAPIView):
#     def get(self, request, *args, **kwargs):
#         if self.errors:
#             return self.errors
#         if self.get_structure:
#             return self.get_serializer_structure()
#
#         # return self.serializer_class.get_json_response(view_obj=self, *args, **kwargs)
#         _data, _status = self.serializer_class.get_json_response(view_obj=self, *args, **kwargs)
#         return JsonResponse(_data, status=_status, safe=True)


def get_customer_accounting_info(request, *args, **kwargs):
    # return JsonResponse({'res': 'اطلاعات مالی یافت نشد'})
    party_id = request.GET.get('party_id')
    if party_id:
        customer = DimCustomer.get_customer(party_id)
        html = render_to_string('micmod-base/quotation/partial/customer_accounting_info_in_quotation.html', {"customer": customer[0]})
        return JsonResponse({'res': html})

    return JsonResponse({'res': 'اطلاعات مالی یافت نشد'})


class CustomerRequestView(LoginRequiredMixin, View):
    queryset = CustomerRequest.objects.all()
    template_name = 'micmod-base/customer_request/view.html'
    # form_struct = {
    #     'form': CustomerRequestForm,
    #     'childes': [
    #         {
    #             'form': CustomerRequestItemForm,
    #             'childes': [{}]
    #         },
    #     ]
    # }
    # flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json', 'QuotationItemsFormPendingView')

    def get(self, request, pk, *args, **kwargs):
        self.object = CustomerRequest.objects.filter(pk=pk).prefetch_related('items')
        customer_request_item = self.object.first().items.all()
        total_qty_dict = dict()
        for cri in customer_request_item:
            total_qty = QuotationItem.objects.filter(customer_request_item=cri).aggregate(total=Sum('quantity'))['total'] or 0
            total_qty_dict[cri.pk] = total_qty
        context = {'object': self.object, 'total_qty': total_qty_dict}

        return render(request, self.template_name, context)

    def post(self, request, pk, *args, **kwargs):
        from django.utils import timezone
        try:
            customer = request.POST.get("customer")
            customer_shop = request.POST.get("customer_shop")
            customer_request = get_object_or_404(CustomerRequest, pk=pk)
            selected_items = request.POST.getlist('selected_items')
            # customer_item_request = get_object_or_404(CustomerRequest, pk=self.object.pk)
            customer_instance = None
            if customer:
                customer_instance = Customer.objects.get(sepidar_party_id=customer)
            elif customer_shop:
                customer_instance = Customer.objects.get(shop_id=customer_shop)
            if not customer_instance.shop_id:
                customer_instance.shop_id = customer_request.customer_shop
                customer_instance.extra_data.request = self.request
                customer_instance.save()
            sale_type = SaleType.objects.get(id=2)

            quotation = Quotation.objects.create(
                creator_user=self.request.user,
                editor_user=self.request.user,
                customer_party_id=customer_instance,
                request_date=timezone.now(),
                expiration_date=timezone.now(),
                sale_type=sale_type,
                customer_request=customer_request,
                customer_code=customer_instance.sepidar_dl_code
            )

            flow_data = {
                "wf_status": 5,  # first draft
                "action": 'ایجاد خودکار',
                "flow_name": 'quotation',
                "state": const.WF__QUOTATION__FIRST_STATE,
                "wf_description": const.WF__QUOTATION__FIRST_WF_DESCRIPTION,
                "belong_to_group": 'sales_user',
                "object_id": quotation.pk,
                "content_type": ContentType.objects.get_for_model(quotation),
                "creator_user": self.request.user,
                "editor_user": self.request.user,
                "from_user": self.request.user,
                "to_user": self.request.user,
                # get_user_model().objects.filter(groups__name='order_admin').first(),
                "current_state_name": const.WF__ORDER__FIRST_CURRENT_STATE_NAME,
            }
            wf = WorkFlow.objects.create(**flow_data)
            quotation.last_work_flow = wf
            quotation.extra_data.request = self.request
            quotation.save()

            total_rows = int(request.POST.get("total_rows", 0))
            for index in range(total_rows):
                if str(index) not in selected_items:
                    continue
                goods_code = request.POST.get(f"id_item-{index}")
                goods_code_instance = Item.objects.get(id=goods_code)
                quantity = float(request.POST.get(f"id_quantity-{index}", 0))
                customer_request_item_id = request.POST.get(f"customer_request_item_id-{index}")
                customer_sku = request.POST.get(f"customer_sku-{index}")
                customer_part_number = request.POST.get(f"customer_part_number-{index}")
                customer_description = request.POST.get(f"customer_description-{index}")
                customer_request_item_instance = None
                if customer_request_item_id:
                    customer_request_item_instance = CustomerRequestItem.objects.get(pk=customer_request_item_id)
                if not goods_code and quantity:
                    break
                # if quantity >= customer_request_item_instance.quantity:
                #     customer_request_item_instance.is_over = True
                #     customer_request_item_instance.extra_data = self.request
                #     customer_request_item_instance.save()

                customer_request_item_instance.product_id = goods_code
                customer_request_item_instance.extra_data = self.request
                customer_request_item_instance.save()

                QuotationItem.objects.create(
                    creator_user=self.request.user,
                    editor_user=self.request.user,
                    quotation=quotation,
                    goods_code_fk=goods_code_instance,
                    goods_code=goods_code_instance,
                    quantity=float(quantity) if quantity else 0,
                    customer_request_item=customer_request_item_instance,
                    customer_goods_code=customer_sku,
                    customer_goods_name=customer_part_number,
                )




        except Exception as e:
            # messages.warning(request, f"ردیف {index + 1} ذخیره نشد: {e}")
            messages.error(request, f"خطا در ذخیره پیش‌فاکتور: {e}")
            return redirect(request.path)

        messages.success(request, "پیش‌فاکتور با موفقیت ساخته شد.")
        url = reverse("micmod_base:quotations.view", kwargs={"pk": quotation.pk})
        return redirect(url)



class CustomerRequestViewSet(viewsets.ModelViewSet):
    # permission_classes = [IsAuthenticated, HasShopPermission]
    # queryset = CustomerRequest.objects.all().order_by('-request_date')
    serializer_class = CustomerRequestSerializer
    
    def get_queryset(self):
        # qs = super().get_queryset()
        q = self.request.GET.get('q')
        if q:
            return qs.filter(pk=q)
        return CustomerRequest.objects.all().order_by('-request_date')

    @action(detail=False, methods=['get'], url_path='by-customer/(?P<customer_id>[^/.]+)')
    def list_by_customer(self, request, customer_id=None):
        queryset = self.get_queryset().filter(customer=customer_id)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def list(self, request, *args, **kwargs):
        return JsonResponse({'detail': 'url with "pk" required'})

class CustomerRequestQuotationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasShopPermission]
    queryset = Quotation.objects.all().order_by('-request_date')
    serializer_class = CustomerQuotationSerializer
    http_method_names = ['get']

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


class CustomerRequestList(LoginRequiredMixin,View):
    def get(self, request):
        q = self.request.GET.get('q')
        context = {}
        return render(request, 'micmod-base/customer_request/list_datatable.html', context)


class CustomerRequestDatatableView(AjaxDatatableView):
    model = CustomerRequest
    title = 'customer request'
    initial_order = [["pk", "desc"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'pk', 'visible': True, 'title': _('شماره درخواست'), 'className': 'py-1 border'},
        {'name': 'id', 'visible': False, 'title': 'شناسه'},
        {'name': 'request_date', 'visible': True, 'orderable': True, 'searchable': False},
        {'name': 'expire_date', 'visible': True, 'title': _('تاریخ انقضا'), 'className': 'py-1 border', 'orderable': False, 'lookup_field': '__customer_party_id__title__icontains'},
        {'name': 'customer_code', 'visible': True, 'title': _('کد مشتری'), 'className': 'py-1 border', 'orderable': False,
         'lookup_field': '__sepidar_dl_code__icontains'},
        {'name': 'customer_title', 'visible': True, 'title': _('عنوان مشتری'), 'className': 'py-1 border', 'orderable': False, 'lookup_field': '__icontains'},
        {'name': 'customer_shop', 'visible': True, 'title': _('مشتری فروشگاه'), 'className': 'py-1 border', 'orderable': False},
        {'name': 'customer_phone', 'visible': True, 'title': 'تلفن مشتری', 'orderable': True,},
        {'name': 'cart_id', 'visible': True, 'title': 'شناسه کارت', 'orderable': True},
        # {'name': 'request_extra_data', 'visible': True, 'title': 'کالا', 'orderable': True},
    ]

    def get_initial_queryset(self, request=None):
        q = request.POST.get('q')
        qs = self.model.objects.all()
        return qs

    def customize_row(self, row, obj):

        row['pk'] = '<a class="fw-bold" target="_blank" href="%s">%s</a>' % (reverse('micmod_base:customer_request.view', args=(obj.id,)), obj.pk)
        row['customer_title'] = obj.customer.title if obj.customer else ''
        row['customer_code'] = obj.customer.sepidar_dl_code if obj.customer else ''
        # row['customer_shop_title'] = obj.shop if obj.customer_shop else ''
        # row['pk'] = '<a class="fw-bold" target="_blank" href="%s">%s</a>' % (reverse('micmod_base:customer_request.view', args=(obj.id,)), obj.pk)
        # row['goods_code_fk'] = obj.goods_code_fk.sku if obj.goods_code_fk else ''
        # row['goods_code_fk__part_number'] = obj.goods_code_fk.part_number if obj.goods_code_fk else ''
        # row['quotation'] = obj.quotation.customer_party_id.title if obj.quotation.customer_party_id else ''
        # row['quotation__customer_party_id'] = obj.quotation.customer_party_id.pk if obj.quotation.customer_party_id else ''
        # row['goods_code_fk__purchase_group'] = obj.goods_code_fk.purchase_group.title if obj.goods_code_fk.purchase_group else ''
        # row['goods_code_fk__sale_group'] = obj.goods_code_fk.sale_group.title if obj.goods_code_fk.sale_group else ''
        # row['quotation__sale_type'] = obj.quotation.sale_type.title if obj.goods_code_fk else ''
        # row['quotation__currency_ref'] = obj.quotation.currency_ref.title if obj.quotation else ''
        # row['fee'] = obj.fee if obj else ''


class QuotationFromCustomerRequestView(View):
    template_name = 'micmod-base/customer_request/view.html'
    conflict_template_name = 'micmod-base/quotation/conflict_view.html'
    post_conflict_template_name = 'micmod-base/quotation/conflict_post_view.html'
    form_class = QuotationForm
    model = CustomerRequest
    wf_last_step_is_open = True
    has_flow = True
    form_struct = {
        'form': QuotationForm,
        'childes': [
            {
                'form': QuotationItemFormset,
                'childes': [{'form': InquiryResultForm}]
            },
        ]
    }
    flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json', 'QuotationsView')

    has_formset = True
    formset_form = QuotationItemForm2
    formset_model = QuotationItem
    formset_fk_field = 'quotation'
    related_name_fk = 'quotation'

    def get(self, request, pk, *args, **kwargs):
        context = dict()
        from workflow.forms import WorkFlowModelForm
        flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json', 'QuotationsView')
        context['flow_state_index'] = 0
        context['flow_state_list'] = flow_config.get('flow_state_list')
        context['flow_state_list'].append('مرحله نهایی')
        """if flow object don't exist select user from group (normally for create step)"""
        group = flow_config.get('flow_users_groups')[1]
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
            content_type_model=Quotation,
            initial={
                'wf_access': True,
                'from_user': None,
                'to_user': to_user,
                'state': 'پیش فاکتور اولیه',
                'state_index': 0,
                'belong_to_group': 'sales_user',
                'action': 'create',
                'deadline': None,
                'flow_config': flow_config,
                'create': True
            },
            current_user=request.user,
        )

        cr = get_object_or_404(CustomerRequest, pk=pk)
        Q_fields = [
            "title", "code", "currency_ref", "status", "request_date", "expiration_date", "customer_code",
            "customer_party_id", "customer_grade", "delivery_time", "payment_method", "market_grade",
            "description", "id", 'sepidar_number', 'self_discount', 'addition', 'duty', 'tax',
            "is_official", "official_value", 'cancel', 'force_inquiry', 'sale_type', 'is_direct',
            'sales_admin_confirm', 'description_sales', 'customer_request'
        ]

        QI_fields = [
            'index', 'customer_goods_name', 'customer_goods_code', 'quantity', 'itemid', 'price_target',
            'delivery_time', 'goods_code', 'goods_code_alt', 'price_method', 'final_price',
            'goods_name', 'stock_amount', 'goods_avg_price', 'goods_price_sheet1', 'goods_price_sheet2',
            'goods_price_sheet3', 'discount_per_item',
            'goods_sheet_date', 'goods_market_date', 'goods_price_market', 'goods_avg_count',
            'goods_name_alt', 'goods_last_sale', 'goods_last_price', 'goods_total_sales',
            'stock_amount_res', 'goods_min_price', 'goods_max_price', 'trade_price_code', 'bazar_price_code',
            'goods_q_last_sale', 'goods_q_last_price', 'goods_q_total_sales', 'local_price_inquiry_done',
            'need_local_price_inquiry', 'foreign_price_inquiry_done', 'need_foreign_price_inquiry', 'description',
            'assigned_trade_user', 'lead_time', 'assigned_trade_user2', 'task_start', 'task_start2',
            'task_start_date', 'task_start_date2', 'has_delay', 'delay_reason', 'delay_time', 'item_in_china',
            'selected_price_code', 'price_json', 'sales_description', 'supply_status', 'customer_request_item',
            ]

        form = QuotationForm(data={ 'self_discount': 0})
        QuotationItemFormset = modelformset_factory(
            QuotationItem,
            extra=2,
            fields=qi_fields,
        )
        formset_initial = [
            {'goods_code': 1, 'quantity': 10},
            {'goods_code': 2, 'quantity': 20},
        ]
        formset = QuotationItemFormset(queryset=QuotationItem.objects.none(), initial=formset_initial, prefix='quotation')

        context['form'] = form
        context['formset'] = formset
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        pass


def item_order_quantity(request):
    goods_code = request.GET.get('sku')
    goods_code_fk = Item.objects.get(sepidar_id_0=goods_code)
    quantity = []
    free_quantity = []
    order_list = []

    for order in goods_code_fk.order_set.all():
        if order.is_wh is False and order.is_bazar is False:
            free_quantity.append(order.remaining_quantity)
            quantity.append(order.quantity)
            order_list.append(order.pk)

    total_qty = sum(quantity)
    total_free_qty = sum(free_quantity)
    context = {'quantity': quantity, 'free_qty': free_quantity, 'total_qty': total_qty, 'total_free_qty': total_free_qty, 'order': order_list}
    res = render_to_string('micmod-base/quotation/partial/item_order_quantity.html', context)
    return JsonResponse({'res': res}, safe=False)


class MicModDynamicView(DynamicViewRouter):
    valid_view = ('customer_item',)
    valid_for_get = ('customer_item',)

    def customer_item(self, request, *args, **kwargs):
        import requests
        customer = self.request.GET.get('customer', None)
        customer_goods_name = self.request.GET.get('customer_goods_name', None)
        quotation_id = self.request.GET.get('quotation_id', None)
        currency_ref_id = self.request.GET.get('currency_ref_id', None)
        payment_method = self.request.GET.get('payment_method', None)
        market_grade = self.request.GET.get('market_grade', None)
        customer_grade = self.request.GET.get('customer_grade', None)
        price_setting = self.request.GET.get('price_setting', None)
        quantity = int(self.request.GET.get('quantity', '1').replace(',', '') or 1)

        # quotation = Quotation.objects.filter(pk=quotation_id).first()
        if customer and customer_goods_name:
            qi = QuotationItem.objects.filter(quotation__customer_party_id=customer, customer_goods_name=customer_goods_name).order_by('-id').first()

            if qi:
                customer_goods_code = qi.customer_goods_code
                item = qi.goods_code_fk
                # party_id = customer.sepidar_party_id


                url = f"""inquiry/item_list/?q={item.sku}&party_id={customer}&id_currency_ref={currency_ref_id}&id_payment_method={payment_method}&id_market_grade={market_grade}&id_customer_grade={customer_grade}&price_setting{price_setting}=&quantity={quantity}&trade_price_code=&bazar_price_code="""
                res = requests.get(f'http://{self.request.get_host()}/{url}')
                if res.ok:
                    moq = item.batch_count
                    moq_box = item.count_in_box
                    moq_main_box = item.count_in_main_box
                    return JsonResponse({'customer_goods_code': customer_goods_code, 'sku': item.sku, 'moq': moq,
                                         'moq_box': moq_box, 'moq_main_box': moq_main_box, 'data': res.json()
                                         })

        return JsonResponse({'res': 'fail'})


# def get_quotation_sales_history(request):
#     qs = Quotation.objects.select_related(
#         'customer_party_id',
#         'customer_party_id__title',
#         'quotation__goods_code_fk__part_number',
#         'quotation__goods_code_fk__sepidar_id_0'
#         'quotation__goods_code_fk__purchase_group__title',
#         'created_date'
#     )
#
#     customer_goods_code = request.GET.get('customer_code')
#     goods_code = request.GET.get('item_code')
#     part_number = request.GET.get('part')
#     purchase_group = request.GET.get('g_p')
#     created_date = request.GET.get('created_date')


def get_quotation_sales_history(request):
    # qs = QuotationItem.objects.select_related(
    #     'quotation',
    #
    # )
    qs = QuotationItem.objects.select_related('goods_code_fk', 'quotation')

    body = json.loads(request.body.decode('utf-8'))
    customer_code = body.get('customer_code')
    item_code = body.get('item_code')
    part = body.get('part')
    start_date = body.get('start_date')
    end_date = body.get('end_date')

    if customer_code:
        qs = qs.filter(
            quotation__customer_party_id__icontains=customer_code
        )

    if item_code:
        qs = qs.filter(goods_code_fk__sku__icontains=item_code)

    if part:
        qs = qs.filter(goods_code_fk__part_number__icontains=part)

    if start_date and end_date:
        qs = qs.filter(
            quotation__created_date__range=[start_date, end_date]
        )

    qs = qs.order_by('-created_date')[:3000] if qs is not None else QuotationItem.objects.none()

    context = {}
    for obj in qs:
        context = {
            'doc_type': 'quotation',
            'number': obj.quotation.pk,
            'date': obj.quotation.created_date,
            'customer_title': obj.quotation.customer_party_id.title,
            'customer_code': obj.quotation.customer_party_id.sepidar_party_id,
            'sales_user_group': obj.quotation.customer_party_id.customer_group.title if obj.quotation.customer_party_id.customer_group else None,
            'item_code': obj.goods_code_fk.sku,
            'item_title': obj.goods_code_fk.part_number,
            'purchase_group': obj.goods_code_fk.purchase_group.title if obj.goods_code_fk.purchase_group else None,
            'sales_type': obj.quotation.sale_type.title if obj.quotation.sale_type else None,
            'quantity': float(obj.quantity),
            'fee': float(obj.fee),
            'currency': obj.quotation.sale_type.currency.title,
            'rate': '-',
        }


    return render(request, 'sepidar/sales_history_factor_quotation.html', context=context)


def quotation_item_approve_view(request, *args, **kwargs):
    if request.method == 'GET':
        return render(request, 'micmod-base/quotation/quotation_item_approve.html')

    if request.method == 'POST':
        try:
            quotation_item_id = json.loads(request.body).get('quotation_item_id')

            row = QuotationItem.objects.select_related("quotation").get(pk=quotation_item_id)
            row.is_approved = True
            row.extra_data.request = request
            row.save()

            quotation = row.quotation

            if not quotation.quotation.filter(is_approved=False).exists():
                quotation.sales_admin_confirm = True
                quotation.extra_data.request = request
                quotation.save(update_fields=["sales_admin_confirm"])

            return JsonResponse({"res": 'success'}, status=200)
        except Exception as e:
            return JsonResponse({'res': str(e)}, status=500)


class QuotationRowsGroupedByQuotationView(View, LoginRequiredMixin):
    """
    برای نمایش لیست ردیف‌های پیش فاکتور دسته‌بندی شده بر اساس پیش فاکتور
    """

    def get(self, request):
        page = request.GET.get('page', 1)
        per_page = min(int(request.GET.get('per_page', 100)), 100)

        quotations = Quotation.objects.filter(sales_admin_confirm=False, sepidar_number__isnull=False, pk__gt=1000, cancel=False, is_deleted=False) \
            .prefetch_related(
            Prefetch(
                'quotation',
                queryset=QuotationItem.objects
                    .select_related('goods_code_fk')
                    .only(
                    'id', 'quantity', 'final_price', 'quotation_id', 'is_approved',
                    'goods_code_fk__id', 'goods_code_fk__part_number', 'goods_code_fk__sku'
                )
                    .order_by('id')  # مرتب‌سازی ردیف‌ها
            )
        ).order_by('-pk').only('pk')

        paginator = Paginator(quotations, per_page)
        current_page = paginator.get_page(page)

        data = {}
        for quotation in current_page:
            # استفاده از list comprehension برای سرعت بیشتر
            items = [
                {
                    'id': item.pk,
                    'goods_code': item.goods_code_fk.part_number if item.goods_code_fk else '',
                    'sku': item.goods_code_fk.sku if item.goods_code_fk else '',
                    'quantity': item.quantity,
                    'final_price': str(item.final_price or '-'),
                    'total_price': str(item.quantity * item.final_price) if item.quantity and item.final_price else 0
                }
                for item in quotation.quotation.all() if not item.is_approved
            ]

            data[str(quotation.pk)] = {
                'customer': quotation.customer_party_id.title if quotation.customer_party_id else '-',
                'items': items,
            }

        response = {
            'success': True,
            'data': data,
            'pagination': {
                'current_page': current_page.number,
                'total_pages': paginator.num_pages,
                'total_quotations': paginator.count,
                'per_page': per_page,
                'has_next': current_page.has_next(),
                'has_previous': current_page.has_previous(),
            },
        }

        return JsonResponse(response, json_dumps_params={'ensure_ascii': False})

    def post(self, request):
        pass