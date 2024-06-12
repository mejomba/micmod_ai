from pprint import pprint
import json

from django.contrib.contenttypes.models import ContentType
from django.template.loader import render_to_string
from django.db.models import Q, QuerySet, CharField
from django.db.models.functions import Cast

from django.utils import timezone

from comments.forms import CommentsForm
from extra_data.models import Item
from inquiry.models import InquiryResult
from notifications.models import Messages
from sepidar.models import APILogs
from sepidar.models import Dl, Device
from sepidar.scripts.sepidar_classes import Urls
import uuid
from ajax_datatable import AjaxDatatableView
from django.contrib.auth.mixins import LoginRequiredMixin
from accounts.models import User
from django.core.paginator import Paginator
from django.forms import inlineformset_factory
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.shortcuts import render, redirect, reverse, get_object_or_404
from django.urls import reverse_lazy
from django.conf import settings
from django.views.generic.edit import FormView
from jalali_date import datetime2jalali

from changelog.models import ChangeLog
from inquiry.forms import InquiryResultForm
from micmod_base.base import CurrencyExchange
from micmod_base.forms import QuotationForm, QuotationItemForm2, CurrencyExchangeForm, \
    QuotationItemFormset, InquiryResultFormset
from sepidar.models import Dl
from tools.import_data import import_customers_from_sepidar
from tools.utils import show_error, to_jalali_date
from translator import get_text as _
from django.contrib.auth import get_user_model
# Create your views here.
from django.views import View

from micmod_base.models import Quotation, QuotationItem
from core.views import BaseView, Base
from workflow.models import WorkFlow
from django.contrib.contenttypes.models import ContentType
from .forms import PendingFormFilter
from django.http import HttpResponseRedirect
from django.urls import reverse
# from core.mixins import DuplicateMixin
# from workflow.forms import WorkFlowModelForm
# import datetime


