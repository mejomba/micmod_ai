from django.http import JsonResponse, Http404
from django.urls import reverse_lazy
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin

from changelog.models import ChangeLog
from core.views import BaseView
from .forms import ReceiptDetailCreateForm2, ReceiptCreateForm2
from .models import Receipt, ReceiptDetail


class ReceiptCreate(LoginRequiredMixin,
                    BaseView,
                    # FormFieldAccessMixin,
                    ):
    form_class = ReceiptCreateForm2
    # main_form = ReceiptCreateForm2
    model = Receipt
    # formset = inlineformset_factory(Receipt, ReceiptDetail, form=ReceiptDetailCreateForm2, extra=1, )
    formset_model = ReceiptDetail
    formset_form = ReceiptDetailCreateForm2
    template_name = 'inventory/receipt_update_or_create.html'
    formset_fk_field = 'receipt_id'
    related_name_fk = 'receiptdetail_set'
    success_url = '.'
    # has_flow = True
    # has_simple_flow = True
    wf_to_user_permission = 'inventory.change_receipt'
    # allow_perms = ['inventory.add_receipt', 'inventory.add_receiptdetail']
    # permission_strategy = 'and'
    create = True

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        """initial work flow form kwargs"""

        # """initial main form kwargs"""
        # fields, action = self.field_access_by_user_permission()
        # kwargs['initial'] = {'permission_access': {'fields': fields, 'action': action}}
        return kwargs

    # Todo fix with base
    def form_valid(self, form):
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        print('sub class context')
        # context['formset'] = self.formset
        return context


class ReceiptList(LoginRequiredMixin, ListView):
    model = Receipt
    template_name = 'inventory/receipt_list.html'
    context_object_name = 'items'


class ReceiptUpdate(LoginRequiredMixin,
                    BaseView,
                    # FormFieldAccessMixin
                    ):
    form_class = ReceiptCreateForm2
    # formset = inlineformset_factory(Receipt, ReceiptDetail, form=ReceiptDetailCreateForm2, extra=1,)
    has_formset = True
    model = Receipt
    formset_model = ReceiptDetail
    formset_form = ReceiptDetailCreateForm2
    template_name = 'inventory/receipt_update_or_create.html'
    success_url = reverse_lazy('inventory:receipt.list')
    context_object_name = 'item'
    related_name_fk = 'receiptdetail_set'
    formset_fk_field = "receipt_id"
    has_flow = True
    wf_to_user_permission = 'inventory.change_receipt'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        """initial work flow form kwargs"""

        """initial main form kwargs"""
        # fields, action = self.field_access_by_user_permission()
        # kwargs['initial'] = {'permission_access': {'fields': fields, 'action': action}}
        return kwargs

    def form_valid(self, form):
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.model.objects.filter(pk=self.kwargs.get('pk')).first()

        # context['workflow_form'] = self.workflow_form(to_user_permission='',
        #                                               content_type_model=self.model,
        #                                               )
        context['flow'] = self.get_flow(context[self.context_object_name])
        context['object_logs'] = ChangeLog.get_log(context[self.context_object_name])

        context['obj'] = obj
        context['receipt_details'] = ReceiptDetail.objects.filter(receipt_id=self.kwargs['pk'])
        context['formset'] = self.formset(instance=obj)

        related_obj = getattr(context[self.context_object_name], f'{self.related_name_fk}', None)
        context['detail_logs'] = []
        for item in related_obj.all():
            context['detail_logs'].append(ChangeLog.get_log(item))

        return context


#  =============== Receipt Detail ===============
class ReceiptDetailList(LoginRequiredMixin, ListView):
    model = ReceiptDetail
    template_name = 'inventory/receipt_detail_list.html'
    context_object_name = 'items'


def receipt_list_json(request):
    if request.method == 'GET':
        q = request.GET.get('q', None)
        obj = {}
        count = 0
        if q:
            items = Receipt.objects.filter(pack_number__icontains=q)
            obj['items'] = []
            for i in items:
                item = dict()
                item['id'] = i.id
                item['pack_number'] = i.pack_number
                item['register_date'] = i.register_date
                item['sepidar_code'] = i.sepidar_code
                item['description'] = i.description
                item['stock_id'] = i.stock_id
                obj['items'].append(item)
                count += 1
        obj['total_count'] = count
        return JsonResponse(obj)
    raise Http404
