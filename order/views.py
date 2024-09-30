from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.urls import reverse_lazy

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