from ajax_datatable import AjaxDatatableView
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView

from core.views import BaseView, Base
from micmod_base.models import QuotationItem
# from order.models import OrderItem
from .forms import OrderForm
from .models import Order


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
        return context


class OrderListView(LoginRequiredMixin, ListView):
    model = Order
    template_name = 'order/list.html'


class OrderDataTableListView(AjaxDatatableView):
    model = Order
    title = 'order_list'
    initial_order = [["created_date", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'
    show_column_filters = True
    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'id', 'orderable': True, 'visible': False, },
        {'name': 'order_title', 'orderable': True, 'visible': True, },
        {'name': 'status', 'orderable': True, 'visible': True, },
        {'name': 'item', 'orderable': True, 'visible': True, },
        {'name': 'customer', 'orderable': True, 'visible': True, },
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
        row['id'] = '<a class="fw-bold" target=_blank href="%s">%s</a>' % (
            reverse('order:order.view', args=(obj.id,)),
            obj.title if obj.title else '_'
        )
