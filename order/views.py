from ajax_datatable import AjaxDatatableView
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView

from core.views import BaseView, Base
from micmod_base.models import QuotationItem
# from order.models import OrderItem
from .forms import OrderForm, PackingForm, PackingItemForm
from .models import Order, OrderOrder, Packing
from translator import get_text as _

# def factor_order_item(request, sku, quantity):
#     items = get_object_or_404(QuotationItem, goods_code=sku)
#
#     for item in items.goods_code:
#         order_item = OrderItem.objects.create(order__title=item)


class OrderView(LoginRequiredMixin, BaseView):
    template_name = 'order/view.html'
    form_class = OrderForm
    model = Order
    wf_last_step_is_open = True
    has_flow = True
    form_struct = {
        'form': OrderForm,
        'childes': [
            {},
        ]
    }
    flow_config = Base.get_flow_config(settings.BASE_DIR/'_keenthemes/view_config.json', 'OrderView')

    def get_success_url(self):
        return reverse_lazy('order:order.view', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        res = super().form_valid(form)
        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        return context


class OrderListView(LoginRequiredMixin, ListView):
    model = Order
    template_name = 'order/list.html'


class OrderDataTableListView(AjaxDatatableView):
    model = Order
    title = 'order_list'
    initial_order = [["created_date", "des"], ]
    length_menu = [[10, 20, 50, -1], [10, 20, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'
    show_column_filters = True
    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'id', 'orderable': True, 'visible': False, },
        {'name': 'order_title', 'orderable': True, 'visible': True, },
        {'name': 'status', 'orderable': True, 'visible': True, },
        {'name': 'item', 'orderable': True, 'visible': True, 'lookup_field': '__sku__icontains'},
        {'name': 'qi', 'title': 'customer', 'orderable': True, 'visible': True, 'lookup_field': '__quotation__customer_party_id__title__icontains'},
        {'name': 'transportation_method', 'orderable': True, 'visible': True, },
        {'name': 'production_lead_time', 'orderable': True, 'visible': True, },
        {'name': 'trade_commitment_date', 'orderable': True, 'visible': True, },
        {'name': 'commitment_date_to_customer', 'orderable': True, 'visible': True, },
        {'name': 'quantity', 'orderable': True, 'visible': True, },
        {'name': 'description_sale', 'orderable': True, 'visible': True, },
        {'name': 'order_type', 'orderable': True, 'visible': True, },
        {'name': 'sales_admin_confirmation', 'orderable': True, 'visible': True, },
        {'name': 'cancel', 'orderable': True, 'visible': True, },
        {'name': 'is_over', 'orderable': True, 'visible': True, },
        {'name': 'created_date', 'orderable': True, 'visible': True, },

        # {'name': 'sepidar_dl_code', 'orderable': True, 'visible': True, 'width': 600, },
        # {'name': 'title', 'title': '<div class="px-15">عنوان</div>', 'orderable': True, 'visible': True,
        #  'className': 'text-center'},
    ]

    def customize_row(self, row, obj):
        row['order_title'] = '<a class="fw-bold" target=_blank href="%s">%s</a>' % (
            reverse('order:order.view', args=(obj.id,)),
            obj.order_title if obj.order_title else 'بدون عنوان'
        )
        row['qi'] = f'<span>{obj.qi.quotation.customer_party_id.title}</span>' if obj.qi else ""


class OrderAction(ListView):
    model = Order
    template_name = 'order/order_action.html'
    paginate_by = 50

    def get_queryset(self):
        x = Order.objects.filter(order_base_items__isnull=False).distinct()
        return x

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(**kwargs)
        context['forms'] = []
        for o in context['object_list']:
            f = OrderForm(instance=o)
            context['forms'].append(f)
        context['form'] = True
        return context


def ajax_order_order_add(request):
    import json
    data = json.loads(request.body)
    data['creator_user'] = request.user
    data['editor_user'] = request.user
    quantity = data.get('quantity')
    obj, created = OrderOrder.objects.get_or_create(defaults=data, order_base_id=data.get('order_base_id'), order_rel_id=data.get('order_rel_id'))
    if quantity and not created:
        obj.quantity += quantity
        obj.save()
    form = OrderForm(instance=obj.order_base)
    html = render_to_string('order/partial/order_order_report.html', context={'form': form})
    return JsonResponse({'res': html})


class PackingView(LoginRequiredMixin, BaseView):
    template_name = 'order/view.html'
    form_class = PackingForm
    model = Order
    wf_last_step_is_open = True
    has_flow = True
    form_struct = {
        'form': PackingForm,
        'childes': [
            {
                'form': PackingItemForm,
                'childes': [{}]
            },
        ]
    }
    flow_config = Base.get_flow_config(settings.BASE_DIR/'_keenthemes/view_config.json', 'PackingView')

    def get_success_url(self):
        return reverse_lazy('order:packing.view', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        res = super().form_valid(form)
        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        return context


class PackingListView(LoginRequiredMixin, ListView):
    """
    sku list view
    """
    model = Packing
    template_name = 'extra_data/sku_list.html'
    context_object_name = 'items'


class PackingDataTableListView(AjaxDatatableView):
    model = Packing
    title = 'packing'
    initial_order = [["created_date", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'TP_METHOD', 'visible': True, 'title': _('TP_METHOD'), 'className': 'py-1 border sku-search',
         'defaultContent': '<a href"#">test</a>', 'lookup_field': '__sku__iexact'},
        {'name': 'sum_qty', 'visible': True, 'title': _('sum_qty'), 'className': 'py-1 border', 'searchable': False},
        {'name': 'sum_arrived_qty', 'visible': True, 'title': _('sum_arrived_qty'), 'className': 'py-1 border', },
        {'name': 'tp_method', 'visible': True, 'title': _('tp_method'), 'className': 'py-1 border', },
        {'name': 'pack_date', 'visible': True, 'title': _('pack_date'), 'className': 'py-1 border', },
        {'name': 'bl_number', 'visible': True, 'title': _('bl_number'), 'className': 'py-1 border', },
        {'name': 'sales_manager_needed', 'visible': True, 'title': _('sales_manager_needed'), 'className': 'py-1 border', },
        {'name': 'creator_user', 'visible': True, 'title': _('creator_user'), 'className': 'py-1 border', },
        {'name': 'created_date', 'orderable': True, 'visible': True, },
    ]