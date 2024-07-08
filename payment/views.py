from ajax_datatable import AjaxDatatableView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import ListView

from core.views import BaseView
from payment.forms import PaymentOrderModelForm
from payment.models import PaymentOrder
from translator import get_text as _


class PaymentOrderView(LoginRequiredMixin, BaseView):
    model = PaymentOrder
    form_class = PaymentOrderModelForm
    template_name = 'payment/payment_order.html'

    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        return context

    def get_success_url(self):
        return reverse_lazy('payment:local.payment.list')


class PaymentOrderListView(ListView):
    model = PaymentOrder
    template_name = 'payment/payment_local_list.html'


class PaymentOrderDatatableView(AjaxDatatableView):
    model = PaymentOrder
    title = 'payment_orderr'
    initial_order = [["pk", "desc"], ]
    length_menu = [[6, 10, 15, -1], [6, 10, 15, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'pk', 'visible': True, 'title': _('code'), 'className': 'py-1 border currency-search'},
        {'name': 'id', 'visible': False, },
        {'name': 'request_date', 'visible': True, 'orderable': True, 'searchable': False},
        {'name': 'payment_date', 'visible': True, 'orderable': False, 'searchable': False},
        {'name': 'amount', 'visible': True, 'orderable': True,},
        {'name': 'behalf', 'visible': True, 'orderable': True},
        {'name': 'pay_to', 'visible': True, 'orderable': True},
        {'name': 'from_source', 'visible': True, 'orderable': True},
        {'name': 'to_account', 'visible': True, 'orderable': True},
        {'name': 'applicant', 'visible': True, 'orderable': True},

        {'name': 'created_date', 'visible': True, 'orderable': True, 'searchable': False},
        {'name': 'creator_user', 'visible': True, 'orderable': True,
         'lookup_field': '__profile__first_name__icontains'},
    ]

    # def get_initial_queryset(self, request=None):
    #     if request.user.base_group == 'trade':
    #         qs = Quotation.objects.filter(cancel=True, is_deleted=False)
    #     else:
    #         qs = Quotation.get_qs(request)
    #     # qs = qs.annotate(quotation_state=Cast('quotation', CharField()))
    #     qs = self.model.objects.filter(pk__in=[i.pk for i in qs])
    #     return qs

    def customize_row(self, row, obj):
        url = reverse_lazy('payment:local.payment.update', args=(obj.pk,))
        row['pk'] = f"""<a href="{url}" target=_blank>{obj.pk}</a>"""