class QuotationsList(LoginRequiredMixin,View):
    def get(self, request):
        q = self.request.GET.get('q')
        # quotations_record_lst = Quotation.objects.get_access_object(request.user, q=q)

        greeting = {}
        greeting['heading'] = _("quotation")
        greeting['pageview'] = _("micmod_base")
        # greeting['quotations'] = quotations_record
        # greeting['quotations'] = quotations_record_lst

        return render(request,'micmod-base/quotation/list_datatable.html',greeting)


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
        return reverse_lazy('micmod_base:quotations.view', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        if self.object is None:
            import_customers_from_sepidar(extra_data={"creator_user_id": 1, "editor_user_id": 1})
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        # if 'submit_duplicate' in self.request.POST:
        #     return self.duplicate(self.object, [], ['quotation'])
        """ run import customer from sepidar before object create"""
        if self.object is None:
            import_customers_from_sepidar(extra_data={"creator_user_id": 1, "editor_user_id": 1})

        res = super().form_valid(form)
        # if self.object and self.object.last_work_flow.current_state_name == 'استعلام قیمت':
        #     Messages.send_message(
        #         **{
        #             'creator_user_id': self.object.creator_user_id,
        #             'user': self.object.last_work_flow.to_user,
        #             'title': f'{_(self.object.last_work_flow.content_type.name)}| {_(self.object.last_work_flow.state)}',
        #             'body': f' کاربر {self.object.creator_user.username} فرایند این موضوع را به شما واگذار کرده است.',
        #             'icon_url': getattr(self.model, 'icon_url', None) or "cube-2",
        #             'link': f'/{self.object.last_work_flow.content_type.app_label}/{self.object.last_work_flow.content_type.model}/view/{self.object.pk}',
        #             'content_type': self.object.last_work_flow.content_type,
        #             'object_id': self.object.pk
        #         }
        #     )
        if 'back' in self.request.POST or 'change_user' in self.request.POST:
            return res
        if not self.object.is_official:
            self.object.official_value = 0
            self.object.save()

        new_quotation = None
        try:

            device = Device.objects.all().first()
            if not self.object.guid:
                self.object.guid = uuid.uuid4()
                self.object.save()
            elif (sepidar_pk := self.object.sepidar_quotation_id) and self.state_index == 2 and 'next' in self.request.POST:
                APILogs.new_call(device=device, url=Urls.del_quotation.url.format(sepidar_pk),
                                 method=Urls.del_quotation.method, save=True)

            if (self.state_index == 1 or self.state_index == 1) and 'submit/copy_q' in self.request.POST:
                flow_copy = False

                """copy quotation"""
                for qi in self.object.quotation.all():
                    if bool(qi.local_price_inquiry_done) != bool(qi.need_local_price_inquiry) or \
                            bool(qi.foreign_price_inquiry_done) != bool(qi.need_foreign_price_inquiry):
                        """مجاز نیستن برن مرحله بعد"""
                        """create new quotation"""
                        quotation_data = dict()
                        pop_quotation_item = ['id', 'guid', 'created_date', 'last_update_date', 'creator_user',
                                              'editor_user']
                        for field in self.model._meta.fields:
                            quotation_data[field.name] = getattr(self.object, field.name, None)
                        [quotation_data.pop(k) for k in pop_quotation_item]

                        quotation_data['quotation_self'] = self.object
                        quotation_data['guid'] = uuid.uuid4()
                        if not new_quotation:
                            new_quotation = self.model.objects.create(**quotation_data)

                            """تمام change log ها کپی بشن (فقط یک بار)"""
                            logs = ChangeLog.get_log(self.object)
                            for log in logs:
                                log.pk = None
                                log.content_type = ContentType.objects.get_for_model(Quotation)
                                log.object_id = new_quotation.pk
                                log.save()

                            """تمام wf ها کپی بشن (فقط یک بار)"""
                            if not flow_copy:
                                flows = self.get_flow(self.object)
                                for idx, flow in enumerate(flows):
                                    if idx == len(flows) - 1:
                                        break
                                    flow.pk = None
                                    flow.object_id = new_quotation.pk
                                    flow.save()
                                    flow_copy = True
                                    new_quotation.last_work_flow = flow

                            """ این آیتم در مرحله استعلام می ماند و wf ثبت نمیکند """
                            # """ این آیتم به مرحله قبل میرود و wf برگشت ثبت میکند """
                            # flow_items = self.get_flow(self.object).filter(wf_status=3).order_by('-id')
                            # pad = 2 if self.state_index >= 2 else 1
                            # for item in flow_items:
                            #     if pad >= 2:
                            #         to_user = item.to_user
                            #     else:
                            #         to_user = item.from_user
                            #     # to_user = item.to_user if pad >= 2 else item.from_usre
                            #     deadline = item.deadline
                            # data = {
                            #     "wf_status": 2,  # back
                            #     "action": self.flow_config.get('flow_action'),
                            #     "flow_name": None,
                            #     "from_user": self.request.user,
                            #     "to_user": to_user,
                            #     "state": self.flow_config.get('flow_state_list')[self.state_index],
                            #     "duty": None,
                            #     "deadline": deadline,
                            #     "wf_description": "back in copy",
                            #     "belong_to_group": self.flow_config.get('flow_users_groups')[self.state_index],
                            #     "content_type": ContentType.objects.get_for_model(Quotation),
                            #     "object_id": new_quotation.id
                            # }
                            # back = WorkFlow.objects.create(**data)

                            new_quotation.quotation_self = self.object
                            new_quotation.extra_data.request = self.request
                            new_quotation.save()
                            # new_quotation.save_user(self.request)

                        qi.quotation = new_quotation
                        qi.save()

                    else:
                        """به مرحله بعد میرود"""
                        """یک wf به مرحله بعد ثبت میکند"""
                        flow_user_groups = self.flow_config.get('flow_users_groups', [])

            if self.state_index == 2 and ('submit/copy' in self.request.POST or 'next' in self.request.POST or 'submit/copy_q' in self.request.POST):
                """ثبت در سپیدار"""
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
                        'Description': qi.description or '',
                        'PriceInfoPercentDiscount': 0,
                        'PriceInfoDiscountRate': 0,
                        'AggregateAmountPercentDiscount': 0,
                        'AggregateAmountPriceDiscount': 0,
                        'AggregateAmountDiscountRate': 0,
                        'CustomerDiscount': 0,
                        'CustomerDiscountRate': 0,
                        'Discount': 0,
                       # 'DiscountParentRef': 1,  # optional
                        'Tax': qi.tax or 0,
                        'Duty': qi.duty or 0,
                        'Addition': self.object.addition if idx == 1 else 0,
                    }
                    quotation_items.append(qi_dict)
                #
                q = Quotation()
                quotation_data = {
                    'GUID': str(self.object.guid),
                    'CurrencyRef': self.object.sale_type.currency.sepidar_id or 1,
                    'Rate': self.object.sale_type.currency.current_rate() or 1,
                    'ExpirationDate': str(self.object.expiration_date),
                    'CustomerRef': self.object.customer_party_id.sepidar_party_id,  # 11
                    'SaleTypeRef': self.object.sale_type.pk,
                  #  'AddressRef': '1',  # optional
                    'DiscountOnCustomer': 0,
                    'Price': self.object.price or 1,
                    'Discount': self.object.self_discount or 0,
                    'Tax': self.object.tax_amount or 0,
                    'Duty': self.object.duty_amount or 0,
                    'Addition': 0, # self.object.addition or 0, TODO sepidar dont save addition for quotation(main form)
                    'items': quotation_items,
                }
                d = json.dumps(quotation_data)
                #
                api_res = APILogs.new_call(device=device, url=Urls.pos_quotations.url,
                                           method=Urls.pos_quotations.method, data=d)
                api_log_obj = api_res[2]
                api_log_obj.extra_data.request = self.request if api_log_obj else ''
                api_log_obj.save()

                self.object.sepidar_quotation_id = api_res[1].get('ID') if api_res[0] == 201 else None
                self.object.sepidar_number = api_res[1].get('Number') if api_res[0] == 201 else None
                self.object.save()
                if api_res[0] == 400:
                    print('rol back .... for status 400')
                    content_type = ContentType.objects.filter(model=self.object._meta.model_name,
                                                              app_label=self.object._meta.app_label).first()
                    flow_object = self.flow_model.objects.filter(object_id=self.object.id,
                                                                 content_type=content_type).last()
                    if flow_object:
                        flow_object.delete()
            if ((self.state_index == 0 and 'next' in self.request.POST) or (self.state_index == 2 and 'back' in self.request.POST)):
                ...
        except Exception as e:
            pass
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
        user_groups = self.request.user.groups.values_list('name', flat=True)
        if self.object:
            self.object.created_date = datetime2jalali(self.object.created_date).strftime('%y/%m/%d-%H:%M')
            self.object.last_update_date = datetime2jalali(self.object.last_update_date).strftime('%y/%m/%d-%H:%M')
        context['data'] = self.object
        context['app_name'] = self.request.resolver_match.app_name

        related_obj = getattr(self.object, f'{self.related_name_fk}', None)
        # context['detail_logs'] = []
        # if related_obj:
        #     for item in related_obj.all():
        #         context['detail_logs'].append(item.change_logs.all())
        # context['detail_logs'].reverse()
        if self.object:
            qis = self.object.quotation.all()
            counter = 0
            for qi in qis:
                if (self.state_index == 1 or self.state_index == 1) and (bool(qi.local_price_inquiry_done) != bool(qi.need_local_price_inquiry) or \
                        bool(qi.foreign_price_inquiry_done) != bool(qi.need_foreign_price_inquiry)):
                    counter += 1
                    context['allow_next'] = False
                    context['submit_copy_q'] = True
            if counter == len(qis):
                context['submit_copy_q'] = False
        if self.object and self.object.cancel:
            context['comment_form'] = CommentsForm(initial={'submit_type': 'uncanceled'})
        else:
            context['comment_form'] = CommentsForm(initial={'submit_type': 'cancel'})
        for f in context['formset']:
            if f.instance.comments.filter(comment_title__in=['L', 'M', 'N']):
                f.has_alt_code = True
        return context


