import json

from django.template.loader import render_to_string
from django.db.models import Q, QuerySet, CharField, Count, Sum
from django.db.models.functions import Cast
from django.utils import timezone
from jalali_date.templatetags.jalali_tags import to_jalali

from comments.forms import CommentsForm
from extra_data.models import Item
from sepidar.models import APILogs
from sepidar.models import Dl, Device
from sepidar.scripts.sepidar_classes import Urls
import uuid
from ajax_datatable import AjaxDatatableView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.forms import inlineformset_factory
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.conf import settings
from jalali_date import datetime2jalali

from changelog.models import ChangeLog
from inquiry.forms import InquiryResultForm
from micmod_base.base import CurrencyExchange
from micmod_base.forms import QuotationForm, QuotationItemForm2, CurrencyExchangeForm, QuotationItemFormset, QuotationItemFormset, InquiryResultFormset, TimeForm
from sepidar.models import Dl
from tools.import_data import import_customers_from_sepidar
from tools.utils import show_error, to_jalali_date
from translator import get_text as _
from django.views import View

from micmod_base.models import Quotation, QuotationItem
from core.views import BaseView, Base
from django.contrib.contenttypes.models import ContentType

from workflow.forms import WorkFlowModelForm
from .forms import PendingFormFilter
from django.urls import reverse
import re

class QuotationsList(LoginRequiredMixin,View):
    def get(self, request):
        q = self.request.GET.get('q')
        greeting = {}
        greeting['heading'] = _("quotation")
        greeting['pageview'] = _("micmod_base")
        greeting['time_form'] = TimeForm()
        # greeting['quotations'] = quotations_record
        # greeting['quotations'] = quotations_record_lst
        return render(request,'micmod-base/quotation/list_datatable.html',greeting)


