from ajax_datatable import AjaxDatatableView
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse_lazy, reverse
from django.views import View

from core.views import BaseView, Base
from micmod_base.forms import TimeForm
from pcba.forms import ContractForm, CustomerItemReceiptForm, ProjectItemListForm
from pcba.models import Contract, CustomerItemReceipt, ProjectItemList
from tools.utils import show_error
from translator import get_text as _


# Create your views here.

class ContractsList(LoginRequiredMixin,View):
    def get(self, request):
        q = self.request.GET.get('q')
        greeting = {}
        greeting['heading'] = _("contract")
        greeting['pageview'] = _("pcba")
        return render(request, 'pcba/partial/list_datatable.html', greeting)


class ContractListDatatable(AjaxDatatableView):
    model = Contract
    title = 'contract_list'
    initial_order = [["pk", "desc"], ]
    length_menu = [[6, 10, 15, -1], [6, 10, 15, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'pk', 'visible': True, 'title': _('code'), 'className': 'py-1 border currency-search'},
        {'name': 'id', 'visible': False, },
        {'name': 'contract_title', 'visible': True, 'title': _('title'), 'className': 'py-1 border', 'lookup_field': '__icontains', 'searchable': True},
        {'name': 'goods_code_fk', 'visible': True, 'title': _('goods_code'), 'className': 'py-1 border', 'orderable': False, 'lookup_field': '__sku__icontains'},
        {'name': 'project_name_en', 'visible': True, 'orderable': True,},
        {'name': 'customer_party_id', 'visible': True, 'title': _('customer'), 'className': 'py-1 border', 'orderable': False, 'lookup_field': '__title__icontains'},
        {'name': 'customer_sheet_count', 'visible': True, 'orderable': True,},
        {'name': 'customer_board_count', 'visible': True, 'orderable': True},
        {'name': 'customer_total_board_count', 'visible': True, 'orderable': True,},
        {'name': 'first_setup_time', 'visible': True, 'orderable': True,},
        # {'name': 'quotation_state', 'visible': True, 'orderable': False, 'searchable': False},
        {'name': 'second_setup_time', 'visible': True, 'orderable': True,},
        {'name': 'pad_count', 'visible': True, 'orderable': True},
        {'name': 'ic_pad_count', 'visible': True, 'orderable': True},
        {'name': 'first_setup_cost', 'visible': True},
        {'name': 'second_setup_cost', 'visible': True}
    ]

    def customize_row(self, row, obj):
        row['customer_party_id'] = '<a class="fw-bold" href="%s" target="_blank">%s</a>' % (
            reverse('pcba:contracts.view', args=(obj.id,)),
            obj.customer_party_id.title if obj.customer_party_id else '-'
        )
        row['project_name_en'] = '<a class="fw-bold" href="%s" target="_blank">%s</a>' % (
            reverse('pcba:contracts.view', args=(obj.id,)),
            obj.project_name_en if obj.project_name_en else '-'
        )
        row['goods_code_fk'] = '<a class="fw-bold" href="%s" target="_blank">%s</a>' % (
            reverse('pcba:contracts.view', args=(obj.id,)),
            obj.goods_code_fk.sku if obj.goods_code_fk else '-'
        )