def print_view(request,id=-1):
    customer_print = reverse("micmod_base:print_customer", args=[id])
    if request.META.get('PATH_INFO') == customer_print:
        template_name = 'micmod-base/quotation/view-print-raw.html'
    else:
        template_name = 'micmod-base/quotation/view-print.html'
    comments_url_params = '0'
    with_comments = '1'
    if request.GET.get('comments_url_params') == '1':
        with_comments = '1'
        comments_url_params = '0'
    elif request.GET.get('comments_url_params') == '0':
        with_comments = '0'
        comments_url_params = '1'
    # formset = inlineformset_factory(Quotation, QuotationItem, form=QuotationItemForm, extra=0, )
    formset = inlineformset_factory(Quotation, QuotationItem, form=QuotationItemForm2, extra=0, )
    greeting = {}
    greeting['heading'] = _("create")
    greeting['pageview'] = _("quotation")
    greeting['with_comments'] = with_comments
    greeting['comments_url_params'] = comments_url_params
    quotation = Quotation.objects.filter(id=id).first()
    greeting['form'] = QuotationForm(instance=quotation)
    greeting['formset'] = formset(instance=quotation,
                                  form_kwargs={
                                      "constraint": {
                                          "wf_access": True,
                                          'form_state': 0,
                                          'request': request,

                                      }
                                  }
                                  )
    if quotation:
        quotation.created_date = datetime2jalali(quotation.created_date).strftime('%y/%m/%d-%H:%M')
        quotation.last_update_date = datetime2jalali(quotation.last_update_date).strftime('%y/%m/%d-%H:%M')
    greeting['data'] = quotation
    return render(request, template_name, greeting)


