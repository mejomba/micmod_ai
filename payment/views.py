from num2fawords import words
from ajax_datatable import AjaxDatatableView
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import ListView

from core.views import BaseView, Base
from payment.forms import PaymentOrderModelForm
from payment.models import PaymentOrder
from tools.utils import to_jalali_date
from translator import get_text as _


class LocalPaymentOrderView(LoginRequiredMixin, BaseView):
    model = PaymentOrder
    # form_class = PaymentOrderModelForm
    template_name = 'payment/payment_local.html'
    has_flow = True
    flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json',
                                       'LocalPaymentOrderView')
    form_struct = {
        'form': PaymentOrderModelForm,
        'childes': [{}]
    }

    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        return context

    def get_success_url(self):
        return reverse_lazy('payment:local.payment.update', kwargs={'pk': self.object.pk})

    def get_success_message(self, cleaned_data):
        return f'تغییرات دخیره شد'

    def form_valid(self, form):
        if self.state_index == 2 and 'next' in self.request.POST and not form.cleaned_data.get('manager_confirmation'):
            form.errors.update({'manager_confirmation': 'بدون تایید امکان ارسال به مرحله نهایی وجود ندارد'})
            return super().form_invalid(form)
        
        return super().form_valid(form)
        


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
        {'name': 'pk', 'visible': False, 'orderable': True,},
        {'name': 'id', 'visible': True, 'title': _('code'), 'className': 'py-1 border currency-search', },
        {'name': 'request_date', 'visible': True, 'orderable': True, 'searchable': False},
        {'name': 'payment_date', 'visible': True, 'orderable': False, 'searchable': False},
        {'name': 'amount', 'visible': True, 'orderable': True,},
        {'name': 'behalf', 'visible': True, 'orderable': True},
        {'name': 'pay_to', 'visible': True, 'orderable': True},
        {'name': 'from_source', 'visible': True, 'orderable': True,  'lookup_field': '__title__icontains'},
        {'name': 'to_account', 'visible': True, 'orderable': True},
        {'name': 'applicant', 'visible': True, 'orderable': True},

        {'name': 'created_date', 'visible': True, 'orderable': True, 'searchable': False},
        {'name': 'creator_user', 'visible': True, 'orderable': True,
         'lookup_field': '__profile__first_name__icontains'},
        {'name': 'last_work_flow', 'title': 'آخرین وضعیت', 'visible': True, 'orderable': True, 'lookup_field': '__current_state_name__icontains'},
        {'name': 'last_work_flow__to_user', 'title': 'متعلق به', 'visible': True, 'orderable': True,
         'lookup_field': '__profile__first_name__icontains'},
    ]

    def get_initial_queryset(self, request=None):
        q = request.POST.get('q')
        qs = self.model.objects.get_access_object(request.user, q=q)
        qs = self.model.objects.filter(pk__in=[i.pk for i in qs])
        return qs

    def customize_row(self, row, obj):
        url = reverse_lazy('payment:local.payment.update', args=(obj.pk,))
        row['id'] = f"""<a href="{url}" target=_blank>{obj.pk}</a>"""
        row['last_work_flow__to_user'] = obj.last_work_flow.to_user.profile.first_name if obj.last_work_flow else ''
        row['request_date'] = '%s' % to_jalali_date(obj.request_date)
        row['payment_date'] = '%s' % to_jalali_date(obj.payment_date)


def num_to_fa_words(request):
    if request.method == 'POST':
        amount = request.POST.get('amount')
        if amount:
            if int(amount) >= 10:
                amount = int(amount) / 10
                amount_in_words = words(amount)
                return JsonResponse({'amount_in_words': amount_in_words})
            else:
                return JsonResponse({'': ''}, safe=False)
        else:
            return JsonResponse({'': ''}, safe=False)
    else:
        return JsonResponse({'error': 'Invalid amount'})
