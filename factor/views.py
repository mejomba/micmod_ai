from itertools import islice

from ajax_datatable import AjaxDatatableView
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.urls import reverse
from django.views import View
from jalali_date import datetime2jalali
from translator import get_text as _

from comments.forms import CommentsForm
from core.views import BaseView, Base
from extra_data.models import Customer, CustomerPartNumber
from factor.forms import FactorModelForm, FactorItemFormset
from factor.models import Factor, FactorItem
from micmod_base.models import Quotation, QuotationItem
from tools.import_data import import_customers_from_sepidar
from tools.utils import to_jalali_date
import json


class FactorView(LoginRequiredMixin, BaseView):
    template_name = 'factor/factor.html'
    form_class = FactorModelForm
    model = Factor
    # wf_last_step_is_open = True
    # has_flow = True
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
        # if 'submit_duplicate' in self.request.POST:
        #     return self.duplicate(self.object, [], ['quotation'])
        """ run import customer from sepidar before object create"""
        if self.object is None:
            pass
            # import_customers_from_sepidar(extra_data={"creator_user_id": 1, "editor_user_id": 1})

        res = super().form_valid(form)

        customer_part_number_list = (CustomerPartNumber(item=fi.goods_code, customer=self.object.q.customer_party_id, part_number=fi.part_number_show) for fi in self.object.factoritem_set.all())
        while True:
            batch = list(islice(customer_part_number_list, 10))
            if not batch:
                break
            CustomerPartNumber.objects.bulk_create(batch, 10)
        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.object:
            return context
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
                        context['factoritem_qi_pair'].append((qi, factor_item_form, False))
                        break
                    else:
                        """(qi, factor item)"""
                        context['factoritem_qi_pair'].append((qi, factor_item_form, False))
                        break
        exclude_qi_qs = qis.filter(~Q(id__in=exclude_qi))
        empty_pair = [(x, context['form_s'][-1], True if idx == 0 else False) for idx, x in enumerate(exclude_qi_qs)]
        context['factoritem_qi_pair'].extend(empty_pair)
        if self.object:
            self.object.created_date = datetime2jalali(self.object.created_date).strftime('%y/%m/%d-%H:%M')
            self.object.last_update_date = datetime2jalali(self.object.last_update_date).strftime('%y/%m/%d-%H:%M')
        context['data'] = self.object
        context['app_name'] = self.request.resolver_match.app_name

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
    q_required = {}#{'cancel': False, "is_deleted": False, "last_work_flow__current_state_name": 'مرحله نهایی'}
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
            q_filter |= Q(quotation__goods_code_fk__sku__icontains=q_str)
        if s == 'search_part_number':
            q_filter |= Q(quotation__goods_code_fk__part_number__icontains=q_str)
    if not search_by:
        q_filter = Q(customer_party_id__title__icontains=q_str) | Q(customer_party_id__sepidar_dl_id__icontains=q_int) | \
                   Q(customer_code__icontains=q_str) | Q(sepidar_number__icontains=q_int) | \
                   Q(customer_party_id__sepidar_dl_code__icontains=q_int) | Q(customer_party_id__sepidar_party_id__icontains=int) | \
                   Q(pk=q_int) | Q(quotation__goods_code_fk__sku__icontains=q_str) | Q(last_work_flow__creator_user__username__icontains=q_str)
    quotations = Quotation.objects.filter(q_filter, **q_required).order_by('-id').distinct()
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
        item['last_work_flow_user'] = q.last_work_flow.creator_user.username if q.last_work_flow else '-'
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

    empty_pair = [(x, context['form_s'][-1], True if idx == 0 else False) for idx, x in enumerate(qis)]
    empty_pair.sort(key=lambda x: x[0].is_over)
    context['factoritem_qi_pair'] = empty_pair
    context['workflow_form'] = WorkFlowModelForm(
        content_type_model=Factor,
        initial={
                    'wf_access': True,
                    'from_user': None,
                    'to_user': request.user,
                    'state': None,
                    'state_index': 0,
                    'belong_to_group': 'sales_user',
                    'action': None,
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
        {'name': 'pk', 'visible': True, 'title': _('code'), 'className': 'py-1 border currency-search'},
        {'name': 'id', 'visible': False, },
        {'name': 'q', 'visible': True, 'title': _('quotation'), 'className': 'py-1 border', 'lookup_field': '__pk__icontains', 'searchable': True},
        {'name': 'sale_type', 'title': _('sale_type'), 'visible': True, 'searchable': False, 'className': 'py-1 border',
         'orderable': True, 'lookup_field': '__title__icontains'},
        {'name': 'delivery_time', 'visible': True, 'title': _('delivery_time'), 'className': 'py-1 border', 'orderable':True, 'lookup_field': '__icontains'},
        {'name': 'sepidar_number', 'visible': True, 'orderable': True},
        # {'name': 'workflows', 'title': 'متعلق به', 'visible': True, 'orderable': True, 'lookup_field': '__profile__first_name__icontains'},
        # {'name': 'factor_self', 'visible': True, 'orderable': True, 'searchable': False},
        {'name': 'self_discount', 'title': 'تخفیف', 'visible': True, 'orderable': True, 'searchable': False},
        {'name': 'is_official', 'title': _('is_official'), 'visible': True, 'searchable': False, 'orderable': True},
        {'name': 'official_value', 'title': _('official_value'), 'visible': True, 'orderable': True},
        {'name': 'cancel', 'visible': True, 'orderable': True, 'searchable': False},
        {'name': 'description', 'visible': True, 'orderable': False, 'searchable': True, 'lookup_field': '__icontains'},

    ]

    def customize_row(self, row, obj):
        row['q'] = '<a class="fw-bold" href="%s" target="_blank">%s</a>' % (
            reverse('micmod_base:quotations.view', args=(obj.id,)),
            obj.q.id if obj.q else '-'
        )
        row['pk'] = '<a class="fw-bold" href="%s" target="_blank">%s</a>' % (
            reverse('factor:factor.view', args=(obj.id,)),
            obj.pk if obj.pk else '-'
        )