class CurrencyExchangeView(LoginRequiredMixin, BaseView):
    model = CurrencyExchange
    form_class = CurrencyExchangeForm
    template_name = 'micmod-base/currency_exchange_list_or_create.html'
    success_url = reverse_lazy('micmod_base:currency_exchange')

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
                      reverse('micmod_base:currency_exchange', args=(obj.id,)),
                      obj.currency if obj.currency else '_'
                    )


class QuotationItemPending(LoginRequiredMixin, View):
    def get(self, request):
        q = self.request.GET.get('q')

        if q == 'local':
            quotations_record_lst = QuotationItem.objects.filter(Q(local_price_inquiry_done=True) &
                                         Q(need_local_price_inquiry=False) |
                                         Q(local_price_inquiry_done=False) &
                                         Q(need_local_price_inquiry=True)
                                         )
        elif q == 'foreign':
            quotations_record_lst = QuotationItem.objects.filter(Q(foreign_price_inquiry_done=True) &
                                         Q(need_foreign_price_inquiry=False) |
                                         Q(foreign_price_inquiry_done=False) &
                                         Q(need_foreign_price_inquiry=True))
        else:
            quotations_record_lst = QuotationItem.objects.filter(
                Q(local_price_inquiry_done=True) & Q(need_local_price_inquiry=False) |
                Q(local_price_inquiry_done=False) & Q(need_local_price_inquiry=True) |
                Q(foreign_price_inquiry_done=True) & Q(need_foreign_price_inquiry=False) |
                Q(foreign_price_inquiry_done=False) & Q(need_foreign_price_inquiry=True)
            )


        greeting = {}
        greeting['heading'] = _("quotation")
        greeting['pageview'] = _("micmod_base")
        # greeting['quotations'] = quotations_record
        greeting['quotationitems'] = quotations_record_lst

        return render(request,'micmod-base/quotation/pending_list.html',greeting)


