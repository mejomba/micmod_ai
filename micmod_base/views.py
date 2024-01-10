from pprint import pprint
import json

from django.contrib.contenttypes.models import ContentType

from sepidar.models import APILogs
from sepidar.models import Dl, Device
from sepidar.scripts.sepidar_classes import Urls
import uuid
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
from workflow.models import WorkFlow
from django.contrib.contenttypes.models import ContentType


# from workflow.models import WorkFlowAction


# User = get_user_model()

class QuotationsList(LoginRequiredMixin,View):
    def get(self, request):
        q = self.request.GET.get('q')
        quotations_record_lst = Quotation.objects.get_access_object(request.user, q=q)

        greeting = {}
        greeting['heading'] = _("quotation")
        greeting['pageview'] = _("micmod_base")
        # greeting['quotations'] = quotations_record
        greeting['quotations'] = quotations_record_lst

        return render (request,'micmod-base/quotation/list.html',greeting)


class QuotationsView(LoginRequiredMixin, BaseView):
    template_name = 'micmod-base/quotation/view.html'
    # formset = inlineformset_factory(Quotation, QuotationItem, form=QuotationItemForm, extra=1,)
    form_class = QuotationForm
    model = Quotation
    wf_last_step_is_open = True
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

    has_formset = True
    formset_form = QuotationItemForm2
    formset_model = QuotationItem
    formset_fk_field = 'quotation'
    related_name_fk = 'quotation'

    def get_success_url(self):
        return reverse_lazy('sls:quotations.view', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        res = super().form_valid(form)
        """..."""

        for qi in self.object.quotation.all():
            if bool(qi.local_price_inquiry_done) != bool(qi.need_local_price_inquiry):
                """create new quotation"""
                """مجاز نیستن برن مرحله بعد"""

                """quotation"""
                quotation_data = dict()
                pop_quotation_item = ['id', 'guid', 'created_date', 'last_update_date', 'creator_user', 'editor_user']
                for field in self.model._meta.fields:
                    quotation_data[field.name] = getattr(self.object, field.name, None)
                [quotation_data.pop(k) for k in pop_quotation_item]

                # InquiryResultForm._meta.model.objects.create()
                quotation_data['quotation_self'] = self.object
                quotation_data['guid'] = uuid.uuid4()
                new_quotation, _ = self.model.objects.get_or_create(**quotation_data)
                new_quotation.save_user(self.request)

                """quotation item"""
                pop_qi_item = ['id', 'created_date', 'last_update_date', 'creator_user', 'editor_user']
                qi_data = dict()
                qi_data_copy = None
                qi_list = []
                for field in self.formset_model._meta.fields:
                    qi_data[field.name] = getattr(qi, field.name, None)
                    qi_data_copy = qi_data.copy()
                if qi_data_copy:
                    qi_list.append(qi_data_copy)
                # for item in qi_list:
                #     for k in pop_qi_item:
                #         item.pop(k)
                [item.pop(k) for k in pop_qi_item for item in qi_list]
                [qi_data.pop(k) for k in pop_qi_item]

                qi_obj_list = []
                for data in qi_list:
                    qi_obj_list.append(self.formset_model.objects.create(**data))

                """inquiry result"""
                for iqr in qi.quotation_item_rel.all():
                    iqr._mata.model.objects.create()

            else:
                """به مرحله بعد میرود"""
                next()
                print('عدم نیاز به تایید', qi.quantity)
        """..."""
        try:
            device = Device.objects.all().first()
            if not self.object.guid:
                self.object.guid = uuid.uuid4()
                self.object.save()
            elif (sepidar_pk := self.object.sepidar_quotation_id) and self.state_index == 2 and 'next' in self.request.POST:
                APILogs.new_call(device=device, url=Urls.del_quotation.url.format(sepidar_pk),
                                 method=Urls.del_quotation.method)

            if self.state_index == 2 and 'next' in self.request.POST:

                quotation_items = []
                for idx, qi in enumerate(self.object.quotation.all(), 1):
                    qi_dict = {
                        'RowID': idx,
                        'ItemRef': qi.itemid,  # optional
                        'StockRef': 2,  # optional
                        'Quantity': qi.quantity,
                        'SecondaryQuantity': 0,
                        'Fee': qi.fee or 1,
                        'Price': qi.price or 1,
                        'Description': 'qi.description',
                        'PriceInfoPercentDiscount': 0,
                        'PriceInfoDiscountRate': 0,
                        'AggregateAmountPercentDiscount': 0,
                        'AggregateAmountPriceDiscount': 0,
                        'AggregateAmountDiscountRate': 0,
                        'CustomerDiscount': 0,
                        'CustomerDiscountRate': 0,
                        'Discount': 0,
                        # 'DiscountParentRef': 1,  # optional
                        'Tax': 0,
                        'Duty': 0,
                        'Addition': 0,
                    }
                    quotation_items.append(qi_dict)

                quotation_data = {
                    'GUID': str(self.object.guid),
                    'CurrencyRef': self.object.currency_ref.pk,
                    'Rate': 0,
                    'ExpirationDate': str(self.object.expiration_date),
                    'CustomerRef': self.object.customer_party_id,  # 11
                    'SaleTypeRef': 2,
                    # 'AddressRef': '1',  # optional
                    'DiscountOnCustomer': 0,
                    'Price': self.object.price or 1,
                    'Discount': 0,
                    'Tax': 0,
                    'Duty': 0,
                    'Addition': 0,
                    'items': quotation_items,
                }
                d = json.dumps(quotation_data)

                api_res = APILogs.new_call(device=device, url=Urls.pos_quotations.url,
                                           method=Urls.pos_quotations.method, data=d)
                self.object.sepidar_quotation_id = api_res[1].get('ID') if api_res[0] == 201 else None
                self.object.sepidar_number = api_res[1].get('Number') if api_res[0] == 201 else None
                self.object.save()
        except Exception as e:
            print('rol back ....')
            content_type = ContentType.objects.filter(model=self.object._meta.model_name, app_label=self.object._meta.app_label).first()
            flow_object = self.flow_model.objects.filter(object_id=self.object.id, content_type=content_type).last()
            if flow_object:
                flow_object.delete()
        return res

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
        # context['detail_logs'].reverse()
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
