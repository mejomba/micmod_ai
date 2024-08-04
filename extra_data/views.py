import json
import uuid
from uuid import uuid4

from ajax_datatable import AjaxDatatableView
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.http import JsonResponse, Http404, HttpResponseRedirect
from django.shortcuts import render
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse_lazy, reverse
from django.views import generic, View

from micmod_base.forms import QuotationForm, QuotationItemFormset
from sepidar.models import APILogs, Device
from sepidar.scripts.sepidar_classes import Urls
from tools.import_data import set_items_sepidar_id_from_sepidar
from tools.utils import show_error
from .forms import ItemWeightForm, PurchaseGroupForm, HsForm, CustomerForm, CustomerDocumentsForm, \
    ChangeCustomerGroupForm, CustomerExpertForm, CustomerContractForm

from accounts.mixins import FormFieldAccessMixin
from changelog.models import ChangeLog
from core.views import BaseView, Base
from extra_data.models import Item, ItemWeight, PurchaseGroup, HS, Customer, CustomerDocuments, CustomerExpert, \
    CustomerContract
from inquiry.forms import SkuCreateForm, InquiryResultForm
from inventory.models import ReceiptDetail

from translator import get_text as _


class SkuCreateView(LoginRequiredMixin,
                    BaseView,
                    FormFieldAccessMixin,
                    ):
    """
    sku create view
    """
    has_flow = True
    # flow_config = {
    #     'flow_action': _('create'),
    #     'flow_state_list': ['تعریف اولیه', 'بررسی فنی'],
    #     'flow_users_groups': ['base_user', 'technical_admin'],
    #     'flow_deadline': [0, 2, 3],
    # }
    flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json', 'SkuCreateView')
    form_struct = {
        'form': SkuCreateForm,
        'childes': [
            {
                'form': '',
                'childes': [{}]
            },
        ]
    }
    allow_perms = ['extra_data.add_item']
    # form_class = SkuCreateForm
    model = Item
    template_name = 'extra_data/sku_create.html'
    success_url = reverse_lazy('extra_data:sku.list')
    success_message = '%(part_number)s create'

    def get(self, request, *args, **kwargs):
        return super().get(self, request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()

        """initial work flow form kwargs"""

        """initial main form kwargs"""
        # fields, action = self.field_access_by_user_permission()
        # kwargs['initial'] = {'permission_access': {'fields': fields, 'action': action}}
        return kwargs

    def form_valid(self, form):
        res = super().form_valid(form)
        if 'technical_admin' in self.request.user.groups.values_list('name', flat=True):
            url = reverse('extra_data:sku.update', kwargs={'pk': self.object.pk})
            return redirect(url)
        return res


class SkuListView(LoginRequiredMixin, generic.ListView):
    """
    sku list view
    """
    model = Item
    template_name = 'extra_data/sku_list.html'
    context_object_name = 'items'


class SkuUpdateView(LoginRequiredMixin,
                    # PermissionRequiredMixin,
                    BaseView,
                    FormFieldAccessMixin,
                    ):
    """
    sku update
    """
    has_flow = True
    # flow_config = {
    #     'flow_name': 'create sku',
    #     'flow_action': _('create'),
    #     'flow_state_list': ['تعریف اولیه', 'بررسی فنی'],
    #     'flow_users_groups': ['base_user', 'technical_admin'],
    #     'flow_deadline': [0, 2, 3],
    # }
    flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json', 'SkuUpdateView')
    form_struct = {
        'form': SkuCreateForm,
        'childes': [
            {
                'form': '',
                'childes': [{}]
            },
        ]
    }
    append_last_step = None
    # permission_required = 'extra_data.change_item'
    allow_perms = ['extra_data.add_item', 'extra_data.change_item']
    form_class = SkuCreateForm
    model = Item
    template_name = 'extra_data/sku_update.html'
    success_url = reverse_lazy('extra_data:sku.list')
    success_message = '%(sku)s update'
    wf_last_step_is_open = True

    # context_object_name = 'item'
    # wf_to_user_permission = 'extra_data.change_item'

    def __init__(self):
        super().__init__()
        print('sub class init')

    def get(self, request, *args, **kwargs):
        return super().get(self, request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        """initial work flow form kwargs"""
        """initial main form kwargs"""
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # context['related_price_inquiry_files'] = context['item'].sku_const.all()
        context['related_price_inquiry_files'] = context['item'].items.all()
        context['related_receipt_detail'] = ReceiptDetail.objects.filter(sku=self.kwargs['pk'])
        if flow := self.get_flow(context['item']):
            context['flow'] = flow.order_by('-id')
        # context['object_logs'] = ChangeLog.get_log(context['item'])
        context['app_name'] = self.request.resolver_match.app_name
        if 'wh_user' in self.request.user.groups.values_list('name', flat=True):
            for name, field in context['form'].fields.items():
                if name not in ['image_1', 'image_2', 'file_1', 'batch_type', 'batch_count']:
                    field.widget.attrs['readonly'] = 'readonly'
                if name in ['is_sea_default', 'active_main_item', 'technical_confirm']:
                    field.disabled = True
        return context

    def form_valid(self, form):
        if self.request.POST.get('draft') or self.request.POST.get('back') or 'change_user' in self.request.POST:
            x = super().form_valid(form)
            if 'technical_admin' in self.request.user.groups.values_list('name', flat=True):
                url = reverse('extra_data:sku.update', kwargs={'pk':self.object.pk})
                return redirect(url)
            else:
                return super(SuccessMessageMixin, self).form_valid(form)
        if self.state_index == 1 and not form.cleaned_data.get('technical_confirm'):
            self.success_message = 'امکان ارسال فرم به مرحله نهایی بدون تایید فنی وجود ندارد'
            return super(SuccessMessageMixin, self).form_valid(form)

        if 'technical_admin' in self.request.user.groups.values_list('name', flat=True):
            super().form_valid(form)
            url = reverse('extra_data:sku.update', kwargs={'pk':self.object.pk})
            return redirect(url)
        super().form_valid(form)
        return super(SuccessMessageMixin, self).form_valid(form)


# class ItemNotConfirmedListView(LoginRequiredMixin, generic.View):
#     model = Item
#     # template_name = 'extra_data/sku_not_confirmed.html'
#
#     def get(self, request, *args, **kwargs):
#         li = []
#         not_confirmed = Item.objects.filter(technical_confirm=False)
#         for item in not_confirmed:
#             form = SkuCreateForm(instance=item)
#             li.append(form)
#
#         context = {'not_confirmed': li}
#
#         return render(request, 'extra_data/sku_not_confirmed.html', context)
#

class SkuRelatedView(LoginRequiredMixin, generic.DetailView):
    """
    sku view-related
    """
    model = Item
    context_object_name = 'item'
    template_name = 'extra_data/sku_view_related.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['related_price_inquiry_files'] = context['item'].sku_const.all()
        context['related_receipt_detail'] = ReceiptDetail.objects.filter(sku=self.kwargs['pk'])
        context['app_name'] = self.request.resolver_match.app_name
        #  Todo 'check related_receipt_detail on production'
        try:
            context['related_receipt_detail'] = Item.objects.filter(sku=self.kwargs['pk']).first().sku_set.all()
        except Exception as e:
            print(e.__traceback__.tb_lineno, e)

        context['form'] = SkuCreateForm
        return context


def item_list_json(request):
    if request.method == 'GET':
        q = request.GET.get('q', None)
        obj = {}
        count = 0
        if q:
            items = Item.objects.filter(sku__icontains=q)
            obj['items'] = []
            for i in items:
                item = dict()
                item['id'] = i.id
                item['sku'] = i.sku
                item['part_number'] = i.part_number
                item['brand'] = i.brand
                item['quality'] = i.quality
                item['group_sell'] = i.group_sell
                item['group_buy'] = i.group_buy
                item['group_customs'] = i.group_customs
                item['package'] = i.package
                obj['items'].append(item)
                count += 1
        obj['total_count'] = count
        return JsonResponse(obj)
    raise Http404


class ItemWeightUpdateView(BaseView):
    model = ItemWeight
    form_class = ItemWeightForm
    template_name = 'extra_data/item_weight_list_or_create.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        return context

    def get_success_url(self):
        item = self.request.GET.get('sku')
        path = reverse('extra_data:item_weight.list')
        path += f"?sku={item if item else self.object.sku.pk}"
        return path


class ItemWeightDataTableView(AjaxDatatableView):
    model = ItemWeight
    title = 'item_weight'
    initial_order = [["created_date", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'sku', 'visible': True, 'title': _('sku'), 'className': 'py-1 border sku-search',
         'defaultContent': '<a href"#">test</a>', 'lookup_field': '__sku__iexact'},
        {'name': 'weight', 'visible': True, 'title': _('weight'), 'className': 'py-1 border', 'searchable': False},
        {'name': 'creator_user', 'visible': True, 'title': _('creator_user'), 'className': 'py-1 border', },
        {'name': 'created_date', 'orderable': True, 'visible': True, },
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
            qs = self.model.objects.filter(item=param)
        else:
            qs = self.model.objects.all()
        return qs.order_by('last_update_date')

    def customize_row(self, row, obj):
        row['sku'] = '<a class="fw-bold" href="%s">%s</a>' % (
                      reverse('extra_data:item_weight.update', args=(obj.id,)),
                      obj.sku if obj.sku else '_'
                    )


class PurchaseGroupView(BaseView):
    model = PurchaseGroup
    template_name = 'extra_data/purchase_group.html'
    success_url = reverse_lazy('extra_data:purchase_group.list')
    success_message = '%(title)s update'
    form_struct = {
        'form': PurchaseGroupForm,
        'childes': [
            {
                'form': '',
                'childes': [{}]
            },
        ]
    }


class PurchaseGroupListView(generic.ListView):
    """
    class PurchaseGroupListView list view
    """
    model = PurchaseGroup
    template_name = 'extra_data/purchase_group_list.html'
    context_object_name = 'items'


class PurchaseGroupDataTableView(AjaxDatatableView):
    model = PurchaseGroup
    title = 'purchase_group'
    initial_order = [["created_date", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        # {'name': 'sku', 'visible': True, 'title': _('sku'), 'className': 'py-1 border sku-search',
        #  'defaultContent': '<a href"#">test</a>', 'lookup_field': '__sku__iexact'},
        # {'name': 'weight', 'visible': True, 'title': _('weight'), 'className': 'py-1 border', 'searchable': False},
        {'name': 'title', 'orderable': True, 'visible': True, },
        {'name': 'price_settings', 'orderable': True, 'visible': True, 'searchable': False},
        {'name': 'hs', 'orderable': True, 'visible': True, 'lookup_field': '__title__icontains'},
        {'name': 'sea_transportation', 'orderable': True, 'visible': True, },
        {'name': 'air_transportation', 'orderable': True, 'visible': True, },
        {'name': 'express_transportation', 'orderable': True, 'visible': True, },
        {'name': 'sepidar_id', 'orderable': True, 'visible': True, },
        {'name': 'sepidar_code', 'orderable': True, 'visible': True, },
        {'name': 'creator_user', 'visible': True, 'title': _('creator_user'), 'className': 'py-1 border', 'lookup_field': '__username__icontains'},
        {'name': 'created_date', 'orderable': True, 'visible': True, 'searchable': False},
    ]

    # def get_initial_queryset(self, request=None):
    #     pass

    def customize_row(self, row, obj):
        row['title'] = '<a class="fw-bold" href="%s">%s</a>' % (
                      reverse('extra_data:purchase_group.update', args=(obj.id,)),
                      obj.title if obj.title else '_'
                    )


class HsView(LoginRequiredMixin, BaseView):
    model = HS
    template_name = 'extra_data/hs.html'
    success_url = reverse_lazy('extra_data:hs.list')
    success_message = '%(title)s update'
    form_struct = {
        'form': HsForm,
        'childes': [
            {
                'form': '',
                'childes': [{}]
            },
        ]
    }


class HsListView(LoginRequiredMixin, generic.ListView):
    model = Item
    template_name = 'extra_data/hs_list.html'
    context_object_name = 'items'


class HsDataTableView(AjaxDatatableView):
    model = HS
    title = 'hs'
    initial_order = [["created_date", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        # {'name': 'sku', 'visible': True, 'title': _('sku'), 'className': 'py-1 border sku-search',
        #  'defaultContent': '<a href"#">test</a>', 'lookup_field': '__sku__iexact'},
        # {'name': 'weight', 'visible': True, 'title': _('weight'), 'className': 'py-1 border', 'searchable': False},
        {'name': 'code', 'orderable': True, 'visible': True, },
        {'name': 'title', 'orderable': True, 'visible': True, 'searchable': False},
        {'name': 'title_en', 'orderable': True, 'visible': True},
        {'name': 'price_settings', 'orderable': True, 'visible': True, },
        {'name': 'customs_rate', 'orderable': True, 'visible': True, },
        {'name': 'creator_user', 'visible': True, 'title': _('creator_user'), 'className': 'py-1 border',
         'lookup_field': '__username__icontains'},
        {'name': 'created_date', 'orderable': True, 'visible': True, 'searchable': False},
    ]

    # def get_initial_queryset(self, request=None):
    #     pass

    def customize_row(self, row, obj):
        row['title'] = '<a class="fw-bold" target=_blank href="%s">%s</a>' % (
            reverse('extra_data:hs.update', args=(obj.id,)),
            obj.title if obj.title else '_'
        )


def ajax_update_from_sepidar(request):
    set_items_sepidar_id_from_sepidar()
    return JsonResponse({'res': 'ok'})


class CustomerView(LoginRequiredMixin, BaseView):
    model = Customer
    template_name = 'extra_data/customer.html'
    # success_url = reverse_lazy('extra_data:customer.update')
    form_struct = {
        'form': CustomerForm,
        'childes': [
            {
                'form': '',
                'childes': [{}]
            },
        ]
    }

    def get_success_message(self, cleaned_data):
        return f'{self.object.title} save'

    def get_success_url(self):
        return reverse_lazy('extra_data:customer.update', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        return context

    # def post(self, request, pk=-1):
    #     self.object = self.model.objects.get(pk=pk)
    #     form = self.form_struct.get('form')(self.request.POST, instance=self.object)
    #     if form.is_valid():
    #         self.object = form.save()
    #     return HttpResponseRedirect(self.get_success_url)
    # def form_valid(self, form):
    #     res = super().form_valid(form)
    #     return res
        # instance = form.save(commit=False)
        # instance.save()
        # form.save_m2m()
        # return HttpResponseRedirect(self.get_success_url())


class CustomerListView(LoginRequiredMixin, generic.ListView):
    model = Item
    template_name = 'extra_data/customer_list.html'
    context_object_name = 'items'


class CustomerDataTableView(AjaxDatatableView):
    model = Customer
    title = 'customer'
    initial_order = [["created_date", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'
    base_columns = dict()
    base_columns = {'name': 'title', 'orderable': True, 'visible': True, }
    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        base_columns,
        # {'name': 'title', 'orderable': True, 'visible': True, },
        {'name': 'name', 'orderable': True, 'visible': True, },
        {'name': 'last_name', 'orderable': True, 'visible': True, },
        {'name': 'email', 'orderable': True, 'visible': True, },
        {'name': 'website', 'orderable': True, 'visible': True, },
        {'name': 'phone', 'orderable': True, 'visible': True, },
        {'name': 'credit_with_doc', 'orderable': True, 'visible': True, },
        {'name': 'customer_group', 'orderable': True, 'visible': True, 'lookup_field': '__title__icontains'},
        {'name': 'province', 'orderable': True, 'visible': True, 'lookup_field': '__title__icontains'},
        {'name': 'location', 'orderable': True, 'visible': True, 'lookup_field': '__title__icontains'},
        {'name': 'address', 'orderable': True, 'visible': True, },
        {'name': 'senf', 'orderable': True, 'visible': True, 'lookup_field': '__title__icontains'},
        {'name': 'sub_senf', 'orderable': True, 'visible': True, 'lookup_field': '__title__icontains'},
        {'name': 'introduction_method', 'orderable': True, 'visible': True, 'lookup_field': '__title__icontains'},
        {'name': 'introducer', 'orderable': True, 'visible': True, 'lookup_field': '__title__icontains'},
        {'name': 'marketer', 'orderable': True, 'visible': True, 'lookup_field': '__title__icontains'},
        {'name': 'creator_user', 'visible': True, 'title': _('creator_user'), 'className': 'py-1 border',
         'lookup_field': '__username__icontains'},
        {'name': 'created_date', 'orderable': True, 'visible': True, 'searchable': False},
        {'name': 'z_no', 'orderable': True, 'visible': True, 'searchable': False},
        {'name': 'z_safte', 'orderable': True, 'visible': True, 'searchable': False},
        {'name': 'z_cheque_s', 'orderable': True, 'visible': True, 'searchable': False},
        {'name': 'z_cheque_ns', 'orderable': True, 'visible': True, 'searchable': False},
        {'name': 'z_max_credit_rafi', 'orderable': True, 'visible': True, 'searchable': False},
        {'name': 'extra_credit', 'orderable': True, 'visible': True, 'searchable': False},
        {'name': 'i_type1_target', 'orderable': True, 'visible': True, 'searchable': False},

        {'name': 'cheque_to_delivery', 'orderable': True, 'visible': True, 'searchable': False},
        # {'name': 'contract', 'orderable': True, 'visible': True, 'searchable': False, 'lookup_field': '__contract_type__icontains'},
        {'name': 'customer_sale_type', 'orderable': True, 'visible': True, 'searchable': False, 'lookup_field': '__title__icontains'},
        {'name': 'official_name', 'orderable': True, 'visible': True, 'searchable': False},
        {'name': 'customer_grade', 'orderable': True, 'visible': True, 'searchable': False},
        {'name': 'description', 'orderable': True, 'visible': True, 'searchable': False},
    ]

    # def get_initial_queryset(self, request=None):
    #     pass

    def customize_row(self, row, obj):
        row['title'] = '<a class="fw-bold" target=_blank href="%s">%s</a>' % (
            reverse('extra_data:customer.update', args=(obj.id,)),
            obj.title if obj.title else '_'
        )


        # row['address'] = f"""
        # <div id="" class="" data-bs-toggle="tooltip" data-bs-original-title="{obj.address}" data-bs-placement="top" data-kt-initialized="1">{obj.address}</div>
        # """ if obj.address else '-'


class CustomerDocumentView(LoginRequiredMixin, BaseView):
    model = CustomerDocuments
    template_name = 'extra_data/customer_document.html'
    # success_url = reverse_lazy('extra_data:customer.list')
    success_message = '%(customer)s update'
    form_struct = {
        'form': CustomerDocumentsForm,
        'childes': [
            {
                'form': '',
                'childes': [{}]
            },
        ]
    }

    def get_success_url(self):
        return reverse_lazy('extra_data:customer.update', kwargs={'pk': self.object.customer.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = Customer.objects.filter(pk=self.request.GET.get('pk')).first()
        context['form'] = CustomerDocumentsForm(initial={'customer': customer or self.object.customer}, instance=self.object)
        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        res = render_to_string(self.template_name, context=context, request=self.request)
        return JsonResponse({'res': res})


class CustomerChangeMarketerView(LoginRequiredMixin, BaseView):
    model = CustomerDocuments
    template_name = 'extra_data/customer_change_marketer.html'
    # success_url = reverse_lazy('extra_data:customer.list')
    success_message = '%(customer)s update'
    form_struct = {
        'form': ChangeCustomerGroupForm,
        'childes': [
            {
                'form': '',
                'childes': [{}]
            },
        ]
    }

    def get_success_url(self):
        return reverse_lazy('extra_data:customer.update', kwargs={'pk': self.object.customer.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = Customer.objects.filter(pk=self.request.GET.get('pk')).first()
        context['form'] = ChangeCustomerGroupForm(initial={'customer': customer or self.object.customer}, instance=self.object)
        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        res = render_to_string(self.template_name, context=context, request=self.request)
        from django.templatetags.static import static
        # jss = context['form'].media._js
        #
        # import requests
        # x = [requests.get('http://' + self.request.META.get('HTTP_HOST') + static(js)).text for js in jss]

        return JsonResponse({'res': res})

class CustomerExpertView(LoginRequiredMixin, BaseView):
    model = CustomerExpert
    template_name = 'extra_data/customer_expert.html'
    success_message = '%(customer)s update'
    form_struct = {
        'form': CustomerExpertForm,
        'childes': [
            {
                'form': '',
                'childes': [{}]
            },
        ]
    }

    def get_success_url(self):
        return reverse_lazy('extra_data:customer.update', kwargs={'pk': self.object.customer.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = Customer.objects.filter(pk=self.request.GET.get('pk')).first()
        context['form'] = CustomerExpertForm(initial={'customer': customer or self.object.customer}, instance=self.object)
        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        res = render_to_string(self.template_name, context=context, request=self.request)
        return JsonResponse({'res': res})

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

class CustomerContractView(LoginRequiredMixin, BaseView):
    model = CustomerContract
    template_name = 'extra_data/customer_contract.html'
    success_message = '%(customer)s update'
    form_struct = {
        'form': CustomerContractForm,
        'childes': [
            {
                'form': '',
                'childes': [{}]
            },
        ]
    }

    def get_success_message(self, cleaned_data):
        return f'قرارداد {self.object.customer.title} save'

    def get_success_url(self):
        return reverse_lazy('extra_data:customer_contract.update', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = Customer.objects.filter(pk=self.request.GET.get('pk')).first()
        context['form'] = CustomerContractForm(initial={'customer': customer or self.object.customer},
                                               instance=self.object)
        return context
    
    def post(self, request, *args, **kwargs):
        x = super().post(request,*args, **kwargs)
        return x

    def form_valid(self, form):
        x = super().form_valid(form)
        return JsonResponse({'res': True})

    def get(self, request, *args, **kwargs):
        # super().get(request, *args, **kwargs)
        context = self.get_context_data()
        res = render_to_string(self.template_name, context=context, request=self.request)
        return JsonResponse({'res': res, 'jss': '', 'csss': ''})


class CustomerSepidarInsertView(View):
    def post(self, request, *args, **kwargs):
        customer = Customer.objects.filter(pk=kwargs.get('pk')).first()
        if customer:
            '''send customer to sepidar'''
            device = Device.objects.all().first()
            address_data = [
                {
                    'GUID': str(uuid.uuid4()),
                    'Title': None,  # '',
                    'IsMain': True,
                    'CityRef': customer.province.pk,
                    'Address': customer.address,
                    'ZipCode': None,  # 'customer.zip_code',
                    'Latitude': None,  # customer.lat,
                    'Longitude': None  # customer.long
                },
            ]
            customer_data = {
                'GUID': str(customer.guid),
                'PhoneNumber': customer.phone,  # optional
                'CustomerType': customer.type,
                'Name': customer.name,
                'LastName': customer.last_name,  # blank for company,
                'BirthDate': 'customer.birth_date',  # optional
                'NationalId': 'customer.national_id',  # optional
                'EconomicCode': 'customer.economic_code',  # optional
                'Addresses': address_data  # optional
            }
            d = json.dumps(customer_data)
            api_res = APILogs.new_call(device=device, url=Urls.post_customers.url,
                                       method=Urls.post_customers.method, data=d, save=True)
            api_log_obj = api_res[2]
            api_log_obj.extra_data.request = self.request if api_log_obj else ''
            api_log_obj.save()
            return JsonResponse({'res': 'success'}, status=api_res[0])
        else:
            return JsonResponse({'res': 'error'}, status=404)
        pass