class QuotationItemFormPending(LoginRequiredMixin, View):
    template_name = 'micmod-base/quotation/form_pending_list.html'
    form_struct = {
        'form': QuotationItemForm2,
        'childes': [
            {
                'form': InquiryResultForm,
                'childes': [{}]
            },
        ]
    }
    flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json', 'QuotationItemsFormPendingView')

    def get(self, request):
        from django.core.paginator import Paginator
        context = dict()
        context['heading'] = _("quotation")
        context['pageview'] = _("micmod_base")
        forms = list()
        form_list = list()

        quotation = request.GET.get('quotation')
        customer_code = request.GET.get('customer_code')
        my_quotations = request.GET.get('my_quotations')
        search_sku = request.GET.get('search_sku')

        if quotation:
            quotations_record_lst = Quotation.quotation_pending(self.request, filter={'pk': quotation})
        elif customer_code:
            quotations_record_lst = Quotation.quotation_pending(self.request, filter={'customer_code': customer_code})

        elif self.request.GET.get('choice') == 'my_quotations':
            quotations_record_lst = Quotation.quotation_pending(self.request, extra_filter={'my_quotations': True})
        elif search_sku:
            quotations_record_lst = Quotation.quotation_pending(self.request,
                                                                extra_filter={'goods_code': search_sku})
        elif self.request.GET.get('choice') == 'my_inquiry_not_started':
            quotations_record_lst = Quotation.quotation_pending(self.request,
                                                                extra_filter={'my_inquiry_not_started': True})
        elif self.request.GET.get('choice') == 'inquiry_not_assigned':
            quotations_record_lst = Quotation.quotation_pending(self.request,
                                                                extra_filter={'inquiry_not_assigned': True})

        else:
            quotations_record_lst = Quotation.quotation_pending(self.request)

        for qi_qs in quotations_record_lst:
            for qi in qi_qs:
                form = QuotationItemForm2(instance=qi, initial={
                    "constraint": {
                        "wf_access": True,
                        'form_state': 0,
                        'request': self.request,
                        'form_constraint': self.flow_config.get('flow_form_constraint'),
                        'formset_constraint': self.flow_config.get('flow_formset_constraint')
                    }
                })
                form.nested = InquiryResultForm(instance=qi.quotation_item_rel.first())
                form.enable = False
                forms.append(form)
            form_list.append(forms)
            forms = []

        paginator = Paginator(form_list, 10)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)
        context['page_obj'] = page_obj
        context['forms'] = form_list
        form_filter = PendingFormFilter()
        context['form_filter'] = form_filter
        return render(request, self.template_name, context)

    def post(self, request):
        if obj_pk := self.request.POST.get('obj_pk'):
            obj_qs = QuotationItem.objects.filter(pk=obj_pk)
            obj = obj_qs.first()
            obj.save_comment(self.request)

            new_goods_code = self.request.POST.get('goods_code')
            if new_goods_code and new_goods_code != obj.goods_code:
                obj.old_goods_code = obj.goods_code
                obj.goods_code = new_goods_code
                obj.old_goods_name = obj.goods_name
                obj.item_editor_user = self.request.user
                obj.save()

            if self.request.POST.get('foreign_price_inquiry_done'):
                obj.foreign_price_inquiry_done = True
                obj.save()
            if self.request.POST.get('local_price_inquiry_done'):
                obj.local_price_inquiry_done = True
                obj.save()

            data = {
                'lead_time': request.POST.get('lead_time'),
                'goods_code': request.POST.get('goods_code'),
                'goods_name': request.POST.get('goods_name'),
            }
            obj_qs.update(**data)

            iqr_obj = obj.quotation_item_rel.first()
            iqr_form = InquiryResultForm(self.request.POST, instance=iqr_obj)
            if iqr_form.is_valid():
                iqr_obj = iqr_form.save()
                iqr_obj.quotation_item = obj
                iqr_obj.save()
        redirect_path = self.request.META.get('HTTP_REFERER', None) or reverse('micmod_base:quotationitem.form.pending')
        return redirect(redirect_path)