class QuotationsView(LoginRequiredMixin, BaseView):
    template_name = 'micmod-base/quotation/view.html'
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
        if 'duplicate' in self.request.POST:
            obj = duplicate_quotation(self.request, self.object.pk)
            if obj:
                return HttpResponseRedirect(reverse('micmod_base:quotations.view', kwargs={'pk': obj.pk}))
        if self.object is None:
            import_customers_from_sepidar(extra_data={"creator_user_id": 1, "editor_user_id": 1})
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        """ run import customer from sepidar before object create"""
        if self.object is None:
            import_customers_from_sepidar(extra_data={"creator_user_id": 1, "editor_user_id": 1})

        res = super().form_valid(form)
        if 'back' in self.request.POST or 'change_user' in self.request.POST:
            return res
        if not self.object.is_official and not self.request.POST.get('official_value'):
            self.object.official_value = 0

        new_quotation = None
        try:

            device = Device.objects.all().first()
            if not self.object.guid:
                self.object.guid = uuid.uuid4()
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
                        'ItemRef': qi.goods_code_fk.sepidar_id_0,  # itemid,  # optional
                        'StockRef': 2,  # optional
                        'Quantity': qi.quantity,
                        'SecondaryQuantity': 0,
                        # 'Fee': qi.fee or 1,
                        'Fee': qi.sepidar_fee or 1,
                        'Price': qi.net_price or 1,
                        'Description': qi.description or '',
                        'PriceInfoPercentDiscount': 0,
                        'PriceInfoDiscountRate': 0,
                        'AggregateAmountPercentDiscount': 0,
                        'AggregateAmountPriceDiscount': 0,
                        'AggregateAmountDiscountRate': 0,
                        'CustomerDiscount': 0,
                        'CustomerDiscountRate': 0,
                        'Discount': qi.discount_value or 0, #qi.sepidar_discount * qi.quantity or 0,
                       # 'DiscountParentRef': 1,  # optional
                        'Tax': qi.tax or 0,
                        'Duty': qi.duty or 0,
                        'Addition': self.object.addition if (idx == 1 and self.object.addition) else  0,
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
                    'Discount': self.object.total_discount or 0, #self_discount or 0,
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
                # self.object.save()
                if api_res[0] >= 400:
                    print('rol back .... for status 400')
                    content_type = ContentType.objects.filter(model=self.object._meta.model_name,
                                                              app_label=self.object._meta.app_label).first()
                    flow_object = self.flow_model.objects.filter(object_id=self.object.id,
                                                                 content_type=content_type).last()
                    if flow_object:
                        flow_object.is_deleted = True
                        flow_object.save()
            if ((self.state_index == 0 and 'next' in self.request.POST) or (self.state_index == 2 and 'back' in self.request.POST)):
                ...
            self.object.save()
        except Exception as e:
            pass
            print('rol back ....')
            content_type = ContentType.objects.filter(model=self.object._meta.model_name, app_label=self.object._meta.app_label).first()
            flow_object = self.flow_model.objects.filter(object_id=self.object.id, content_type=content_type).last()
            if flow_object:
                flow_object.is_deleted = True
                flow_object.save()
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
        context['duplicate'] = True

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
    with_alt_code = '0'
    alt_code = '1'
    if request.GET.get('comments_url_params') == '1':
        with_comments = '1'
        comments_url_params = '0'
    elif request.GET.get('comments_url_params') == '0':
        with_comments = '0'
        comments_url_params = '1'
    if request.GET.get('alt_code') == '1':
        with_alt_code = '1'
        alt_code = '0'
    elif request.GET.get('alt_code') == '0':
        with_alt_code = '0'
        alt_code = '1'

    formset = inlineformset_factory(Quotation, QuotationItem, form=QuotationItemForm2, extra=0, )
    greeting = {}
    greeting['alt_code_html'] = []
    greeting['heading'] = _("create")
    greeting['pageview'] = _("quotation")
    greeting['with_comments'] = with_comments
    greeting['comments_url_params'] = comments_url_params
    greeting['with_alt_code'] = with_alt_code
    greeting['alt_code'] = alt_code
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
    for f in greeting['formset']:
        f.alt_codes_html = []
        if alt_qs := f.instance.comments.filter(comment_title__in=['L', 'M', 'N']):
            for alt_comment in alt_qs:
                comment_str_lower = alt_comment.comment_content.lower()
                pattern_pk = r'sku_(\d+)'
                pks = re.findall(pattern_pk, comment_str_lower)
                sku_item = Item.objects.filter(pk__in=pks).first()
                try:
                    if sku_item:
                        item = dict()
                        item['obj'] = sku_item
                        item['quotation'] = f.instance.quotation
                        price_inquiry_result = sku_item.price if sku_item else None
                        price_inquiry_result_bazar = sku_item.bazar_price if sku_item else None
                        id_currency_ref = f.instance.quotation.currency_ref.pk
                        id_customer_grade = f.instance.quotation.customer_grade
                        id_customer_grade = id_customer_grade.split(',')[-1] if id_customer_grade else None
                        id_payment_method = f.instance.quotation.payment_method
                        id_payment_method = id_payment_method.split(',')[-1] if id_payment_method else None
                        quantity = f.instance.quantity
                        if price_inquiry_result:
                            price_setting = price_inquiry_result.price_settings
                            price_inquiry_result.set_discount_params(
                                quantity=quantity,
                                customer_grade=id_customer_grade,
                                payment_method=id_payment_method,
                                currency=id_currency_ref,
                                price_setting=price_setting
                            )
                            item["price_settings"] = price_setting.pk
                            if str(id_currency_ref) == str(1):  # rial
                                item["rial_final_price"] = price_inquiry_result.rial_final_price
                                item["rial_final_price_new_order"] = price_inquiry_result.rial_final_price_new_order
                            elif str(id_currency_ref) == str(2):  # rmb
                                item['rmb_final_price'] = price_inquiry_result.rmb_final_price
                            item["price_update_date"] = to_jalali(price_inquiry_result.price_update_date, "%Y-%m-%d")
                        else:
                            item["rial_final_price"] = {'express': None, 'air': None, 'sea': None}
                            item["rial_final_price_new_order"] = {'express': None, 'air': None, 'sea': None}

                        if price_inquiry_result_bazar:
                            price_setting = price_inquiry_result_bazar.price_settings
                            price_inquiry_result_bazar.set_discount_params(
                                quantity=quantity,
                                customer_grade=id_customer_grade,
                                payment_method=id_payment_method,
                                currency=id_currency_ref,
                                price_setting=price_setting
                            )
                            item["goods_price_market"] = price_inquiry_result_bazar.bazar_price
                            item["goods_market_date"] = to_jalali(price_inquiry_result_bazar.price_update_date, "%Y-%m-%d")
                        else:
                            item["goods_price_market"] = None
                            item["goods_market_date"] = None
                        # render html
                        html = render_to_string('micmod-base/quotation/partial/alt_code_print.html', context=item)
                        f.alt_codes_html.append(html)
                except Exception as e:
                    show_error(e, __file__)
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
        filter_form = PendingFormFilter(self.request.GET)
        filter_form.is_valid()
        context = dict()
        context['heading'] = _("quotation")
        context['pageview'] = _("micmod_base")
        forms = list()

        quotation = request.GET.get('quotation')
        customer_code = request.GET.get('customer_code')
        customer_name = request.GET.get('customer_name')
        my_quotations = request.GET.get('my_quotations')
        my_inquiry_not_started = request.GET.get('my_inquiry_not_started')
        inquiry_not_assigned = request.GET.get('inquiry_not_assigned')
        search_sku = request.GET.get('search_sku')
        search_part_number = request.GET.get('search_part_number')
        force_inquiry = request.GET.get('force_inquiry')
        time_range = request.GET.get('time_range')
        from_time = self.request.GET.get('from_time')
        to_time = self.request.GET.get('to_time')

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

        elif self.request.GET.get('from_time') or self.request.GET.get('to_time'):
            quotations_record_lst = quotations_record_lst.filter(quotation__created_date__range=[filter_form.cleaned_data.get('from_time'),filter_form.cleaned_data.get('to_time')])
        elif self.request.GET.get('choice') == 'search_part_number' or search_part_number:
            quotations_record_lst = quotations_record_lst.filter(goods_code_fk__part_number__icontains=search_part_number)
        elif self.request.GET.get('choice') == 'customer_name' or customer_name:
            customer_filter = (Q(quotation__customer_party_id__title__icontains=customer_name) |
                               Q(quotation__customer_party_id__name__icontains=customer_name) |
                               Q(quotation__customer_party_id__last_name__icontains=customer_name))
            quotations_record_lst = quotations_record_lst.filter(customer_filter)
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

        d = dict()
        for item in forms:
            if not d.get(item.instance.quotation.pk):
                d[item.instance.quotation.pk] = []
            repeated_goods_code = quotations_record_lst.filter(goods_code_fk=item.instance.goods_code_fk).aggregate(Sum('quantity'), Count('id'))
            count = repeated_goods_code.get('id__count')
            if count > 1:
                html = f"""<div class="mt-3 py-2 px-1 rounded hover_light_primary"><a href="/micmod_base/quotationitem/list/form/pending/?choice=search_sku&search_sku={item.instance.goods_code_fk}">
                <span class="">{count}</span> 
                <span class="me-3"> درخواست تکراری</span>
                <span> جمع کل </span>
                :
                <span>{repeated_goods_code.get('quantity__sum')}<span>
                </a></div>"""
                item.repeated_goods_code_count = html
            d[item.instance.quotation.pk].append(item)

        inquiry = QuotationItem.inquiry_not_started(request.user)
        # my_inquiry_not_started = inquiry[0]
        # inquiry_not_started_count = inquiry[1]

        per_page = page_obj.paginator.per_page
        context['page_obj'] = page_obj
        context['item_count'] = page_obj.number * per_page - (per_page - len(page_obj.object_list))
        context['forms'] = forms
        context['d'] = d
        context['zip_data'] = zip(page_obj, d)
        form_filter = PendingFormFilter()
        context['form_filter'] = form_filter
        context['app_name'] = self.request.resolver_match.app_name
        # context['my_inquiry_not_started'] = my_inquiry_not_started
        # context['inquiry_not_started_count'] = inquiry_not_started_count
        return render(request, self.template_name, context)

    def post(self, request):
        if obj_pk := self.request.POST.get('obj_pk'):
            obj_qs = QuotationItem.objects.full_queryset(pk=obj_pk)
            obj = obj_qs.first()
            obj.save_comment(self.request)

            new_goods_code = self.request.POST.get('goods_code')
            if new_goods_code and new_goods_code != obj.goods_code:
                obj.old_goods_code = obj.goods_code
                obj.goods_code = new_goods_code
                obj.old_goods_name = obj.goods_name
                obj.goods_code_fk = Item.objects.filter(sku=new_goods_code).first()

                from sepidar.models import Item as sepidar_item
                items = sepidar_item.get_item(new_goods_code)
                for item_ in items:
                    try:
                        obj.itemid = item_.itemid
                        obj.stock_amount = item_.stock_qty
                        obj.stock_amount_res = item_.stock_res_qty
                    except Exception as e:
                        pass
                obj.item_editor_user = self.request.user
                obj.extra_data.request = self.request
                obj.save()

            if self.request.POST.get('foreign_price_inquiry_done'):
                obj.foreign_price_inquiry_done = True
                obj.extra_data.request = self.request
                obj.save()
            elif obj.need_foreign_price_inquiry and not self.request.POST.get('foreign_price_inquiry_done'):
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

            if self.request.user.base_group == 'trade':
                data = {
                    'lead_time': request.POST.get('lead_time') or obj.lead_time,
                    'goods_code': request.POST.get('goods_code'),
                    'goods_name': request.POST.get('goods_name'),
                    'has_delay': True if request.POST.get('has_delay') else False,
                    'delay_reason': request.POST.get('delay_reason') or '',
                    'delay_time': request.POST.get('delay_time') or '',
                }
                obj_for_update = obj_qs.first()
                if obj_for_update:
                    obj_for_update.lead_time = data['lead_time']
                    obj_for_update.goods_code = data['goods_code']
                    obj_for_update.goods_name = data['goods_name']
                    obj_for_update.has_delay = data['has_delay']
                    obj_for_update.delay_reason = data['delay_reason']
                    obj_for_update.delay_time = data['delay_time']
                    obj_for_update.extra_data.request = self.request
                    obj_for_update.save()

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
        {'name': 'last_work_flow__to_user', 'title': 'متعلق به', 'visible': True, 'orderable': True, 'lookup_field': '__profile__first_name__icontains'},
        {'name': 'description', 'visible': True, 'orderable': True, 'searchable': False},
        {'name': 'inquiry_status', 'title': 'وضعیت استعلام', 'visible': True, 'orderable': False, 'searchable': False},
        # {'name': 'quotation_state', 'visible': True, 'orderable': False, 'searchable': False},
        {'name': 'last_work_flow','title': 'آخرین وضعیت', 'visible': True, 'orderable': True, 'lookup_field': '__current_state_name__icontains'},
        {'name': 'sepidar_number', 'visible': True, 'orderable': True},
        {'name': 'cancel', 'visible': True, 'orderable': True},
        {'name': 'comment', 'visible': True, 'title': '<div class="px-10">نظرات</div>', 'searchable': False}
    ]

    def get_initial_queryset(self, request=None):
        if request.user.base_group == 'trade':
            qs = Quotation.objects.filter(cancel=True, is_deleted=False,
                                          quotation__need_foreign_price_inquiry=True,
                                          quotation__foreign_price_inquiry_done=True)
        else:
            qs = Quotation.get_qs(request)
        qs = self.model.objects.filter(pk__in=[i.pk for i in qs])
        return qs

    # @timer
    def customize_row(self, row, obj):
        qi_comments = [x.comments.all() for x in obj.quotation.all()]
        c = 0
        for qs in qi_comments:
            for comment in qs:
                if not comment.commentseen_set.all():
                    c += 1
        for comment in obj.comments.all():
            if not comment.commentseen_set.all():
                c += 1
        if c > 0:
            row['comment'] = f'<span class="bg-success rounded px-2">{c} کامنت جدید</span>'
        else:
            row['comment'] = f'{c} کامنت جدید'

        row['last_work_flow__to_user'] = obj.last_work_flow.to_user.profile.first_name if obj.last_work_flow else ''
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
        row['created_date'] = '%s' % to_jalali_date(obj.created_date)
        row['expiration_date'] = '%s' % to_jalali_date(obj.expiration_date)
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


