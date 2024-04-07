from ajax_datatable import AjaxDatatableView
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.http import JsonResponse, Http404, HttpResponseRedirect
from django.urls import reverse_lazy, reverse
from django.views import generic

from micmod_base.forms import QuotationForm, QuotationItemFormset
from tools.utils import show_error
from .forms import ItemWeightForm

from accounts.mixins import FormFieldAccessMixin
from changelog.models import ChangeLog
from core.views import BaseView, Base
from extra_data.models import Item, ItemWeight
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
        if not self.object.sku:
            self.object.sku = self.object.pk
            self.object.save()
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
        context['object_logs'] = ChangeLog.get_log(context['item'])
        return context

    def form_valid(self, form):
        if self.request.POST.get('draft') or self.request.POST.get('back'):
            return super().form_valid(form)
        if self.state_index == 1 and not form.cleaned_data.get('technical_confirm'):
            self.success_message = 'امکان ارسال فرم به مرحله نهایی بدون تایید فنی وجود ندارد'
            # return HttpResponseRedirect('.')
            return super(SuccessMessageMixin, self).form_valid(form)

        return super().form_valid(form)
        # if self.request.POST.get('draft'):
        #     return super().form_valid(form)
        # if form.cleaned_data.get('technical_confirm') and not self.request.POST.get('back'):
        #     return super().form_valid(form)
        # if self.request.POST.get('back'):
        #     return super().form_valid(form)
        # else:
        #     self.success_message = 'امکان ارسال فرم به مرحله نهایی بدون تایید فنی وجود ندارد'
        #     return HttpResponseRedirect('.')


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