class QuotationItemFormPending2(LoginRequiredMixin, View):
    template_name = 'micmod-base/quotation/form_pending_list2.html'
    form_struct = {
        'form': QuotationItemForm2,
        'childes': [
            {
                'form': InquiryResultForm,
                'childes': [{}]
            },
        ]
    }
    flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json', 'QuotationItemsFormPendingView')

    def get(self, request):
        from django.core.paginator import Paginator
        context = dict()
        context['heading'] = _("quotation")
        context['pageview'] = _("micmod_base")
        forms = list()

        quotation = request.GET.get('quotation')
        customer_code = request.GET.get('customer_code')
        my_quotations = request.GET.get('my_quotations')
        my_inquiry_not_started = request.GET.get('my_inquiry_not_started')
        inquiry_not_assigned = request.GET.get('inquiry_not_assigned')
        search_sku = request.GET.get('search_sku')
        force_inquiry = request.GET.get('force_inquiry')

        quotations_record_lst = QuotationItem.objects.none()

        if self.request.user.is_superuser:
            quotations_record_lst = QuotationItem.quotation_item_all_pending(inquiry_type=None, path=self.request.path)
        if 'trade' in self.request.user.base_group:
            quotations_record_lst = QuotationItem.quotation_item_all_pending(inquiry_type='trade', path=self.request.path)
        if 'bazar' in self.request.user.base_group:
            quotations_record_lst = QuotationItem.quotation_item_all_pending(inquiry_type='bazar', path=self.request.path)
        if quotation:
            quotations_record_lst = quotations_record_lst.filter(quotation=quotation)
        elif customer_code:
            quotations_record_lst = quotations_record_lst.filter(quotation__customer_code=customer_code)
        elif self.request.GET.get('choice') == 'my_quotations' or my_quotations:
            f = Q(assigned_trade_user=request.user) | Q(assigned_trade_user2=request.user)
            quotations_record_lst = quotations_record_lst.filter(f)
        elif search_sku:
            quotations_record_lst = quotations_record_lst.filter(goods_code=search_sku)
        elif self.request.GET.get('choice') == 'my_inquiry_not_started' or my_inquiry_not_started:
            f = (Q(assigned_trade_user=request.user) & Q(task_start=False)) | \
                (Q(assigned_trade_user2=request.user) & Q(task_start2=False))
            quotations_record_lst = quotations_record_lst.filter(f)
        elif self.request.GET.get('choice') == 'inquiry_not_assigned' or inquiry_not_assigned:
            f = Q(assigned_trade_user__isnull=True) & Q(assigned_trade_user2__isnull=True)
            quotations_record_lst = quotations_record_lst.filter(f)
        elif force_inquiry:
            f = {'quotation__force_inquiry': True}
            quotations_record_lst = quotations_record_lst.filter(**f)
        elif self.request.GET.get('item_in_china'):
            quotations_record_lst = quotations_record_lst.filter(item_in_china=True)
        else:
            quotations_record_lst = quotations_record_lst

        quotations_record_lst = quotations_record_lst.order_by('-quotation_id', 'id')

        paginator = Paginator(quotations_record_lst, 10)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        for qi in page_obj.object_list:
        #for qi in quotations_record_lst:
            form = QuotationItemForm2(instance=qi, initial={
                "constraint": {
                    "wf_access": True,
                    'form_state': 0,
                    'request': self.request,
                    'form_constraint': self.flow_config.get('flow_form_constraint'),
                    'formset_constraint': self.flow_config.get('flow_formset_constraint')
                }
            })
            form.nested = InquiryResultForm(instance=qi.quotation_item_rel.order_by('id').first())
            form.enable = False
            forms.append(form)

        #paginator = Paginator(forms, 10)
        #page_number = request.GET.get("page")
        #page_obj = paginator.get_page(page_number)

        d = dict()
        #for item in page_obj:
        for item in forms:
            if not d.get(item.instance.quotation.pk):
                d[item.instance.quotation.pk] = []
            d[item.instance.quotation.pk].append(item)

        per_page = page_obj.paginator.per_page
        context['page_obj'] = page_obj
        context['item_count'] = page_obj.number * per_page - (per_page - len(page_obj.object_list))
        context['forms'] = forms
        context['d'] = d
        context['zip_data'] = zip(page_obj, d)
        form_filter = PendingFormFilter()
        context['form_filter'] = form_filter
        return render(request, self.template_name, context)

    def post(self, request):
        if obj_pk := self.request.POST.get('obj_pk'):
            obj_qs = QuotationItem.objects.filter(pk=obj_pk)
            obj = obj_qs.first()
            obj.save_comment(self.request)

            new_goods_code = self.request.POST.get('goods_code')
            if new_goods_code and new_goods_code != obj.goods_code:
                obj.old_goods_code = obj.goods_code
                obj.goods_code = new_goods_code
                obj.old_goods_name = obj.goods_name
                obj.item_editor_user = self.request.user
                obj.extra_data.request = self.request
                obj.save()

            if self.request.POST.get('foreign_price_inquiry_done'):
                obj.foreign_price_inquiry_done = True
                obj.extra_data.request = self.request
                obj.save()
            elif self.request.POST.get('need_foreign_price_inquiry') and not self.request.POST.get('foreign_price_inquiry_done'):
                obj.foreign_price_inquiry_done = False
                obj.save()
            if self.request.POST.get('local_price_inquiry_done'):
                obj.local_price_inquiry_done = True
                obj.extra_data.request = self.request
                obj.save()
            elif self.request.POST.get('need_local_price_inquiry') and not self.request.POST.get('local_price_inquiry_done'):
                obj.local_price_inquiry_done = False
                obj.extra_data.request = self.request
                obj.save()


            data = {
                'lead_time': request.POST.get('lead_time') or obj.lead_time,
                'goods_code': request.POST.get('goods_code'),
                'goods_name': request.POST.get('goods_name'),
                'has_delay': True if request.POST.get('has_delay') else False or obj.has_delay,
                'delay_reason': request.POST.get('delay_reason') or obj.delay_reason,
                'delay_time': request.POST.get('delay_time') or obj.delay_time,
            }
            obj_qs.update(**data)

            iqr_obj = obj.quotation_item_rel.first()
            iqr_form = InquiryResultForm(self.request.POST, instance=iqr_obj)
            if iqr_form.is_valid():
                iqr_obj = iqr_form.save()
                iqr_obj.quotation_item = obj
                iqr_obj.extra_data.request = self.request
                iqr_obj.save()
        redirect_path = self.request.META.get('HTTP_REFERER', None) or reverse('micmod_base:quotationitem.form.pending')
        return redirect(redirect_path)