def repeated_goods_code_view(request):
    base_group = request.user.base_group
    qi = QuotationItem.quotation_item_all_pending(base_group)
    repeated_goods_code_qi = qi.order_by('goods_code_fk_id').values('goods_code').annotate(goods_code_count=Count('goods_code')).filter(
        goods_code_count__gt=1)
    repeated_goods_code = repeated_goods_code_qi.values_list('goods_code', 'goods_code_count')
    repeated_codes = list(repeated_goods_code)
    res = render_to_string('micmod-base/quotation/partial/repeated_goods_code.html',
                           context={'repeated_goods_code': repeated_codes})
    return JsonResponse({'res': res}, safe=False)


def save_parent_item(request):
    import json
    data = json.loads(request.body)
    item_sku = data.get('item')
    parent_sku = data.get('parent')

    item = Item.objects.filter(sku=item_sku).first()
    parent_item = Item.objects.filter(sku=parent_sku).first()

    if request.method == 'DELETE' and item:
        item.parent = None
        item.save()
        return JsonResponse({'res': 'delete'}, status=200)

    if item and parent_item:
        item.parent = parent_item
        item.save()
        return JsonResponse({'res': 'ok'})
    return JsonResponse({'res': 'کد نامعتبر'}, status=400)


def sale_user_report(request):
    from .models import Quotation
    wf_states = ['پیش فاکتور اولیه', 'استعلام قیمت', 'تایید پیش فاکتور', 'تایید مشتری', 'تایید کارشناس', 'مرحله نهایی']
    from_date = request.GET.get('from_time')
    to_date = request.GET.get('to_time')
    sale_user_report_call = Quotation.sale_user_report(request.user, wf_states, from_date, to_date)
    res = render_to_string('micmod-base/quotation/partial/sale_user_report.html',
                           context={'sale_user_report_call': sale_user_report_call, 'wf_states': wf_states,
                                    'from_date': from_date, 'to_date': to_date})
    return JsonResponse({'res': res}, safe=False)

  
