from django.contrib.contenttypes.models import ContentType
from django.template.loader import render_to_string
from django.utils import timezone
from django.views import View
from num2fawords import words
from ajax_datatable import AjaxDatatableView
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView

from core.views import BaseView, Base
from payment.forms import PaymentOrderModelForm, PaymentDocumentsForm, CreditCardForm, PaymentItemForm, PaymentForm
from payment.models import PaymentOrder, PaymentDocument, CreditCard, GenericPaymentItem, Payment
from tools.utils import to_jalali_date, is_ajax
from translator import get_text as _
from workflow.models import WorkFlow
from datetime import datetime


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
        # pay => """اسناد مثبته توسط درخواست کننده"""
        # pay_accounting => """اسناد پرداخت توسط حسابدار"""
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        last_wf = self.object.last_work_flow if self.object else None
        if self.object and last_wf and last_wf.current_state_name in ['کنترل حسابداری']:
            context['form'].initial["accounting"] = last_wf.to_user

        context['add_pay_doc'] = True if self.state_index == 0 else False
        context['add_pay_accounting_doc'] = True if self.state_index >= 1 and self.request.user.base_group == 'accounting' else False
        context['show_pay_doc'] = True if self.state_index >= 1 else False
        context['show_pay_accounting_doc'] = True if self.state_index >= 1 else False
        context['wf_access'] = self.wf_access

        return context

    def get_success_url(self):
        return reverse_lazy('payment:local.payment.update', kwargs={'pk': self.object.pk})

    def get_success_message(self, cleaned_data):
        return f'تغییرات دخیره شد'

    def form_valid(self, form):
        if self.state_index == 2 and 'next' in self.request.POST and not form.cleaned_data.get('manager_confirmation') and form.cleaned_data.get('is_paid'):
            form.errors.update({'manager_confirmation': 'بدون تایید امکان ارسال به مرحله نهایی وجود ندارد'})
            return super().form_invalid(form)
        if self.state_index == 3 and 'next' in self.request.POST and not form.cleaned_data.get('manager_confirmation'):
            form.errors.update({'manager_confirmation': 'بدون تایید امکان ارسال به مرحله نهایی وجود ندارد'})
            return super().form_invalid(form)
        
        res = super().form_valid(form)
        if self.state_index == 2 and 'next' in self.request.POST and form.cleaned_data.get(
                'manager_confirmation') and form.cleaned_data.get('is_paid'):
            WorkFlow.objects.create(created_date=timezone.now(), last_update_date=timezone.now(), wf_status=3,
                                    action='ایجاد', state='پرداخت', belong_to_group='accounting_user',
                                    object_id=self.object.pk, content_type=ContentType.objects.get_for_model(PaymentOrder),
                                    creator_user=self.request.user, editor_user=self.request.user, from_user=self.object.last_work_flow.to_user,
                                    to_user=self.object.last_work_flow.to_user, current_state_name='مرحله نهایی')
        return res


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
        {'name': 'to_account', 'visible': True, 'orderable': True, 'title': '<div class="px-20">به حساب یا کارت</div>'},
        {'name': 'applicant', 'visible': True, 'orderable': True},

        {'name': 'created_date', 'visible': True, 'orderable': True, 'searchable': False},
        {'name': 'creator_user', 'visible': True, 'orderable': True,
         'lookup_field': '__profile__first_name__icontains'},
        {'name': 'last_work_flow', 'title': 'آخرین وضعیت', 'visible': True, 'orderable': True, 'lookup_field': '__current_state_name__icontains'},
        {'name': 'last_work_flow__to_user', 'title': 'متعلق به', 'visible': True, 'orderable': True,
         'lookup_field': '__profile__first_name__icontains'},
        {'name': 'is_paid', 'visible': True, 'orderable': True},
    ]

    def get_initial_queryset(self, request=None):
        q = request.POST.get('q')
        qs = self.model.objects.get_access_object(request.user, q=q)
        qs = self.model.objects.filter(pk__in=[i.pk for i in qs])
        if q == 'pay':
            qs = qs.filter(is_paid=True)
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
            # if int(amount) >= 10:
            #     amount = int(amount) / 10
            amount_in_words = words(amount)
            return JsonResponse({'amount_in_words': amount_in_words})
            # else:
            #     return JsonResponse({'': ''}, safe=False)
        else:
            return JsonResponse({'': ''}, safe=False)
    else:
        return JsonResponse({'error': 'Invalid amount'})


class LocalPaymentDoc(LoginRequiredMixin, BaseView):
    model = PaymentDocument
    template_name = 'payment/pay_accounting_document.html'
    success_message = '%(payment_order)s update'
    form_struct = {
        'form': PaymentDocumentsForm,
        'childes': [
            {
                'form': '',
                'childes': [{}]
            },
        ]
    }

    def get_success_url(self):
        return reverse_lazy('payment:local.payment.update', kwargs={'pk': self.object.payment_order.pk})

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        x = super().form_valid(form)
        return x

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pay = PaymentOrder.objects.filter(pk=self.request.GET.get('pk')).first()
        last_wf = pay.last_work_flow if pay else None
        doc_type = ''
        if not last_wf:
            doc_type = "A"

        if last_wf and last_wf.current_state_name in ["درخواست اولیه"]:
            doc_type = "A"
            self.template_name = 'payment/pay_document.html'
        if last_wf and last_wf.current_state_name not in ["درخواست اولیه"]:
            doc_type = "B"
            self.template_name = 'payment/pay_accounting_document.html'

        context['form'] = PaymentDocumentsForm(initial={'payment_order': pay or self.object.payment_order,
                                                        'doc_type': doc_type}, instance=self.object)
        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        res = render_to_string(self.template_name, context=context, request=self.request)
        return JsonResponse({'res': res})
    
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)