class MyQuotationItemFormPendingToday(LoginRequiredMixin, View):
    template_name = 'micmod-base/quotation/form_pending_list.html'
    form_struct = {
        'form': QuotationItemForm2,
        'childes': [
            {
                'form': InquiryResultForm,
                'childes': [{}]
            },
        ]
    }
    flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json',
                                       'QuotationItemsFormPendingView')

    def get(self, request):
        from django.core.paginator import Paginator
        context = dict()
        context['heading'] = _("quotation")
        context['pageview'] = _("micmod_base")
        forms = list()
        form_list = list()

        quotation = request.GET.get('quotation')
        customer_code = request.GET.get('customer_code')
        my_quotations = request.GET.get('my_quotations')
        search_sku = request.GET.get('search_sku')

        if quotation:
            quotations_record_lst = Quotation.quotation_pending(self.request, filter={'pk': quotation})
        elif customer_code:
            quotations_record_lst = Quotation.quotation_pending(self.request, filter={'customer_code': customer_code})

        elif self.request.GET.get('choice') == 'my_quotations':
            quotations_record_lst = Quotation.quotation_pending(self.request, extra_filter={'my_quotations': True})
        elif search_sku:
            quotations_record_lst = Quotation.quotation_pending(self.request,
                                                                extra_filter={'goods_code': search_sku})
        elif self.request.GET.get('choice') == 'my_inquiry_not_started':
            quotations_record_lst = Quotation.quotation_pending(self.request,
                                                                extra_filter={'my_inquiry_not_started': True})
        # elif 'goods_code and my_quotations':
        #     quotations_record_lst = Quotation.quotation_pending(self.request,
        #                                                         extra_filter={'goods_code': search_sku, "my_quotations": True})
        # elif from_time and to_time:
        #     quotations_record_lst = Quotation.quotation_pending(self.request, filter={'created_date__gte': from_time, 'created_date__lte': to_time})
        else:
            quotations_record_lst = Quotation.quotation_pending(self.request)

        for qi_qs in quotations_record_lst:
            for qi in qi_qs:
                form = QuotationItemForm2(instance=qi, initial={
                    "constraint": {
                        "wf_access": True,
                        'form_state': 0,
                        'request': self.request,
                        'form_constraint': self.flow_config.get('flow_form_constraint'),
                        'formset_constraint': self.flow_config.get('flow_formset_constraint')
                    }
                })
                form.nested = InquiryResultForm(instance=qi.quotation_item_rel.first())
                form.enable = False
                forms.append(form)
            form_list.append(forms)
            forms = []

        paginator = Paginator(form_list, 10)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)
        context['page_obj'] = page_obj
        context['forms'] = form_list
        form_filter = PendingFormFilter()
        context['form_filter'] = form_filter
        # t2 = time.time()
        # print(t2 - t1)
        # print('yyyyyyyyyyyyyyy')
        return render(request, self.template_name, context)

    def post(self, request):
        if obj_pk := self.request.POST.get('obj_pk'):
            obj_qs = QuotationItem.objects.filter(pk=obj_pk)
            obj = obj_qs.first()
            obj.save_comment(self.request)

            new_goods_code = self.request.POST.get('goods_code')
            if new_goods_code and new_goods_code != obj.goods_code:
                obj.old_goods_code = obj.goods_code
                obj.goods_code = new_goods_code
                obj.old_goods_name = obj.goods_name
                obj.item_editor_user = self.request.user
                obj.save()

            if self.request.POST.get('foreign_price_inquiry_done'):
                obj.foreign_price_inquiry_done = True
                obj.save()
            if self.request.POST.get('local_price_inquiry_done'):
                obj.local_price_inquiry_done = True
                obj.save()

            data = {
                'lead_time': request.POST.get('lead_time'),
                'goods_code': request.POST.get('goods_code'),
                'goods_name': request.POST.get('goods_name'),
            }
            obj_qs.update(**data)

            iqr_obj = obj.quotation_item_rel.first()
            iqr_form = InquiryResultForm(self.request.POST, instance=iqr_obj)
            if iqr_form.is_valid():
                iqr_obj = iqr_form.save()
                iqr_obj.quotation_item = obj
                iqr_obj.save()
        redirect_path = self.request.META.get('HTTP_REFERER', None) or reverse('micmod_base:quotationitem.form.pending')
        return redirect(redirect_path)