class ContractView(LoginRequiredMixin, BaseView):
    template_name = 'pcba/view.html'
    form_class = ContractForm
    model = Contract
    wf_last_step_is_open = True
    # has_flow = True
    form_struct = {
        'form': ContractForm,
        'childes': [
            {'form': '',
                'childes': [{}]
             },
        ]
    }

    def get_success_url(self):
        return reverse_lazy('pcba:contracts.view', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        res = super().form_valid(form)
        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # context['form_s'] = ProjectItemListFormset(instance=self.object)
        context['app_name'] = self.request.resolver_match.app_name
        return context


class CustomerItemReceiptView(LoginRequiredMixin, BaseView):
    template_name = 'pcba/customer_item_receipt.html'
    ajax_template_name = 'pcba/partial/customer_item_receipt_ajax.html'
    form_class = CustomerItemReceiptForm
    model = CustomerItemReceipt
    wf_last_step_is_open = True
    # has_flow = True
    form_struct = {
        'form': CustomerItemReceiptForm,
        'childes': [
            {},
        ]
    }

    def get_success_url(self):
        return reverse_lazy('pcba:customer.item.receipt.view', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        res = super().form_valid(form)
        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        pk = self.request.GET.get('pk', None)
        if pk:
            contract = Contract.objects.filter(pk=pk).first()
            context['form'] = CustomerItemReceiptForm(initial={'contract': contract or self.object.contract, }, instance=self.object)
        return context

    def get(self, request, *args, **kwargs):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            html = render_to_string(self.ajax_template_name, self.get_context_data(), self.request)
            return JsonResponse({'res': html})
        return super().get(request, *args, **kwargs)


class CustomerItemReceiptList(LoginRequiredMixin,View):
    def get(self, request):
        q = self.request.GET.get('q')
        greeting = {}
        greeting['heading'] = _("customer_item_receipt")
        greeting['pageview'] = _("pcba")
        return render(request, 'pcba/partial/customer_list_datatable.html', greeting)


class CustomerItemReceiptListDatatable(AjaxDatatableView):
    model = CustomerItemReceipt
    title = 'customer_item_receipt_list'
    initial_order = [["pk", "desc"], ]
    length_menu = [[6, 10, 15, -1], [6, 10, 15, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'pk', 'visible': True, 'title': _('code'), 'className': 'py-1 border currency-search'},
        {'name': 'id', 'visible': False, },
        {'name': 'contract', 'visible': True, 'title': _('contract'), 'className': 'py-1 border', 'lookup_field': '__contract_title__icontains', 'searchable': False},
        {'name': 'contract__customer_party_id', 'visible': True, 'title': _('customer'), 'className': 'py-1 border', 'lookup_field': '__title__icontains', 'searchable': False},
        {'name': 'receipt_date', 'visible': True, 'title': _('receipt_date'), 'className': 'py-1 border', 'orderable': False, },
        {'name': 'status', 'visible': True, 'orderable': True, 'searchable': True},
        {'name': 'total_board_receipt_count', 'visible': True, 'orderable': False, },
        {'name': 'parent', 'visible': True, 'orderable': True, 'title': _('self'), 'className': 'py-1 border', 'lookup_field': '__id__icontains', 'searchable': False},
    ]

    def customize_row(self, row, obj):
        row['pk'] = '<a class="fw-bold" href="%s" target="_blank">%s</a>' % (
            reverse('pcba:customer.item.receipt.view', args=(obj.id,)),
            obj.pk if obj.pk else '-'
        )
        row['contract'] = '<a class="fw-bold" href="%s" target="_blank">%s</a>' % (
            reverse('pcba:customer.item.receipt.view', args=(obj.id,)),
            obj.contract.contract_title if obj.contract else '-'
        )
        row['contract__customer_party_id'] = f'<span>{obj.contract.customer_party_id.title if obj.contract else "-" }</span>'


class ProjectItemListView(LoginRequiredMixin, BaseView):
    template_name = 'pcba/project_item_list.html'
    ajax_template_name = 'pcba/partial/project_item_list_ajax.html'
    form_class = ProjectItemListForm
    model = ProjectItemList
    wf_last_step_is_open = True
    # has_flow = True
    form_struct = {
        'form': ProjectItemListForm,
        'childes': [
            {},
        ]
    }

    def get_success_url(self):
        return reverse_lazy('pcba:project.item.list', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        res = super().form_valid(form)
        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        pk = self.request.GET.get('pk', None)
        if pk:
            contract = Contract.objects.filter(pk=pk).first()
            goods_code_fk = contract.goods_code_fk
            context['form'] = ProjectItemListForm(initial={'contract': contract or self.object.contract, 'goods_code_fk': goods_code_fk or self.object.contract.goods_code_fk}, instance=self.object)
        return context

    def get(self, request, *args, **kwargs):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            html = render_to_string(self.ajax_template_name, self.get_context_data(), self.request)
            return JsonResponse({'res': html})
        return super().get(request, *args, **kwargs)


def get_contracts(request):
    q = request.GET.get('q', None)
    reps = [["ي", "ی"], ["ك", "ک"]]
    obj = {}
    count = 0
    if q:
        CIRs = Contract.objects.filter(pk=q)
        obj['items']=[]
        for cir in CIRs:
            item = {}
            item['id'] = cir.pk
            item['text'] = cir.contract_title
            obj['items'].append(item)
            count += 1
            # try:
            #     contract = Contract.objects.filter(pk=cir).first()
            # except Exception as e:
            #     show_error(e, __file__)

    obj['total_count'] = count
    return JsonResponse(obj,safe=False)


def get_parents(request):
    q = request.GET.get('q', None)
    reps = [["ي", "ی"], ["ك", "ک"]]
    obj = {}
    count = 0
    if q:
        CIRs = CustomerItemReceipt.objects.filter(pk=q)
        obj['items']=[]
        for cir in CIRs:
            item = {}
            item['id'] = cir.pk
            item['text'] = cir.contract.customer_party_id.title
            obj['items'].append(item)
            count += 1
            # try:
            #     customer_item_receipt = CustomerItemReceipt.objects.filter(pk=cir).first()
            # except Exception as e:
            #     show_error(e, __file__)

    obj['total_count'] = count
    return JsonResponse(obj,safe=False)
