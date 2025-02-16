import datetime
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

from translator import get_text as _

from core.views import BaseView, Base
from factor.forms import FactorModelForm, FactorItemFormset, FactorItemModelForm
from factor.models import Factor, FactorItem
from micmod_base.models import Quotation, QuotationItem
from tools.utils import to_jalali_date, show_error
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
    formset_form = FactorItemFormset
    formset_model = FactorItem
    formset_fk_field = 'factoritem_set'
    related_name_fk = 'factoritem_set'

    def get_success_url(self):
        return reverse_lazy('factor:factor.view', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        if self.object is None:
            pass
            # import_customers_from_sepidar(extra_data={"creator_user_id": 1, "editor_user_id": 1})
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        if self.object is None:
            pass
        res = super().form_valid(form)
        if self.is_need_sales_admin_confirmation() and 'next' in self.request.POST:
            wf_data = {
                'state': self.flow_config.get('flow_state_list')[self.state_index],
                'wf_description': 'بدون نیاز به تایید مدیر فروش',
                'from_user': self.request.user,
                'to_user': get_user_model().objects.filter(groups__name='accounting'),
                'current_state_name': self.flow_config.get('flow_state_list')[self.state_index + 1],
                'object_id': self.object.pk,
            }
            self.save_flow(self.request, **wf_data)
        return res

    def is_need_sales_admin_confirmation(self):
        x = not all([all((x.qi.final_price == x.price, x.qi.goods_code_fk == x.goods_code)) for x in
                self.object.factoritem_set.all()])
        return x

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.object:
            return context
        context['form'].enable = True if self.wf_access else False
        context['update'] = True if self.object else False
        context['obj'] = self.object
        context['quotation'] = self.object.q if self.object else None
        qis = self.object.q.quotation.all() if self.object else None
        FactorItemFormset.extra = context['quotation'].quotation.count() - self.object.factoritem_set.count() if self.object else 0
        context['form_s'] = FactorItemFormset(instance=self.object)

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
            self.object.created_date = datetime2jalali(self.object.created_date).strftime('%y/%m/%d-%H:%M')
            self.object.last_update_date = datetime2jalali(self.object.last_update_date).strftime('%y/%m/%d-%H:%M')
        context['data'] = self.object
        context['app_name'] = self.request.resolver_match.app_name
        context['submit_copy'] = True

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
    q_filter = Q(last_work_flow__current_state_name='مرحله نهایی') | Q(last_work_flow__current_state_name='تایید کارشناس')
    q_required = {'cancel': False, "is_deleted": False}
    for s in search_by:
        if s == 'search_customer':
            q_filter &= Q(customer_party_id__title__icontains=q_str)
        if s == 'search_id':
            q_filter &= Q(pk=q_int)
        if s == 'search_marketer':
            q_filter &= Q(last_work_flow__creator_user__username__icontains=q_str)
        if s == 'search_sepidar_id':
            q_filter &= Q(sepidar_number__icontains=q_int)
        if s == 'search_sku':
            q_filter &= Q(quotation__goods_code_fk__sku__iexact=q_str)
        if s == 'search_part_number':
            q_filter &= Q(quotation__goods_code_fk__part_number__icontains=q_str)
    if not search_by:
        q_filter = Q(last_work_flow__current_state_name='مرحله نهایی') | Q(last_work_flow__current_state_name='تایید کارشناس') & \
                   (Q(customer_party_id__title__icontains=q_str) | \
                   Q(customer_party_id__sepidar_dl_id__icontains=q_int) | \
                   Q(customer_code__icontains=q_str) | Q(sepidar_number__icontains=q_int) | \
                   Q(customer_party_id__sepidar_dl_code__icontains=q_int) | Q(customer_party_id__sepidar_party_id__icontains=int) | \
                   Q(pk=q_int) | Q(quotation__goods_code_fk__sku__icontains=q_str) | Q(last_work_flow__creator_user__username__icontains=q_str))
    quotations = Quotation.objects.get_access_object(request.user, lst=False).filter(q_filter, **q_required).order_by('-id').distinct()
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
        res['items'].append(item)
    else:
        res['total_count'] = total_count
    return JsonResponse(res)


def get_quotation_items_for_factor(request, pk, *args, **kwargs):
    from workflow.forms import WorkFlowModelForm
    flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json', 'Factor')
    quotation = Quotation.objects.filter(pk=pk).first()
    qis = QuotationItem.objects.filter(quotation_id=pk)
    form = FactorModelForm(instance=quotation)
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
        content_type_model=Factor,
        initial={
                    'wf_access': True,
                    'from_user': None,
                    'to_user': to_user, #self.get_flow_user(flow_user_groups[self.state_index + 1]), #request.user.__class__.objects.get(pk=59), #._meta.model.objects.get(pk=21),
                    'state': 'فاکتور اولیه',
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
    initial_order = [["pk", "desc"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'pk', 'visible': True, 'title': _('code'), 'className': 'currency-search'},
        {'name': 'id', 'visible': False, 'className': 'border'},
        {'name': 'q', 'visible': True, 'title': _('quotation'), 'lookup_field': '__pk__icontains', 'searchable': True, 'className': 'border'},
        {'name': 'q__customer_party_id', 'visible': True, 'title': _('customer'), 'lookup_field': '__title__icontains', 'searchable': True, 'className': 'border'},
        {'name': 'sale_type', 'title': _('sale_type'), 'visible': True, 'searchable': False, 'orderable': True, 'lookup_field': '__title__icontains', 'className': 'border'},
        {'name': 'delivery_time', 'visible': True, 'searchable': True ,'title': _('delivery_time'), 'orderable':True, 'lookup_field': '__icontains', 'className': 'border'},
        {'name': 'sepidar_number', 'visible': True, 'orderable': True, 'className': 'border'},
        {'name': 'self_discount', 'title': 'تخفیف', 'visible': True, 'orderable': True, 'searchable': True, 'className': 'border'},
        {'name': 'is_official', 'title': _('is_official'), 'visible': True, 'searchable': True, 'orderable': True, 'className': 'border'},
        {'name': 'official_value', 'title': _('official_value'), 'visible': True, 'orderable': True, 'searchable': True, 'className': 'border'},
        {'name': 'cancel', 'visible': True, 'orderable': True, 'searchable': True, 'className': 'border'},
        {'name': 'description', 'visible': True, 'orderable': True, 'searchable': True, 'lookup_field': '__icontains', 'className': 'border'},

    ]

    def customize_row(self, row, obj):
        row['q'] = '<a class="fw-bold" href="%s" target="_blank">%s</a>' % (
            reverse('micmod_base:quotations.view', args=(obj.q.id,)),
            obj.q.id if obj.q else '-'
        )
        row['pk'] = '<a class="fw-bold" href="%s" target="_blank">%s</a>' % (
            reverse('factor:factor.view', args=(obj.id,)),
            obj.pk if obj.pk else '-'
        )
        row['q__customer_party_id'] = obj.q.customer_party_id.title if obj.q else ''


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