def get_sku(request):
    sku = request.GET.get('sku')
    sku_qs = Item.objects.filter(sku=sku).first()
    if sku_qs:
        return JsonResponse({'res': sku_qs.sku, 'id': sku_qs.pk, 'part_number': sku_qs.part_number})
    else:
        return JsonResponse({})


class QuotationListDatatable(AjaxDatatableView):
    model = Quotation
    title = 'currency_list'
    initial_order = [["pk", "desc"], ]
    length_menu = [[6, 10, 15, -1], [6, 10, 15, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'pk', 'visible': True, 'title': _('code'), 'className': 'py-1 border currency-search'},
        {'name': 'id', 'visible': False, },
        {'name': 'title', 'visible': True, 'title': _('title'), 'className': 'py-1 border', 'lookup_field': '__icontains', 'searchable': False},
        {'name': 'customer_party_id', 'visible': True, 'title': _('customer_name'), 'className': 'py-1 border', 'orderable': False, 'lookup_field': '__title__icontains'},
        {'name': 'created_date', 'visible': True, 'orderable': True, 'searchable': False},
        {'name': 'expiration_date', 'visible': True, 'orderable': True, 'searchable': False},
        {'name': 'creator_user', 'visible': True, 'orderable': True, 'lookup_field': '__profile__first_name__icontains'},
        {'name': 'description', 'visible': True, 'orderable': True, 'searchable': False},
        {'name': 'inquiry_status', 'visible': True, 'orderable': False, 'searchable': False},
        # {'name': 'quotation_state', 'visible': True, 'orderable': False, 'searchable': False},
        {'name': 'last_work_flow', 'visible': True, 'orderable': True, 'lookup_field': '__current_state_name__icontains'},
        {'name': 'sepidar_number', 'visible': True, 'orderable': True},
        {'name': 'cancel', 'visible': True, 'orderable': True},
    ]

    def get_initial_queryset(self, request=None):
        if request.user.base_group == 'trade':
            qs = Quotation.objects.filter(cancel=True, is_deleted=False)
        else:
            qs = Quotation.get_qs(request)
        # qs = qs.annotate(quotation_state=Cast('quotation', CharField()))
        qs = self.model.objects.filter(pk__in=[i.pk for i in qs])
        return qs

    # @timer
    def customize_row(self, row, obj):

        row['customer_party_id'] = '<a class="fw-bold" href="%s" target="_blank">%s</a>' % (
            reverse('micmod_base:quotations.view', args=(obj.id,)),
            obj.customer_party_id.title if obj.customer_party_id else '-'
        )

        counter = obj.get_inquiry_result_count

        local_color_condition = counter[1] == counter[2] and counter[1] != 0
        foreign_color_condition = counter[3] == counter[4] and counter[3] != 0
        out = f'''<span> کل: {counter[0]} </span > <br>''' \
              + f'''<p {'class="bg-success rounded mb-1"' if local_color_condition else 'class="mb-1"'}>
              داخلی
              {counter[1]} /  {counter[2]} </p>''' \
              + f''' <p {'class="bg-success rounded mb-1"' if foreign_color_condition else 'class="mb-1"'}>
              خارجی
              {counter[3]} / {counter[4]} </p> '''
        row['inquiry_status'] = out

        row['title'] = '<a class="fw-bold" href="%s" target="_blank">%s</a>' % (
            reverse('micmod_base:quotations.view', args=(obj.id,)),
            obj.title if obj.title else '_'
        )
        # row['quotation_state'] = '%s' % obj.get_inquiry_state
        row['created_date'] = '%s' % to_jalali_date(obj.created_date)
        row['expiration_date'] = '%s' % to_jalali_date(obj.created_date)
        cancel_obj = obj.comments.filter(~Q(comment_title='O')).last()
        if obj.cancel:
            row['cancel'] = f'''<span class="text-danger">{cancel_obj.get_comment_title_display() if cancel_obj else 'cancel'} </span><span>{cancel_obj.comment_content if cancel_obj else 'علت کنسلی نیاز به بررسی دارد!!!' }</span>'''
        else:
            row['cancel'] = '-'


def inquiry_report(request):
    from .models import QuotationItem
    inquiry_report_call = QuotationItem.get_inquiry_report()
    res = render_to_string('micmod-base/quotation/partial/inquiry_report_filter.html', context={'quotationitem_filters':inquiry_report_call})
    return JsonResponse({'res': res}, safe=False)
