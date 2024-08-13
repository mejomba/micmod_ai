from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from jalali_date import datetime2jalali

from comments.forms import CommentsForm
from core.views import BaseView, Base
from extra_data.models import Customer
from factor.forms import FactorModelForm, FactorItemFormset
from factor.models import Factor
from micmod_base.models import Quotation
from tools.import_data import import_customers_from_sepidar


class FactorView(LoginRequiredMixin, BaseView):
    template_name = 'micmod-base/factor/factor.html'
    form_class = FactorModelForm
    model = Factor
    wf_last_step_is_open = True
    has_flow = True
    form_struct = {
        'form': FactorModelForm,
        'childes': [
            {
                'form': FactorItemFormset,
                'childes': [{}]
            },
        ]
    }
    flow_config = Base.get_flow_config(settings.BASE_DIR/'_keenthemes/view_config.json', 'QuotationsView')

    # has_formset = True
    # formset_form = QuotationItemForm2
    # formset_model = QuotationItem
    formset_fk_field = 'quotation'
    related_name_fk = 'quotation'

    def get_success_url(self):
        return reverse_lazy('micmod_base:quotations.view', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        if self.object is None:
            pass
            # import_customers_from_sepidar(extra_data={"creator_user_id": 1, "editor_user_id": 1})
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        # if 'submit_duplicate' in self.request.POST:
        #     return self.duplicate(self.object, [], ['quotation'])
        """ run import customer from sepidar before object create"""
        if self.object is None:
            pass
            # import_customers_from_sepidar(extra_data={"creator_user_id": 1, "editor_user_id": 1})

        res = super().form_valid(form)

        # new_quotation = None
        # try:
        #
        #     device = Device.objects.all().first()
        #     if not self.object.guid:
        #         self.object.guid = uuid.uuid4()
        #         # self.object.save()
        #     elif (sepidar_pk := self.object.sepidar_quotation_id) and self.state_index == 2 and 'next' in self.request.POST:
        #         APILogs.new_call(device=device, url=Urls.del_quotation.url.format(sepidar_pk),
        #                          method=Urls.del_quotation.method, save=True)
        #
        #     if (self.state_index == 1 or self.state_index == 1) and 'submit/copy_q' in self.request.POST:
        #         flow_copy = False
        #
        #         """copy quotation"""
        #         for qi in self.object.quotation.all():
        #             if bool(qi.local_price_inquiry_done) != bool(qi.need_local_price_inquiry) or \
        #                     bool(qi.foreign_price_inquiry_done) != bool(qi.need_foreign_price_inquiry):
        #                 """مجاز نیستن برن مرحله بعد"""
        #                 """create new quotation"""
        #                 quotation_data = dict()
        #                 pop_quotation_item = ['id', 'guid', 'created_date', 'last_update_date', 'creator_user',
        #                                       'editor_user']
        #                 for field in self.model._meta.fields:
        #                     quotation_data[field.name] = getattr(self.object, field.name, None)
        #                 [quotation_data.pop(k) for k in pop_quotation_item]
        #
        #                 quotation_data['quotation_self'] = self.object
        #                 quotation_data['guid'] = uuid.uuid4()
        #                 if not new_quotation:
        #                     new_quotation = self.model.objects.create(**quotation_data)
        #
        #                     """تمام change log ها کپی بشن (فقط یک بار)"""
        #                     logs = ChangeLog.get_log(self.object)
        #                     for log in logs:
        #                         log.pk = None
        #                         log.content_type = ContentType.objects.get_for_model(Quotation)
        #                         log.object_id = new_quotation.pk
        #                         log.save()
        #
        #                     """تمام wf ها کپی بشن (فقط یک بار)"""
        #                     if not flow_copy:
        #                         flows = self.get_flow(self.object)
        #                         for idx, flow in enumerate(flows):
        #                             if idx == len(flows) - 1:
        #                                 break
        #                             flow.pk = None
        #                             flow.object_id = new_quotation.pk
        #                             flow.save()
        #                             flow_copy = True
        #                             new_quotation.last_work_flow = flow
        #
        #                     """ این آیتم در مرحله استعلام می ماند و wf ثبت نمیکند """
        #                     # """ این آیتم به مرحله قبل میرود و wf برگشت ثبت میکند """
        #
        #                     new_quotation.quotation_self = self.object
        #                     new_quotation.extra_data.request = self.request
        #                     new_quotation.save()
        #                     # new_quotation.save_user(self.request)
        #
        #                 qi.quotation = new_quotation
        #                 qi.save()
        #
        #             else:
        #                 """به مرحله بعد میرود"""
        #                 """یک wf به مرحله بعد ثبت میکند"""
        #                 flow_user_groups = self.flow_config.get('flow_users_groups', [])
        #
        #     if self.state_index == 2 and ('submit/copy' in self.request.POST or 'next' in self.request.POST or 'submit/copy_q' in self.request.POST):
        #         """ثبت در سپیدار"""
        #         quotation_items = []
        #         for idx, qi in enumerate(self.object.quotation.all(), 1):
        #             qi_dict = {
        #                 'RowID': idx,
        #                 'ItemRef': qi.goods_code_fk.sepidar_id_0,  # itemid,  # optional
        #                 'StockRef': 2,  # optional
        #                 'Quantity': qi.quantity,
        #                 'SecondaryQuantity': 0,
        #                 # 'Fee': qi.fee or 1,
        #                 'Fee': qi.sepidar_fee or 1,
        #                 'Price': qi.net_price or 1,
        #                 'Description': qi.description or '',
        #                 'PriceInfoPercentDiscount': 0,
        #                 'PriceInfoDiscountRate': 0,
        #                 'AggregateAmountPercentDiscount': 0,
        #                 'AggregateAmountPriceDiscount': 0,
        #                 'AggregateAmountDiscountRate': 0,
        #                 'CustomerDiscount': 0,
        #                 'CustomerDiscountRate': 0,
        #                 'Discount': qi.discount_value or 0, #qi.sepidar_discount * qi.quantity or 0,
        #                # 'DiscountParentRef': 1,  # optional
        #                 'Tax': qi.tax or 0,
        #                 'Duty': qi.duty or 0,
        #                 'Addition': self.object.addition if (idx == 1 and self.object.addition) else  0,
        #             }
        #             quotation_items.append(qi_dict)
        #         #
        #         q = Quotation()
        #         quotation_data = {
        #             'GUID': str(self.object.guid),
        #             'CurrencyRef': self.object.sale_type.currency.sepidar_id or 1,
        #             'Rate': self.object.sale_type.currency.current_rate() or 1,
        #             'ExpirationDate': str(self.object.expiration_date),
        #             'CustomerRef': self.object.customer_party_id.sepidar_party_id,  # 11
        #             'SaleTypeRef': self.object.sale_type.pk,
        #           #  'AddressRef': '1',  # optional
        #             'DiscountOnCustomer': 0,
        #             'Price': self.object.price or 1,
        #             'Discount': self.object.total_discount or 0, #self_discount or 0,
        #             'Tax': self.object.tax_amount or 0,
        #             'Duty': self.object.duty_amount or 0,
        #             'Addition': 0, # self.object.addition or 0, TODO sepidar dont save addition for quotation(main form)
        #             'items': quotation_items,
        #         }
        #         d = json.dumps(quotation_data)
        #         #
        #         api_res = APILogs.new_call(device=device, url=Urls.pos_quotations.url,
        #                                    method=Urls.pos_quotations.method, data=d)
        #         api_log_obj = api_res[2]
        #         api_log_obj.extra_data.request = self.request if api_log_obj else ''
        #         api_log_obj.save()
        #
        #         self.object.sepidar_quotation_id = api_res[1].get('ID') if api_res[0] == 201 else None
        #         self.object.sepidar_number = api_res[1].get('Number') if api_res[0] == 201 else None
        #         # self.object.save()
        #         if api_res[0] >= 400:
        #             print('rol back .... for status 400')
        #             content_type = ContentType.objects.filter(model=self.object._meta.model_name,
        #                                                       app_label=self.object._meta.app_label).first()
        #             flow_object = self.flow_model.objects.filter(object_id=self.object.id,
        #                                                          content_type=content_type).last()
        #             if flow_object:
        #                 flow_object.is_deleted = True
        #                 flow_object.save()
        #     if ((self.state_index == 0 and 'next' in self.request.POST) or (self.state_index == 2 and 'back' in self.request.POST)):
        #         ...
        #     self.object.save()
        # except Exception as e:
        #     pass
        #     print('rol back ....')
        #     content_type = ContentType.objects.filter(model=self.object._meta.model_name, app_label=self.object._meta.app_label).first()
        #     flow_object = self.flow_model.objects.filter(object_id=self.object.id, content_type=content_type).last()
        #     if flow_object:
        #         flow_object.is_deleted = True
        #         flow_object.save()
        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context
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


def search_factor_view(request, *args, **kwargs):
    q = request.GET.get('q')
    quotations = Quotation.objects.filter(customer_party_id__title__icontains=q).order_by('-id')
    res = dict()
    res['items'] = []
    total_count = 0
    for total_count, q in enumerate(quotations):
        item = dict()
        item['id'] = q.pk
        item['customer'] = q.customer_party_id.title
        item['customer_party_id'] = q.customer_party_id.sepidar_dl_code
        item['quotation_id'] = q.pk
        item['row_count'] = q.quotation.all().count()
        item['last_work_flow_user'] = q.last_work_flow.creator_user.username
        item['expiration_date'] = q.expiration_date
        item['sale_type'] = q.sale_type.title
        res['items'].append(item)
    else:
        res['items'].append(total_count)
    return JsonResponse(res)
