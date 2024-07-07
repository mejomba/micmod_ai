from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import ListView

from core.views import BaseView
from payment.forms import PaymentOrderModelForm
from payment.models import PaymentOrder


class PaymentOrderView(LoginRequiredMixin, BaseView):
    model = PaymentOrder
    form_class = PaymentOrderModelForm
    template_name = 'payment/payment_order.html'
    # success_url = reverse_lazy('micmod_base:currency_exchange')

    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class PaymentOrderListView(ListView):
    ...