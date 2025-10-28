import datetime

from django.db.models.signals import post_save, m2m_changed
from django.utils import timezone
from django.contrib import messages
from ajax_datatable import AjaxDatatableView
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.forms import inlineformset_factory
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.urls import reverse
from django.views import View
from jalali_date import datetime2jalali
from jalali_date.templatetags.jalali_tags import to_jalali
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from simple_history.models import HistoricalRecords

from core.exceptions import StockRefNotFoundError
from core.permissions import HasShopPermission
from extra_data.models import Item
from factor.cont import disable_all_signals
from factor.serializers import FactorSerializer
from micmod_base.serializers import CustomerRequestSerializer
from sepidar.api_call import SepidarApiCall
from sepidar.models import Dl
from translator import get_text as _

from core.views import BaseView, Base
from factor.forms import FactorModelForm, FactorItemFormset, FactorItemModelForm, DeliveryForm
from factor.models import Factor, FactorItem, Delivery
from micmod_base.models import Quotation, QuotationItem, CustomerRequest
from tools.utils import to_jalali_date, show_error, timer
import json


class FactorView(LoginRequiredMixin, BaseView):
    template_name = 'factor/factor.html'
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
            if res:
                self.object.sepidar_number = res.get('number')
                self.object.sepidar_id = res.get('invoiceid')
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
                return
            else:
                self.after_sepidar_error()
                messages.error(self.request, f'خطا در ارسال فاکتور به سپیدار')
                return
        except StockRefNotFoundError as e:
            self.after_sepidar_error()
            messages.error(self.request, f'{e}')
        except Exception as e:
            self.after_sepidar_error()
            messages.error(self.request, f'{e}')

    def get_success_url(self):
        return reverse_lazy('factor:factor.view', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        if self.object is None:
            pass
            # import_customers_from_sepidar(extra_data={"creator_user_id": 1, "editor_user_id": 1})

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

    # @staticmethod
    # def reconnect_history(model):
    #     from simple_history import register
    #     register(model)

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
        if 'back' in self.request.POST and not self.object.is_need_sales_admin_confirmation() and self.state_index == 2:
            # belong_to_group = self.flow_config.get('flow_users_groups')[self.state_index - 2]
            last_wf_belong_to_sales_user_if_change = self.object.workflows.filter(belong_to_group='sales_user', wf_status=4).order_by('id').last()
            last_wf_belong_to_sales_user = self.object.workflows.filter(belong_to_group='sales_user').order_by('id').first()
            wf_data = {
                'wf_status': 2,  # back
                'state': self.flow_config.get('flow_state_list')[self.state_index - 1],
                'wf_description': 'بدون نیاز به تایید مدیر فروش',
                'from_user': self.request.user,
                'to_user': last_wf_belong_to_sales_user_if_change.to_user if last_wf_belong_to_sales_user_if_change else last_wf_belong_to_sales_user.from_user,
                'current_state_name': self.flow_config.get('flow_state_list')[self.state_index - 2],
                'object_id': self.object.pk,
            }
            self.save_flow(self.request, **wf_data)
        if 'next' in self.request.POST and not self.object.is_need_sales_admin_confirmation() and self.state_index == 0:
            wf_data = {
                'state': self.flow_config.get('flow_state_list')[self.state_index + 1],
                'wf_description': 'بدون نیاز به تایید مدیر فروش',
                'from_user': self.request.user,
                'to_user': get_user_model().objects.filter(groups__name='wh_admin').first(),
                'current_state_name': self.flow_config.get('flow_state_list')[self.state_index + 2],
                'object_id': self.object.pk,
            }
            self.save_flow(self.request, **wf_data)
        if 'next' in self.request.POST and self.state_index == 4:
            self.send_factor_to_sepidar()

        # if self.object.final_check and not obj_before_save.final_check and 'next' not in self.request.POST:
        #     self.send_factor_to_sepidar()

        # self.reconnect_history(Factor)
        # self.reconnect_history(FactorItem)
        self.object.save()
        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.object:
            context['allow_next'] = False
        context['f_warning'] = []
        if not self.object:
            return context
        context['section_id'] = 'factor'
        context['is_need_sales_admin_confirmation'] = self.object.is_need_sales_admin_confirmation() and self.state_index < 2
        context['form'].enable = True if self.wf_access else False
        context['update'] = True if self.object else False
        context['obj'] = self.object
        context['quotation'] = self.object.q if self.object else None
        qis = self.object.q.quotation.all() if self.object else None
        FactorItemFormset.extra = context['quotation'].quotation.count() - self.object.factoritem_set.count() if self.object else 0
        context['form_s'] = FactorItemFormset(instance=self.object, form_kwargs={
                                                  "constraint": {
                                                      "wf_access": self.wf_access,
                                                      'form_state': self.state_index,
                                                      'request': self.request,
                                                      'form_constraint': self.flow_config.get("flow_form_constraint"),
                                                      'formset_constraint': self.flow_config.get('flow_formset_constraint')
                                                      }
                                              })

        exclude_qi = set()
        context['factoritem_qi_pair'] = []
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
        if self.object and self.state_index == 3 and (self.object.need_financial_approval and not self.object.accounting_confirm):
            context['f_warning'].append('نیاز به تایید مالی دارد.')
            context['allow_next'] = False

        if self.object:
            factoritems = (
                self.object.factoritem_set
                .select_related('supply_locations')
                .all()
            )

            if self.object and self.state_index >= 0 and not all(x.supply_locations.is_all_arrival for x in factoritems):
                context['allow_next'] = False
                context['f_warning'].append('سفارش در راه دارد')

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
        quotations = Quotation.objects.get_access_object(request.user, lst=False).filter(pk=q_int, sales_admin_confirm=True, **q_required).order_by('-id').distinct()
    else:
        quotations = Quotation.objects.get_access_object(request.user, lst=False).filter(q_filter, sales_admin_confirm=True, **q_required).order_by('-id').distinct()
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
    qis = QuotationItem.objects.filter(quotation_id=pk)
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
        else:
            self.cols.append({'name': 'q', 'visible': True, 'title': _('quotation'), 'lookup_field': '__pk__icontains', 'searchable': True, 'className': 'border'})
            self.cols.append({'name': 'q__payment_method', 'visible': True, 'title': _('روش پرداخت'), 'lookup_field': '__icontains', 'className': 'border'})
            self.cols.append({'name': 'sale_type', 'title': _('sale_type'), 'visible': True, 'searchable': False, 'orderable': True, 'lookup_field': '__title__icontains', 'className': 'border'},)
            self.cols.append({'name': 'self_discount', 'title': 'تخفیف', 'visible': True, 'orderable': True, 'searchable': True, 'className': 'border'},)
            self.cols.append({'name': 'delivery_time', 'visible': True, 'searchable': True, 'title': _('delivery_time'), 'orderable': True, 'lookup_field': '__icontains', 'className': 'border'},)
            self.cols.append({'name': 'is_official', 'title': _('is_official'), 'visible': True, 'searchable': True, 'orderable': True, 'className': 'border'},)
            self.cols.append({'name': 'official_value', 'title': _('official_value'), 'visible': True, 'orderable': True, 'searchable': True, 'className': 'border'},)

        return self.cols

    def get_initial_queryset(self, request=None):
        qs = self.model.get_qs(self.request, lst=False)
        return qs

    def customize_row(self, row, obj):
        row['q'] = '<a class="fw-bold" href="%s" target="_blank">%s</a>' % (
            reverse('micmod_base:quotations.view', args=(obj.q.id,)),
            obj.q.id if obj.q else '-'
        )
        row['id'] = '<a class="fw-bold" href="%s" target="_blank">%s</a>' % (
            reverse('factor:factor.view', args=(obj.id,)),
            obj.pk if obj.pk else '-'
        )
        row['q__customer_party_id'] = obj.q.customer_party_id.title if obj.q else ''
        row['q__last_work_flow'] = obj.q.last_work_flow.to_user.username if obj.q else ''
        row['q__payment_method'] = obj.q.payment_method if obj.q else ''
        row['wh_user'] = " ".join([x.username for x in obj.wh_user.all()])
        row['checker'] = " ".join([x.username for x in obj.checker.all()])

    def wh_column_defs(self, request):
        for col in [
            {'name': 'wh_user', 'visible': True, 'title': _('wh_user'), 'lookup_field': '__username__icontains',
             'searchable': True, 'className': 'border'},
            {'name': 'checker', 'visible': True, 'title': _('accounting_user'), 'lookup_field': '__username__icontains',
             'searchable': True, 'className': 'border'},
            {'name': 'q__last_work_flow', 'visible': True, 'title': _('کارشناس مربوطه'),
             'lookup_field': '__to_user__username__icontains', 'className': 'border'},
            {'name': 'last_work_flow', 'visible': True, 'searchable': True, 'title': "مرحله", 'orderable': True,
             'lookup_field': '__current_state_name__icontains', 'className': 'border'},
            {'name': 'sepidar_number', 'visible': True, 'orderable': True, 'className': 'border'},
            {'name': 'cancel', 'visible': True, 'orderable': True, 'searchable': True, 'className': 'border'},
            {'name': 'description', 'visible': True, 'orderable': True, 'searchable': True,
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
            {'name': 'q__last_work_flow', 'visible': True, 'title': _('کارشناس مربوطه'),
             'lookup_field': '__to_user__username__icontains', 'className': 'border'},
            {'name': 'last_work_flow', 'visible': True, 'searchable': True, 'title': "مرحله", 'orderable': True,
             'lookup_field': '__current_state_name__icontains', 'className': 'border'},
            {'name': 'sepidar_number', 'visible': True, 'orderable': True, 'className': 'border'},
            {'name': 'cancel', 'visible': True, 'orderable': True, 'searchable': True, 'className': 'border'},
            {'name': 'description', 'visible': True, 'orderable': True, 'searchable': True,
             'lookup_field': '__icontains', 'className': 'border'},
            {'name': 'q', 'visible': True, 'title': _('quotation'), 'lookup_field': '__pk__icontains',
             'searchable': True, 'className': 'border'},
            {'name': 'q__payment_method', 'visible': True, 'title': _('روش پرداخت'), 'lookup_field': '__icontains',
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
        ]:
            self.cols.append(col)
        return self.cols

    def base_cols(self):
        self.cols = [
            AjaxDatatableView.render_row_tools_column_def(),
            {'name': 'pk', 'visible': False, 'className': 'currency-search'},
            {'name': 'id', 'visible': True, 'orderable': True, 'title': _('code'), 'className': 'border'},
            {'name': 'q__customer_party_id', 'visible': True, 'title': _('customer'),
             'lookup_field': '__title__icontains', 'searchable': True, 'className': 'border'},
        ]
        return self.cols


def print_view(request,id=-1):

    template_name = 'factor/factor_print.html'

    formset = inlineformset_factory(Factor, FactorItem, form=FactorItemModelForm, extra=0, )
    greeting = {}
    greeting['alt_code_html'] = []
    greeting['heading'] = _("create")
    greeting['pageview'] = _("quotation")
    factor = Factor.objects.filter(id=id).first()
    greeting['form'] = FactorModelForm(instance=factor)
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
        factor = Factor.objects.prefetch_related('factoritem_set').get(pk=pk)
        factor_items = factor.factoritem_set.all()
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