class CreditCardView(LoginRequiredMixin, BaseView):
    model = CreditCard
    template_name = 'payment/credit_card.html'
    success_message = 'ذخیره شد'
    form_struct = {
        'form': CreditCardForm,
        'childes': [
            {
                'form': '',
                'childes': [{}]
            },
        ]
    }

    def get_success_url(self):
        return reverse_lazy('payment:credit_card')

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        x = super().form_valid(form)
        return x

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        return context


class CreditCardDatatableView(AjaxDatatableView):
    model = CreditCard
    title = 'credit_card_list'
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
            {'name': 'credit_card_number', 'title': "<div class='px-3' style='width:40px;'>کارت / حساب / شبا</div>",},
            {'name': 'creator_user', 'lookup_field': '__username__icontains'},
            {'name': 'editor_user', 'lookup_field': '__username__icontains'},
            {'name': 'jalali_last_update_date', 'title': "<div class='px-3' style='width:40px;'>آخرین زمان تغییر</div>", 'searchable': False, 'orderable': False},
        ]

        return self.get_columns(cols)

    def get_initial_queryset(self, request=None):
        return super().get_initial_queryset(request)

    def customize_row(self, row, obj):
        x = super().customize_row(row, obj)
        row['title'] = '<a class="fw-bold" href="%s">%s</a>' % (
            reverse('payment:credit_card.update', args=(obj.id,)),
            obj.title if obj.title else '_'
        )


class CreditCardAjax(View):
    def get(self, request):
        title = request.GET.get('title')
        credit_card = CreditCard.objects.filter(title=title).first()
        if credit_card:
            return JsonResponse({'res': credit_card.credit_card_number})
        else:
            return JsonResponse({'res': 'حسابی پیدا نشد. حساب ایجاد کنید یا به صورت دستی مقدار را وارد کنید'})


class PaymentView(LoginRequiredMixin, BaseView):
    template_name = 'payment/payment_view.html'
    form_class = PaymentForm
    model = Payment
    # wf_last_step_is_open = True
    # has_flow = True
    success_message = 'با موفقیت ذخیره شد'
    form_struct = {
        'form': PaymentForm,
        'childes': [
            {},
        ]
    }
    # flow_config = Base.get_flow_config(settings.BASE_DIR/'_keenthemes/view_config.json', 'GIOView')

    def get_success_url(self):
        return reverse_lazy('payment:payment.update', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        res = super().form_valid(form)
        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        return context


class PaymentItemView(LoginRequiredMixin, BaseView):
    template_name = 'payment/payment_item_view.html'
    form_class = PaymentItemForm
    model = GenericPaymentItem
    form_struct = {
        'form': PaymentItemForm,
        'childes': [
            {},
        ]
    }

    def get_success_url(self):
        return reverse_lazy('payment:paymentitem.update', kwargs={'pk': self.object.payment.pk})

    def post(self, request, *args, **kwargs):
        x = super().post(request, *args, **kwargs)
        if is_ajax(request):
            return JsonResponse({'res': 'success'})
        else:
            return x

    def form_valid(self, form):
        x = super().form_valid(form)
        return JsonResponse({'res': True})

    def get(self, request, pk=None, *args, **kwargs):
        if is_ajax(request):
            context = self.get_context_data()
            res = render_to_string(self.template_name, context=context)
            return JsonResponse({'res': res})
        return JsonResponse({'res': 'only ajax request'})

    def get_context_data(self, **kwargs):
        context = {}
        payment = Payment.objects.filter(pk=self.request.GET.get('pk')).first()
        form = self.form_class(initial={'payment': payment or self.object.payment}, instance=self.object)
        context['app_name'] = self.request.resolver_match.app_name
        context['form'] = form
        return context


class PaymentListView(LoginRequiredMixin, View):
    """
    sku list view
    """
    model = Payment
    template_name = 'payment/payment_list.html'
    context_object_name = 'items'

    def get(self, request, *args, **kwargs):
        context = {}
        return render(request, self.template_name, context)


class PaymentDataTableListView(AjaxDatatableView):
    model = Payment
    title = 'Payment'
    initial_order = [["created_date", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'id', 'visible': False, 'title': _('id'), 'className': 'py-1 border',},
        {'name': 'pk', 'visible': True, 'title': _('id'), 'className': 'py-1 border',},
        {'name': 'from_date', 'visible': True, 'title': _('gio_date'), 'className': 'py-1',},
        {'name': 'to_date', 'visible': True, 'title': _('total_quantity'), 'className': 'py-1', },
        {'name': 'total_amount', 'title': _('total_amount'), 'className': 'py-1', },
        {'name': 'description', 'orderable': True, 'visible': True, },
        {'name': 'creator_user', 'orderable': True, 'visible': True, 'title': _('creator_user')},
        {'name': 'editor_user', 'orderable': True, 'visible': True, 'title': _('editor_user')},
        {'name': 'created_date', 'orderable': True, 'visible': True, },
    ]

    def customize_row(self, row, obj):
        row['pk'] = '<a class="fw-bold" target=_blank href="%s">%s</a>' % (
            reverse('payment:payment.update', args=(obj.id,)),
            obj.id if obj.id else 'بدون عنوان'
        )