def inquiry_not_started(request):
    trade_user = request.user
    inquiry = QuotationItem.inquiry_not_started(trade_user)
    res = {'my_inquiry_not_started': inquiry[0],
           'inquiry_not_started_count': inquiry[1],
           'item_in_china': inquiry[2],
           'new_inquiry': inquiry[3]
           }

    return JsonResponse(res)


from django.db import transaction


def duplicate_quotation(request, quotation_id):
    with transaction.atomic():
        # Get the original quotation
        quotation = Quotation.objects.get(pk=quotation_id)

        wf_initial = {
            'wf_access': True,
            'from_user': None,
            'to_user': request.user,
            'state': 'پیش فاکتور اولیه',
            'state_index': 0,
            'belong_to_group': 'sales_user',
            'action': 'create',
            'deadline': None,
            'flow_config': Base.get_flow_config(settings.BASE_DIR/'_keenthemes/view_config.json', 'QuotationsView'),
            'create': True
        }
        wfform = WorkFlowModelForm(data=request.POST, initial=wf_initial, content_type_model=Quotation,
                                   current_user=request.user)
        if wfform.is_valid():
            quotation.pk = None
            quotation.guid = uuid.uuid4()
            quotation.sepidar_number = None
            quotation.sepidar_quotation_id = None


            wf_obj = wfform.save()
            wf_obj.from_user = request.user
            wf_obj.to_user = request.user

            wf_obj.content_type = ContentType.objects.filter(app_label=quotation._meta.app_label,
                                                             model=quotation._meta.model_name).first()
            wf_obj.wf_status = 5  # first draft
            wf_obj.extra_data.request = request
            wf_obj.current_state_name = 'پیش فاکتور اولیه'
            wf_obj.save()

            # Duplicate the quotation
            quotation.last_work_flow = wf_obj

            quotation.extra_data.request = request
            quotation.save()
            wf_obj.object_id = quotation.pk
            wf_obj.save()


            # Duplicate each related QuotationItem
            quotation_items = QuotationItem.objects.filter(quotation=quotation_id)
            for item in quotation_items:
                item.pk = None  # Create a new record
                item.quotation = quotation  # Assign the new quotation
                item.extra_data.request = request
                item.save()

        return quotation
