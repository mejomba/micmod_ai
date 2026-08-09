import json
import uuid
from uuid import uuid4

from OpenSSL.rand import status
from ajax_datatable import AjaxDatatableView
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db import IntegrityError
from django.http import JsonResponse, Http404, HttpResponseRedirect
from django.shortcuts import render
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse_lazy, reverse
from django.views import generic, View
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import HasShopPermission
from micmod_base.forms import QuotationForm, QuotationItemFormset
from sepidar.api_call import SepidarApiCall
from sepidar.models import APILogs, Device
from sepidar.scripts.sepidar_classes import Urls
from services.product.api_call import ProductApiCall
from tools.import_data import set_items_sepidar_id_from_sepidar
from tools.utils import show_error, set_secret_id, DaxCall
from .forms import ItemWeightForm, PurchaseGroupForm, HsForm, CustomerForm, CustomerDocumentsForm, \
    ChangeCustomerGroupForm, CustomerExpertForm, CustomerContractForm, ItemPackageForm, AccountingUserForm, \
    CustomerGroupUserForm, CustomerAddressForm

from accounts.mixins import FormFieldAccessMixin
from changelog.models import ChangeLog
from core.views import BaseView, Base
from extra_data.models import Item, ItemWeight, PurchaseGroup, HS, Customer, CustomerDocuments, CustomerExpert, \
    CustomerContract, ChangeCustomerGroup, ItemPackage, AccountingUser, CustomerGroup, CustomerAddress
from inquiry.forms import SkuCreateForm, InquiryResultForm
from inventory.models import ReceiptDetail

from translator import get_text as _
from .serializers import ItemSerializer
from .task import link_item_packages


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
    form_class = SkuCreateForm
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
        # if 'wh_user' in self.request.user.groups.values_list('name', flat=True):
        #     for name, field in context['form'].fields.items():
        #         if name not in ['image_1', 'image_2', 'file_1', 'batch_type', 'batch_count', 'count_in_box',
        #                         'count_in_main_box', 'location_in_wh']:
        #             field.widget.attrs['readonly'] = 'readonly'
        #         if name in ['is_sea_default', 'active_main_item', 'technical_confirm']:
        #             field.disabled = True
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
        {'name': 'jalali_last_update_date', 'orderable': True, 'visible': True, },
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
        {'name': 'trade_transportation_method_json', 'orderable': True, 'visible': True, },
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        return context


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
    set_items_sepidar_id_from_sepidar(request)
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
        context['customer_credit'] = self.object.get_sepidar_credit() if self.object else 'در دسترس نیست'
        return context

    # def form_valid(self, form):
    #     x = super().form_valid(form)
    #     if self.request.user.is_superuser:
    #         for idx, item in enumerate(self.model.objects.all()):
    #             for _ in range(5):
    #                 try:
    #                     item.secret_id = set_secret_id()
    #                     item.save()
    #                     print(idx)
    #                     break
    #                 except IntegrityError as e:
    #                     print(e)
    #                     continue
    #     return x


class CustomerListView(LoginRequiredMixin, generic.ListView):
    model = Item
    template_name = 'extra_data/customer_list.html'
    context_object_name = 'items'


