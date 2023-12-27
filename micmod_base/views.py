from pprint import pprint

from ajax_datatable import AjaxDatatableView
from django.contrib.auth.mixins import LoginRequiredMixin
from accounts.models import User
from django.core.paginator import Paginator
from django.forms import inlineformset_factory
from django.http import HttpResponse
from django.shortcuts import render, redirect, reverse, get_object_or_404
from django.urls import reverse_lazy
from django.conf import settings
from django.views.generic.edit import FormView
from jalali_date import datetime2jalali

from changelog.models import ChangeLog
from inquiry.forms import InquiryResultForm
from micmod_base.base import CurrencyExchange
from micmod_base.forms import QuotationForm, QuotationItemForm, QuotationItemForm2, CurrencyExchangeForm, \
    QuotationItemFormset
from sepidar.models import Dl
from tools.utils import show_error
from translator import get_text as _
from django.contrib.auth import get_user_model
# Create your views here.
from django.views import View

from micmod_base.models import Quotation, QuotationItem
from core.views import BaseView, Base


# from workflow.models import WorkFlowAction


# User = get_user_model()

class QuotationsList(LoginRequiredMixin,View):
    def get(self, request):
        quotations_record = Quotation.custom_objects.own_quotations(request)
        # p = Paginator(quotations_record, 10)
        # page = request.GET.get('page')
        # if p == None:
        #    page = int(1)
        # page_obj = p.get_page(page)
        greeting = {}
        greeting['heading'] = _("quotation")
        greeting['pageview'] = _("micmod_base")
        greeting['quotations'] = quotations_record
        # greeting['page_obj'] = page_obj

        return render (request,'micmod-base/quotation/list.html',greeting)


class QuotationsView(LoginRequiredMixin, BaseView):
    template_name = 'micmod-base/quotation/view.html'
    # formset = inlineformset_factory(Quotation, QuotationItem, form=QuotationItemForm, extra=1,)
    form_class = QuotationForm
    model = Quotation
    has_flow = True
    form_struct = {
        'form': QuotationForm,
        'childes': [
            {
                'form': QuotationItemFormset,
                'childes': [{'form': InquiryResultForm}]
            },
        ]
    }
    flow_config = Base.get_flow_config(settings.BASE_DIR/'_keenthemes/view_config.json', 'QuotationsView')
    # print(flow_config)

    has_formset = True
    formset_form = QuotationItemForm2
    formset_model = QuotationItem
    formset_fk_field = 'quotation'
    related_name_fk = 'quotation'

    def get_success_url(self):
        return reverse_lazy('sls:quotations.view', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['heading'] = _('create')
        context['pageview'] = _('quotation')
        if self.object:
            self.object.created_date = datetime2jalali(self.object.created_date).strftime('%y/%m/%d-%H:%M')
            self.object.last_update_date = datetime2jalali(self.object.last_update_date).strftime('%y/%m/%d-%H:%M')
        context['data'] = self.object

        related_obj = getattr(self.object, f'{self.related_name_fk}', None)
        context['detail_logs'] = []
        if related_obj:
            for item in related_obj.all():
                context['detail_logs'].append(ChangeLog.get_log(item))
        return context


def print_view(request,id=-1):
    template_name = 'micmod-base/quotation/view-print.html'
    # formset = inlineformset_factory(Quotation, QuotationItem, form=QuotationItemForm, extra=0, )
    formset = inlineformset_factory(Quotation, QuotationItem, form=QuotationItemForm2, extra=0, )
    greeting = {}
    greeting['heading'] = _("create")
    greeting['pageview'] = _("quotation")
    quotation = Quotation.objects.filter(id=id).first()
    greeting['form'] = QuotationForm(instance=quotation)
    greeting['formset'] = formset(instance=quotation)
    if quotation:
        quotation.created_date = datetime2jalali(quotation.created_date).strftime('%y/%m/%d-%H:%M')
        quotation.last_update_date = datetime2jalali(quotation.last_update_date).strftime('%y/%m/%d-%H:%M')
    greeting['data'] = quotation
    return render(request, template_name, greeting)


class CurrencyExchangeView(LoginRequiredMixin, BaseView):
    model = CurrencyExchange
    form_class = CurrencyExchangeForm
    template_name = 'micmod-base/currency_exchange_list_or_create.html'
    success_url = reverse_lazy('sls:currency_exchange')

    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # context['form'] = self.form_class(initial={'currency': 2})
        # context.update({
        #     'form': self.form_class(initial=map(lambda x: x, self.request.GET.items()))
        # })
        return context


class CurrencyExchangeDataTableView(AjaxDatatableView):
    model = CurrencyExchange
    title = 'currency_list'
    initial_order = [["last_update_date", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'currency', 'visible': True, 'title': _('currency'), 'className': 'py-1 border currency-search', 'lookup_field': '__title__icontains'},
        {'name': 'buy_exchange', 'visible': True, 'title': _('buy_exchange'), 'className': 'py-1 border'},
        {'name': 'sell_exchange', 'visible': True, 'title': _('sell_exchange'), 'className': 'py-1 border'},
        {'name': 'id', 'visible': False, },
        {'name': 'last_update_date', 'visible': False, 'orderable': True},
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
            qs = self.model.objects.filter(sku=param)
        else:
            qs = self.model.objects.all()
        return qs.order_by('last_update_date')

    def customize_row(self, row, obj):
        row['currency'] = '<a class="fw-bold" href="%s">%s</a>' % (
                      reverse('sls:currency_exchange', args=(obj.id,)),
                      obj.currency if obj.currency else '_'
                    )