class CustomerDataTableView(AjaxDatatableView):
    model = Customer
    title = 'customer_list'
    initial_order = [["created_date", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'
    base_columns = dict()
    show_column_filters = True
    # base_columns = {'name': 'title', 'orderable': True, 'visible': True, }
    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'id', 'orderable': True, 'visible': False, },
        {'name': 'sepidar_dl_code', 'orderable': True, 'visible': True, 'width': 600, },
        {'name': 'title', 'title': '<div class="px-15">عنوان</div>', 'orderable': True, 'visible': True, 'className': 'text-center'},
        {'name': 'name', 'orderable': True, 'title': '<div class="px-10">نام</div>', 'visible': True, 'className': 'text-center'},
        {'name': 'last_name', 'orderable': True, 'visible': True, 'className': 'text-center'},
        {'name': 'official_name', 'orderable': True, 'title': '<div class="px-6">نام رسمی</div>', 'visible': True, 'className': 'text-center'},
        {'name': 'phone', 'orderable': True, 'visible': True, 'className': 'text-center'},
        {'name': 'customer_group', 'orderable': True, 'visible': True, 'lookup_field': '__title__icontains', 'className': 'text-center'},
        {'name': 'accounting_user', 'orderable': True, 'visible': True, 'lookup_field': '__title__icontains', 'className': 'text-center'},
        {'name': 'senf', 'orderable': True, 'visible': True, 'lookup_field': '__title__icontains', 'className': 'text-center'},
        {'name': 'cheque_to_delivery', 'title': '<div class="px-0">بدون قرارداد<br>چک هنگام تحویل</div>', 'orderable': True, 'visible': True, 'searchable': False, 'className': 'text-center'},
        {'name': 'z_no', 'orderable': True, 'visible': True, 'searchable': False, 'className': 'text-center'},
        {'name': 'z_safte', 'orderable': True, 'title': '<div class="px-10">سفته</div>', 'visible': True, 'searchable': True, 'className': 'text-center'},
        {'name': 'z_cheque_s', 'orderable': True, 'title': '<div class="px-5">چک صیادی</div>', 'visible': True, 'searchable': True, 'className': 'text-center'},
        {'name': 'z_cheque_ns', 'orderable': True, 'title': '<div class="px-5">چک غیر صیادی</div>', 'visible': True, 'searchable': True, 'className': 'text-center'},
        {'name': 'z_max_credit_rafi', 'title': '<div class="text-center">حد اعتباری <br> (صلاحدید آقای رفیع)</div>', 'orderable': True, 'visible': True, 'searchable': True, 'className': 'text-center'},
        {'name': 'extra_credit', 'orderable':  True, 'title': '<div class="px-5">extra_credit</div>', 'visible': True, 'searchable': True, 'className': 'text-center'},
        {'name': 'i_type1_target', 'orderable': True, 'visible': True, 'searchable': True, 'className': 'text-center'},
        {'name': 'customer_sale_type', 'orderable': True, 'visible': True, 'searchable': True,
         'lookup_field': '__title__icontains', 'className': 'text-center'},
        {'name': 'customer_grade', 'orderable': True, 'visible': True, 'searchable': True, 'className': 'text-center'},
        {'name': 'sub_senf', 'orderable': True, 'title': '<div class="px-5">sub senf</div>','visible': True, 'lookup_field': '__title__icontains', 'className': 'text-center'},
        {'name': 'introduction_method', 'orderable': True, 'title': '<div class="px-2">روش آشنایی</div>', 'visible': True, 'lookup_field': '__title__icontains', 'className': 'text-center'},
        {'name': 'province', 'orderable': True, 'visible': True, 'lookup_field': '__title__icontains', 'className': 'text-center'},
        {'name': 'location', 'orderable': True, 'visible': True, 'lookup_field': '__title__icontains', 'className': 'text-center'},
        {'name': 'address', 'title': '<span class="px-20">آدرس</span>',  'orderable': True, 'visible': True, },
        {'name': 'introducer', 'orderable': True, 'visible': True, 'lookup_field': '__title__icontains', 'className': 'text-center'},
        {'name': 'marketer', 'orderable': True, 'title': '<div class="px-3">بازاریاب</div>', 'visible': True, 'lookup_field': '__title__icontains', 'className': 'text-center'},
        {'name': 'credit_with_doc', 'orderable': True, 'visible': True, 'className': 'text-center'},
        {'name': 'email', 'orderable': True, 'title': '<div class="px-15">email</div>', 'visible': True, 'className': 'text-center'},
        {'name': 'website', 'orderable': True, 'title': '<div class="px-15">website</div>', 'visible': True, 'className': 'text-center'},
        {'name': 'description', 'orderable': False, 'visible': True, 'searchable': False, 'className': 'text-center'},
        {'name': 'creator_user', 'visible': True, 'title': _('creator_user'), 'className': 'py-1 border',
         'lookup_field': '__username__icontains'},
        {'name': 'created_date', 'orderable': True, 'visible': True, 'searchable': False, 'className': 'text-center'},
        {'name': 'pcb', 'orderable': True, 'visible': True, 'searchable': True, 'className': 'text-center'},
        {'name': 'assembly', 'orderable': True, 'visible': True, 'searchable': True, 'className': 'text-center'},
        {'name': 'item', 'orderable': True, 'visible': True, 'searchable': True, 'className': 'text-center'},

    ]

    # def get_initial_queryset(self, request=None):
    #     pass

    def customize_row(self, row, obj):
        row['customer_group'] = obj.change_marketer_rel.latest('created_date').to_marketer.title if obj.change_marketer_rel.all() and obj.change_marketer_rel.latest('created_date').to_marketer else ''
        row['title'] = '<a class="fw-bold" target=_blank href="%s">%s</a>' % (
            reverse('extra_data:customer.update', args=(obj.id,)),
            obj.title if obj.title else '_'
        )
        row['z_max_credit_rafi'] = f"""{obj.z_max_credit_rafi:,}""" if obj.z_max_credit_rafi else ''
        row['z_safte'] = f"""{obj.z_safte:,}""" if obj.z_safte else ''
        row['z_cheque_s'] = f"""{obj.z_cheque_s:,}""" if obj.z_cheque_s else ''
        row['z_cheque_ns'] = f"""{obj.z_cheque_ns:,}""" if obj.z_cheque_ns else ''
        row['extra_credit'] = f"""{obj.extra_credit:,}""" if obj.extra_credit else ''
        row['credit_with_doc'] = f"""{obj.credit_with_doc:,}""" if obj.credit_with_doc else ''


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
    model = ChangeCustomerGroup
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
        try:
            next_step_from_marketer = customer.change_marketer_rel.all().order_by('id').last().to_marketer if customer else None
        except Exception as e:
            next_step_from_marketer = None
        if next_step_from_marketer:
            context['form'] = ChangeCustomerGroupForm(initial={'customer': customer or self.object.customer, 'from_marketer': next_step_from_marketer}, instance=self.object)
        else:
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

    def form_valid(self, form):
        res = super().form_valid(form)
        return res

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
        SepidarApiCall.dl_to_sepidar(self.request, customer)
        return
        if customer:
            '''send customer to sepidar'''
            device = Device.objects.all().first()
            address_data = [
                {
                    # 'CustomerAddressID': 100000,
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
                'BirthDate': None,  # optional
                'NationalId': None,  # optional
                'EconomicCode': None,  # optional
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


class ItemListUpdate(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            extra_avg = data.get('kala')
            sea_avg = data.get('sea')
            air_avg = data.get('air')
            express_avg = data.get('express')
            pk_values = data.get('pk_values')
            items = Item.objects.filter(pk__in=pk_values)
            for item in items:
                if extra_avg:
                    item.extra_cost_percentage = extra_avg
                if express_avg:
                    item.express_extra_cost_percentage = express_avg
                if air_avg:
                    item.air_extra_cost_percentage=air_avg
                if sea_avg:
                    item.sea_extra_cost_percentage = sea_avg
                if extra_avg or express_avg or air_avg or sea_avg:
                    item.extra_data.request = request
                    item.save()
            # items.update(express_extra_cost_percentage=express_avg,
            #              air_extra_cost_percentage=air_avg,
            #              sea_extra_cost_percentage=sea_avg,
            #              editor_user=request.user)
            return JsonResponse({'res': 'success'})
        except Exception as e:
            return JsonResponse({'res': 'fail'}, status=500)


class ItemPackageView(LoginRequiredMixin, BaseView):
    model = ItemPackage
    template_name = 'extra_data/item_package_list_or_create.html'
    success_message = '%(package)s update'
    form_struct = {
        'form': ItemPackageForm,
        'childes': [
            {
                'form': '',
                'childes': [{}]
            },
        ]
    }
    def get(self, request, *args, **kwargs):
        # link_item_packages()
        return super().get(request, *args, **kwargs)

    def get_success_message(self, cleaned_data):
        return f'package {self.object.title} save'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        return context

    def get_success_url(self):
        return reverse_lazy('extra_data:item_package_list_or_create.view')


class ItemPackageDatatableView(AjaxDatatableView):
    model = ItemPackage
    title = 'item_package'
    initial_order = [["last_update_date", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'title', 'visible': True, 'title': _('title'), 'className': 'py-1 border'},
        {'name': 'weight', 'visible': True, 'title': _('weight'), 'className': 'py-1 border',},
        {'name': 'creator_user', 'visible': True, 'title': _('creator_user'), 'className': 'py-1 border', 'lookup_field': '__username__icontains' },
        {'name': 'created_date', 'orderable': True, 'visible': True, 'searchable': False},
        {'name': 'last_update_date', 'orderable': True, 'visible': True, 'searchable': False},
        {'name': 'jalali_last_update_date', 'orderable': True, 'visible': True, 'searchable': False},
    ]

    # def get_initial_queryset(self, request=None):
    #     param: str = self.request.POST.get('sku')
    #     try:
    #         if param and param.isdigit():
    #             param = int(param)
    #         else:
    #             param = ''
    #     except TypeError as e:
    #         show_error(e, __file__)
    #     if param:
    #         qs = self.model.objects.filter(item=param)
    #     else:
    #         qs = self.model.objects.all()
    #     return qs.order_by('last_update_date')

    def customize_row(self, row, obj):
        row['title'] = '<a class="fw-bold" href="%s">%s</a>' % (
            reverse('extra_data:item_package_list_or_create.update', args=(obj.id,)),
            obj.title if obj.title else '_'
        )


class ItemPackageWeightSearchView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        package = self.request.GET.get('package')
        package = ItemPackage.objects.filter(title__iexact=package).first()
        context = {'package': package}

        res = render_to_string('extra_data/partials/item_package_weight_result.html', context=context, request=self.request)
        return JsonResponse({'res': res})

#
# class ReadCustomerDebtsFromSheet(APIView):
#     def post(self, request, *args, **kwargs):
#         customer_id = -1
#         rows = request.data.get('rows', [])
#
#         for row in rows[1:]:
#             try:
#                 customer_id = row[0]
#                 debts = row[2]
#                 Customer.objects.filter(id=customer_id).update(debts=debts)
#
#             except Exception as e:
#                 print(f'{customer_id}--{e}')
#         return JsonResponse({'success': True}, status=status.HTTP_200_OK)
#


class AccountingUserView(LoginRequiredMixin, BaseView):
    model = AccountingUser
    template_name = 'extra_data/accounting_user.html'
    success_message = 'ذخیره شد'
    form_struct = {
        'form': AccountingUserForm,
        'childes': [
            {
                'form': '',
                'childes': [{}]
            },
        ]
    }

    def get_success_url(self):
        return reverse_lazy('extra_data:accounting_user')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        return context


class AccountingUserDatatableView(AjaxDatatableView):
    model = AccountingUser
    title = 'accounting_user_list'
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
            {'name': 'id', 'title': "<div class='px-3' style='max-width:40px;'>شناسه</div>", 'className': 'mxw-50px'},
            {'name': 'title', },
            {'name': 'name', 'title': "<div class='px-3' style='width:40px;'>نام اصلی</div>",},
            {'name': 'sepidar_id', },
            {'name': 'sepidar_group_id', },
            {'name': 'creator_user', 'lookup_field': '__username__icontains'},
            {'name': 'editor_user', 'lookup_field': '__username__icontains'},
            {'name': 'jalali_last_update_date', 'title': "<div class='px-3' style='width:40px;'>آخرین زمان تغییر</div>", 'searchable': False, 'orderable': False},
        ]

        return self.get_columns(cols)

    def customize_row(self, row, obj):
        x = super().customize_row(row, obj)
        row['title'] = '<a class="fw-bold" href="%s">%s</a>' % (
            reverse('extra_data:accounting_user.update', args=(obj.id,)),
            obj.title if obj.title else '_'
        )


class CustomerGroupUserView(LoginRequiredMixin, BaseView):
    model = CustomerGroup
    template_name = 'extra_data/customer_group_user.html'
    success_message = 'ذخیره شد'
    form_struct = {
        'form': CustomerGroupUserForm,
        'childes': [
            {
                'form': '',
                'childes': [{}]
            },
        ]
    }

    def get_success_url(self):
        return reverse_lazy('extra_data:customer_group_user')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        return context


class CustomerGroupUserDatatableView(AjaxDatatableView):
    model = CustomerGroup
    title = 'customer_group_user_list'
    initial_order = [["sepidar_id", "des"], ]
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
            {'name': 'sepidar_id', 'title': "<div class='px-3' style='max-width:40px;'>شناسه</div>", 'className': 'mxw-50px'},
            {'name': 'title', },
            {'name': 'current_user__username', 'title': "<div class='px-3' style='width:40px;'>نام اصلی</div>", },
            {'name': 'sepidar_group_id', },
            {'name': 'creator_user', 'lookup_field': '__username__icontains'},
            {'name': 'editor_user', 'lookup_field': '__username__icontains'},
            {'name': 'jalali_last_update_date', 'title': "<div class='px-3' style='width:40px;'>آخرین زمان تغییر</div>", 'searchable': False, 'orderable': False},
        ]

        return self.get_columns(cols)

    def customize_row(self, row, obj):
        x = super().customize_row(row, obj)
        row['title'] = '<a class="fw-bold" href="%s">%s</a>' % (
            reverse('extra_data:customer_group_user.update', args=(obj.sepidar_id,)),
            obj.title if obj.title else '_'
        )
        row['current_user__username'] = obj.current_user.username if obj.current_user else ''


def get_customer_dax(request, customer_id):
    """فقط باید چک بشه ایدی ارسالی درست است الان روی sepidar_party_id """
    # daxs = DaxCall()
    daxs_data = DaxCall.customer_dax()
    if not daxs_data:
        return JsonResponse({'res': 'no data found'})
    matches = [dax for dax in daxs_data if dax.get('dim_customer[dl_id]') == customer_id]
    if matches:
        data = dict()
        for k, v in matches[0].items():
            if 'dl_id' in k:
                continue
            else:
                data[k[1:-1]] = v
        context = {'dax': data}
        html = render_to_string('extra_data/partials/customer_dax.html', context, request)
        return JsonResponse({'res': html}, safe=False)
    return JsonResponse({'res': 'no data found'})
    #
    # for dax in daxs_data:
    #     customer_dl_id = dax.get('dim_customer[dl_id]')
    #     if customer_dl_id == customer_id:
    #         return JsonResponse(customer_dl_id, safe=False)
    #     else:
    #         return JsonResponse({'err': 'no data found'})


class ItemFromProductView(APIView):
    def dispatch(self, request, *args, **kwargs):
        view_name = self.request.GET.get('view_name')
        if view_name and self.request.method == 'GET':
            return getattr(self, view_name, 'get')(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, skus, response_function='default', *args, **kwargs):

        return JsonResponse({'res': 'invalid view name'})

    def get_image_and_datasheet(self, request, skus, response_function=None, *args, **kwargs):
        response_function = self.request.GET.get('response_function')
        res = ProductApiCall.get_product_by_skus(skus=skus, response_function=response_function)
        return JsonResponse({'res': res})


class CustomerAddressView(LoginRequiredMixin, BaseView):
    model = CustomerAddress
    template_name = 'extra_data/customer_address.html'
    success_message = '%(customer)s update'
    form_struct = {
        'form': CustomerAddressForm,
        'childes': [
            {
                'form': '',
                'childes': [{}]
            },
        ]
    }

    def get_success_message(self, cleaned_data):
        return f'آدرس {self.object.customer.title} save'

    def get_success_url(self):
        return reverse_lazy('extra_data:customer_address.update', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = Customer.objects.filter(pk=self.request.GET.get('pk')).first()
        context['form'] = CustomerAddressForm(initial={'customer': customer or self.object.customer},
                                              instance=self.object)
        return context

    def post(self, request, *args, **kwargs):
        x = super().post(request, *args, **kwargs)
        return x

    def form_valid(self, form):
        x = self.form.save()
        # x = super().form_valid(form)
        return JsonResponse({'res': True})

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        res = render_to_string(self.template_name, context=context, request=self.request)
        return JsonResponse({'res': res, 'jss': '', 'csss': ''})


def websoket(request, *args, **kwargs):
    iw = ItemWeight.objects.get(pk=100)
    form = ItemWeightForm(instance=iw)
    form.id = iw.pk
    return render(request, 'extra_data/item-realtime.html', context={'form': form})


class ItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasShopPermission]
    queryset = Item.objects.all().order_by('-created_date')
    serializer_class = ItemSerializer
    http_method_names = ['get']

    @staticmethod
    def update_and_clean(data, subtract_value, limit_value):
        """
        روی دیکشنری پیمایش می‌کند، مقدار free را منهای subtract_value می‌کند
        و اگر صفر یا منفی شد، کلید معادلش را حذف می‌کند

        Args:
            data: دیکشنری ورودی
            subtract_value: عددی که از free کم می‌شود
        """
        # لیستی برای ذخیره کلیدهایی که باید حذف شوند
        keys_to_remove = []

        # پیمایش روی کلیدهای سطح اول (899)
        for outer_key, outer_value in data.items():
            # پیمایش روی کلیدهای سطح دوم (2, 28, 51, 73)
            for inner_key, inner_value in outer_value.items():
                # مقدار free را منهای عدد مورد نظر می‌کنیم
                new_free = inner_value['free'] - subtract_value

                # اگر صفر یا منفی شد، کلید را برای حذف علامت‌گذاری می‌کنیم
                if new_free <= 0:
                    keys_to_remove.append(outer_key)
                else:
                    # در غیر این صورت مقدار جدید را جایگزین می‌کنیم
                    data[outer_key][inner_key]['free'] = min(new_free, limit_value)

        # حذف کلیدهای علامت‌گذاری شده
        for outer_key in keys_to_remove:
            del data[outer_key]
            # # اگر دیکشنری داخلی خالی شد، خود کلید خارجی را هم حذف می‌کنیم
            # if not data[outer_key]:
            #     del data[outer_key]

        return data

    @action(detail=False, methods=['get'], url_path='stock-free-quantity')
    def stock_free_quantity(self, request, *args, **kwargs):
        try:
            skus = request.GET.get('skus')
            out = dict()
            out_after_clean = dict()
            if skus:
                skus = skus.split(',')
                items = Item.objects.filter(sku__in=skus)
                for item in items:
                    zero_quantity = item.shop_zero_quantity
                    limit_quantity = item.shop_limit_quantity
                    min_order_quantity = item.shop_min_order_quantity
                    if not zero_quantity:
                        continue
                    if not limit_quantity:
                        continue

                    out[item.sku] = item.free_qty_dict()

                    out_after_clean = self.update_and_clean(out, zero_quantity, limit_quantity)

                    out_after_clean[item.sku].update({
                        'zero_quantity': zero_quantity,
                        'limit_quantity': limit_quantity,
                        'min_order_quantity': min_order_quantity or 1,
                    })

            return Response(out_after_clean)
        except Exception as e:
            return Response(show_error(e, __file__, output=True))