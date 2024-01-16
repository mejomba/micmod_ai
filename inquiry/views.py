import datetime
from django.core.cache import cache
from django.conf import settings
from django.forms import inlineformset_factory
from django import forms
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse_lazy, reverse
from django.views import generic
from django.views.generic import View
from django.contrib.auth.mixins import LoginRequiredMixin

from ajax_datatable.views import AjaxDatatableView

from jalali_date.templatetags.jalali_tags import to_jalali
from tools.google_sheet import price_wb
from sepidar.models import Item as sepidar_item
from changelog.models import ChangeLog
from micmod_base.base import Currency
from sepidar.models import Item as SepidarItem, Dl
from .forms import PriceInquiryFileCreateForm, PriceInquiryResultCreateForm, SalesPriceInqueryLogForm, \
    InquiryResultForm, PriceInquiryResult2CreateForm, SupplierModelForm
from .models import PriceInquiryFile, PriceInquiryResult, SalesPriceInqueryLog, InquiryResult, Supplier
from extra_data.models import Item, PriceSettings
from core.views import BaseView, JsonTemplateResponseMixin, Base
from translator import get_text as _

from tools.utils import show_error, get_tuple_value_list
from tools.form_tools import get_choice_field,get_obj_from_dict


class PriceInquiryFileCreateView(LoginRequiredMixin,
                                 BaseView,
                                 ):
    """
    price inquiry file create
    """
    form_struct = {
        'form': PriceInquiryFileCreateForm,
        'childes': [
            {
                'form': inlineformset_factory(
                        PriceInquiryFile,
                        PriceInquiryResult,
                        form=PriceInquiryResultCreateForm,
                        extra=1,
                        # fields=qi_fields,
                    ),
                'childes': [{}]
            },
        ]
    }
    flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json', 'PriceInquiryFileCreateView')
    # form_class = PriceInquiryFileCreateForm
    model = PriceInquiryFile
    # formset = inlineformset_factory(PriceInquiryFile, PriceInquiryResult, form=PriceInquiryResultCreateForm, extra=1, )
    has_formset = True
    # formset_form = PriceInquiryResultCreateForm
    formset_model = PriceInquiryResult
    extra_formset = 1
    template_name = 'inquiry/price_inquiry_file_update_or_create.html'
    success_message = '%(item)s create'
    related_name_fk = 'inquery_result'
    formset_fk_field = 'price_inquiry_file'
    # has_simple_flow = True
    # has_flow = True
    # flow_config = {
    #     'flow_name': 'create sku',
    #     'flow_action': 'some action',
    #     'flow_state_list': ['state1', 'state2', 'state3', 'state4', 'state5', 'state6', 'state7'],
    #     'flow_users_groups': ['sales_admin', 'base_user', 'wh_user', 'wh_user', 'wh_user', 'wh_user', 'base_user'],
    #     'flow_deadline': [0, 2, 3, 1, 1, 1, 2],
    # }
    # wf_to_user_permission = 'inquiry.change_priceinquiryfile'

    def get_success_url(self):
        return reverse_lazy('inquiry:price_inquiry_file.view-related', kwargs={'pk': self.object.pk})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        return kwargs

    def form_valid(self, form):
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # if self.request.user.has_perms(('inquiry.change_priceinquiryfile',)):
        #     if self.object:
        #         context['formset'] = self.formset(instance=self.object, initial=[{'sku': self.object.item if self.object else None}])
        #     ...
        return context


class PriceInquiryFileListView(LoginRequiredMixin, generic.ListView):
    """
    price inquiry file list
    """
    model = PriceInquiryFile
    template_name = 'inquiry/price_inquiry_file_list.html'
    context_object_name = 'items'


class PriceInquiryFileRelatedView(LoginRequiredMixin, generic.DetailView):
    """
    price inquiry file view-related
    """
    model = PriceInquiryFile
    context_object_name = 'item'
    template_name = 'inquiry/price_inquiry_file_view_related.html'
    form_class = PriceInquiryFileCreateForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.form_class
        if self.request.user.has_perms(('inquiry.view_inquiryresult',)):
            context['related_price_inquiry_files'] = PriceInquiryResult.objects.filter(price_inquiry_file=self.kwargs['pk'])
        return context


class PriceInquiryFileUpdateView(LoginRequiredMixin,
                                 BaseView,
                                 ):
    """
    price inquiry file update
    """
    form_struct = {
        'form': PriceInquiryFileCreateForm,
        'childes': [
            {
                'form': inlineformset_factory(
                    PriceInquiryFile,
                    PriceInquiryResult,
                    form=PriceInquiryResultCreateForm,
                    extra=1,
                    # fields=qi_fields,
                ),
                'childes': [{}]
            },
        ]
    }
    flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json', 'PriceInquiryFileUpdateView')
    # form_class = PriceInquiryFileCreateForm
    has_formset = True
    # formset_form = PriceInquiryResultCreateForm
    formset_model = PriceInquiryResult
    model = PriceInquiryFile
    template_name = 'inquiry/price_inquiry_file_update_or_create.html'
    success_message = '%(item)s update'
    context_object_name = 'priceinquiryfile'
    related_name_fk = 'inquery_result'
    formset_fk_field = 'price_inquiry_file'
    wf_to_user_permission = 'inquiry.change_priceinquiryfile'
    # has_flow = True
    # has_simple_flow = True

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        """initial work flow form kwargs"""
        return kwargs

    def get_success_url(self):
        return reverse_lazy('inquiry:price_inquiry_file.view-related', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        # form.make_disable(['sku'])
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if flow := self.get_flow(context[self.context_object_name]):
            context['flow'] = flow.order_by('-id')
        # context['flow'] = self.get_flow(context[self.context_object_name]).order_by('-id')

        context['object_logs'] = ChangeLog.get_log(context[self.context_object_name])
        # context['formset'] = self.formset(instance=self.object, initial=[{'sku': self.object.item if self.object else None}])

        related_obj = context[self.context_object_name].inquery_result.all()

        context['detail_logs'] = []
        for item in related_obj:
            context['detail_logs'].append(ChangeLog.get_log(item))

        return context


class SkuListDataTableView(AjaxDatatableView):
    model = Item
    title = 'sku_list'
    initial_order = [["sku", "des"], ]
    length_menu = [[25, 50, 100, -1], [25, 50, 100, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'sku', 'visible': True, 'title': _('sku'), 'className': 'py-1 border', 'defaultContent': '<a href"#">test</a>' },
        {'name': 'part_number', 'visible': True, 'title': _('part number'), 'className': 'py-1 border'},
        {'name': 'brand', 'visible': True, 'title': _('brand'), 'className': 'py-1 border'},
        {'name': 'quality', 'visible': True, 'title': _('quality'), 'className': 'py-1 border'},
        {'name': 'sale_group', 'visible': True, 'title': _('group sell'), 'className': 'py-1 border'},
        {'name': 'purchase_group', 'visible': True, 'title': _('group buy'), 'className': 'py-1 border'},
        {'name': 'customs_group', 'visible': True, 'title': _('group_customs'), 'className': 'py-1 border'},
        {'name': 'package', 'visible': True, 'title': _('package'), 'className': 'py-1 border'},
        {'name': 'id', 'visible': False, },
    ]

    def get_initial_queryset(self, request=None):
        qs = self.model.objects.get_access_object(self.request.user)
        return qs

    def customize_row(self, row, obj):
        row['sku'] = '<a class="fw-bold" href="%s">%s</a>' % (
                      reverse('extra_data:sku.update', args=(obj.id,)),
                      obj.sku if obj.sku else '_'
                    )


def sku_list(request):
    items = Item.objects.all()
    obj = dict()
    obj['items'] = []
    count = 0
    for item in items:
        item_json = dict()
        item_json['id'] =item.pk
        item_json['part_number'] = item.part_number
        item_json['brand'] = item.brand
        item_json['quality'] = item.quality
        item_json['group_sell'] = item.group_sell
        item_json['group_buy'] = item.group_buy
        item_json['group_customs'] = item.group_customs
        item_json['package'] = item.package

        count += 1

        obj['items'].append(item_json)
    obj['total_count'] = count
    return JsonResponse(obj)


class InquiryResultListView(BaseView):
    model = PriceInquiryResult
    form_class = PriceInquiryResult2CreateForm
    template_name = 'inquiry/inquiry_result_list_or_create.html'
    success_url = '.'

    # def get_success_url(self):
    #     sku = self.request.GET.get('sku')
    #     path = reverse('inquiry:inquiry_result.list')
    #     path += f"?sku={sku if sku else self.object.sku.pk}"
    #     return path

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form': self.form_class(initial=dict(map(lambda x: x, self.request.GET.items())))
        })
        context['submit_copy'] = True
        return context

    def post(self, request, *args, **kwargs):
        print('post')
        return super().post(request, *args, **kwargs)

    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)

    def form_valid(self, form):
        if form.cleaned_data['update_price']:
            print('update price')
        else:
            print('no update price D:')
        return super().form_valid(form)


class InquiryResultUpdateView(BaseView):
    model = PriceInquiryResult
    form_class = PriceInquiryResult2CreateForm
    template_name = 'inquiry/inquiry_result_update.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

    def get_success_url(self):
        # sku = self.request.GET.get('sku')
        path = reverse('inquiry:inquiry_result.list')
        # path += f"?sku={sku if sku else self.object.sku.pk}"
        return path

    def form_valid(self, form):
        from django.utils import timezone
        if form.cleaned_data['update_price']:
            obj = form.save(commit=False)
            obj.price_update_date = timezone.now()
            obj.save()
        else:
            pass
        return super().form_valid(form)


class InquiryResultDataTableView(AjaxDatatableView):
    model = PriceInquiryResult
    title = 'inquiry_list'
    initial_order = [["active", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    def get_columns(self, fields):
        res = [AjaxDatatableView.render_row_tools_column_def()]
        for field in fields:
            col = dict()
            col['className'] = 'p-0 border sku-search'
            col['lookup_field'] = '__icontains'
            col['defaultContent'] = ''
            col['orderable'] = True
            col['searchable'] = True
            col['name'] = field if isinstance(field,str) else None
            col['visible'] = True
            if isinstance(field,dict):
                for key in field.keys():
                    col[key] = field[key]
            res.append(col)
        return res

    def get_column_defs(self, request):
        cols = self.get_columns([
            {'name': 'sku', 'lookup_field': '__sku__iexact'},
            {'name': 'part_number', 'searchable': False},
            # 'part_number',
            # {"name": "purchase_group", "lookup_field": "sku__purchase_group__title__icontains"},
            {"name": "purchase_group", "searchable": False},
            'price',
            {'name': 'currency_type', 'lookup_field': '__title__icontains'},
            {'name': 'weight', 'searchable': False},
            {'name': 'rial_final_price_rendered', 'searchable': False, 'orderable': False},
            {'name': 'rmb_final_price_rendered', 'searchable': False, 'orderable': False},
            {'name': 'id', 'visible': False},
            {'name': 'last_update_date', 'orderable': True, 'visible': False},
            'active',
        ])
        return cols

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
        row['sku'] = '<a class="fw-bold" href="%s">%s</a>' % (
                      reverse('inquiry:inquiry_result.update', args=(obj.id,)),
                      obj.sku if obj.sku else '_'
                    )

        row['rmb_final_price_rendered'] = obj.rmb_final_price_rendered()
        row['rial_final_price_rendered'] = obj.rial_final_price_rendered()


class InquiryResultSaleView(JsonTemplateResponseMixin, BaseView):
    model = SalesPriceInqueryLog
    form_class = SalesPriceInqueryLogForm
    template_name = 'inquiry/inquiry_result_for_sales.html'

    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.form_class(initial={'currency': 1})
        return context


def inquiry_result_sale_ajax(request, *args, **kwargs):
        dict_ = request.GET or request.POST
        sku = dict_.get('sku_c')
        party_code = dict_.get('party_code')
        quantity = dict_.get('quantity') or 1
        price_setting = dict_.get('price_setting')
        currency = dict_.get('currency')
        payment_method = dict_.get('payment_method')
        grade = dict_.get('grade')

        dl_obj = Dl.get_dl(party_code)
        party_id = dl_obj[0].PartyId if dl_obj else None

        item_sku = Item.objects.filter(sku=sku).first()
        currency_obj = Currency.objects.filter(pk=currency).first()
        price = item_sku.price if item_sku else None
        price_setting_obj = PriceSettings.objects.filter(pk=price_setting).first() if price_setting else None
        final_price_settings = price_setting_obj or price.price_settings if price else PriceSettings.setting()  # use default for price !?

        form = SalesPriceInqueryLogForm(initial={'sku': sku, 'sku_c': sku, 'currency': currency or 1,
                                                 'price_setting': price_setting_obj,
                                                 'quantity': quantity or 1, 'party_code': party_code,
                                                 'payment_method': payment_method, 'grade': grade
                                                 })

        payment_methods = get_tuple_value_list(final_price_settings.discount_based_payment_method, 'title')
        grades = get_tuple_value_list(final_price_settings.discount_based_customer, 'title')
        form.fields['payment_method'] = get_choice_field(payment_methods, payment_method)
        form.fields['payment_method'].widget.attrs['onchange'] = "refresh_data(event)"
        form.fields['grade'] = get_choice_field(grades, grade)
        form.fields['grade'].widget.attrs['onchange'] = "refresh_data(event)"

        if item_sku and item_sku.price is not None:
            item_sku.price.set_discount_params(quantity=quantity, customer_grade=grade,
                                               payment_method=payment_method, currency=currency,
                                               price_setting=price_setting_obj)
        sepidar_inquiry_result = SepidarItem.get_item(code=sku, party_id=party_id)
        if sepidar_inquiry_result:
            res = sepidar_inquiry_result[0]
            item = res.__dict__
            item['q_date_cust'] = res.quotation_date
            item['q_qty_cust'] = res.quotation_qty
            item['q_fee_cust'] = res.quotation_fee
        else:
            item = dict()
        a = item_sku.sepidar_stock
        if request.GET:
            html = render_to_string('inquiry/partial/partial_inquiry_result_for_sales.html', { 'form': form, "sku": item_sku, 'item': item},request)

            return JsonResponse({'res': html})
        if request.POST:
            inquiry_log_params = {
                'sku': item_sku, 'quantity': quantity, 'grade': grade, 'payment_method': payment_method,
                'currency': currency_obj, 'price_setting': price_setting_obj, 'party_code': party_code
            }
            inquiry_log_obj = SalesPriceInqueryLog.objects.create(**inquiry_log_params)
            inquiry_log_obj.save_user(request)

            inquiry_result_params = {
                #  استعلام از بازار
                "goods_price_market": item.get('m_price') or None,
                "goods_market_date": item.get('m_date') or None,
                #  قیمت ۶۰ روز اخیر
                "goods_avg_price": item.get('avg_price') or None,
                "goods_min_price": item.get('min_price') or None,
                "goods_max_price": item.get('max_price') or None,
                #  آخرین فروش به مشتری (فاکتور)
                "goods_last_sale": item.get('f_date_cust') or None,
                "goods_total_sales": item.get('f_qty_cust') or None,
                "goods_last_price": item.get('f_fee_cust') or None,
                #  آخرین فروش به مشتری (پیش فاکتور)
                "goods_q_last_sale": item.get('q_date_cust') or None,
                "goods_q_total_sales": item.get('q_qty_cust') or None,
                "goods_q_last_price": item.get('q_fee_cust') or None,
                #  موجودی انبار
                "stock_amount": item.get('stock_qty'),
                "stock_amount_res": item.get('stock_qty_res'),
                #  express - air - sea (1) => 7200
                #  ۹ تا از این ها نگه دار ۳ تا برای ۷۲۰۰ و ۳ تا برای ۷۴۰۰ و سه تا برای rmb_final_price همونی که ۳ تا قیمت برمیگردونه
                "express_transportation_cost_1": price.rial_final_price.get('express'),
                "air_transportation_cost_1": price.rial_final_price.get('air'),
                "sea_transportation_cost_1": price.rial_final_price.get('sea'),
                #  express - air - sea (2) => 7400
                "express_transportation_cost_2": price.rial_final_price_new_order.get('express'),
                "air_transportation_cost_2": price.rial_final_price_new_order.get('air'),
                "sea_transportation_cost_2": price.rial_final_price_new_order.get('sea'),
                #  express - air - sea (3) => transportations_cost
                "express_transportation_cost_3": price.rmb_final_price.get('express'),
                "air_transportation_cost_3": price.rmb_final_price.get('air'),
                "sea_transportation_cost_3": price.rmb_final_price.get('sea'),
                "quotation_item": None,
                "price_settings": final_price_settings or None,
                "sales_price_inquery_log_id": inquiry_log_obj.id or None
            }
            obj = InquiryResult.objects.create(**inquiry_result_params)
            obj.save_user(request)

        html = render_to_string('inquiry/partial/partial_inquiry_result_for_sales.html', { 'form': form, 'item': inquiry_result_params, "sku": item_sku},request)
        # inquiry_result = render_to_string('inquiry/partial/partial_result_inquiry_result_for_sales.html', {'d': price, 'items': inquiry_result_params})

        return JsonResponse({'res': html})#, 'inquiry_result': inquiry_result})
        # return render(request, 'inquiry/partial/partial_inquiry_result_for_sales.html', {'d': price})


def get_item(request):
    q = request.GET.get('q', None)
    party_id = request.GET.get('party_id', None)
    id_currency_ref = request.GET.get('id_currency_ref', None)
    id_payment_method = request.GET.get('id_payment_method', None)
    id_payment_method = id_payment_method.split(',')[-1] if id_payment_method else None
    id_market_grade = request.GET.get('id_market_grade', None)
    id_customer_grade = request.GET.get('id_customer_grade', None)
    id_customer_grade = id_customer_grade.split(',')[-1] if id_customer_grade else None
    quantity = request.GET.get('quantity', None)
    reps = [["ي", "ی"], ["ك", "ک"]]
    obj = {}
    count = 0
    if q:
        for rep in reps:
            q = q.replace(rep[1], rep[0])
        items = sepidar_item.get_item(q, party_id)
        obj['items'] = []
        for item_ in items:
            item = {}
            try:
                item['id'] = item_.code
                item['itemid'] = item_.itemid
                item['text'] = item_.title
                item['f_date_cust'] = to_jalali(item_.f_date_cust, "%Y-%m-%d")  # goods_last_sale
                item['f_fee_cust'] = item_.f_fee_cust  # goods_last_price
                item['f_qty_cust'] = item_.f_qty_cust  # goods_total_sales
                item['q_date_cust'] = to_jalali(item_.quotation_date, "%Y-%m-%d")  # goods_q_last_sale
                item['q_fee_cust'] = item_.quotation_fee  # goods_q_last_price
                item['q_qty_cust'] = item_.quotation_qty  # goods_q_total_sales
                item['f_qty_all'] = item_.f_qty_all
                item['min_price'] = item_.min_price
                item['avg_price'] = item_.avg_price
                item['max_price'] = item_.max_price
                item['stock_qty'] = item_.stock_qty
                item['stock_qty_res'] = item_.stock_res_qty
                try:
                    price_inquiry_result: PriceInquiryResult = PriceInquiryResult.objects.filter(sku__sku=item_.code).first()
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
                except Exception as e:
                    show_error(e, __file__)
                obj['items'].append(item)
                count += 1
            except Exception as e:
                print(str(e))


    obj['total_count'] = count
    return JsonResponse(obj, safe=False)


def get_items(request):
    nested = None
    form_s = None
    q = request.GET.get('q', None)
    party_id = request.GET.get('party_id', None)
    id_currency_ref = request.GET.get('id_currency_ref', None)
    id_payment_method = request.GET.get('id_payment_method', None)
    id_payment_method = id_payment_method.split(',')[-1] if id_payment_method else None
    id_market_grade = request.GET.get('id_market_grade', None)
    id_customer_grade = request.GET.get('id_customer_grade', None)
    id_customer_grade = id_customer_grade.split(',')[-1] if id_customer_grade else None
    quantity = request.GET.get('quantity', None)
    reps = [["ي", "ی"], ["ك", "ک"]]
    obj = {}
    count = 0
    if q:
        for rep in reps:
            q = q.replace(rep[1], rep[0])
        items = sepidar_item.get_items(q, party_id)
        obj['items'] = []
        for item_ in items:
            item = {}
            try:
                item['id'] = item_.code
                item['itemid'] = item_.itemid
                item['text'] = item_.title
                item['f_date_cust'] = to_jalali(item_.f_date_cust, "%Y-%m-%d")  # goods_last_sale
                item['f_fee_cust'] = item_.f_fee_cust  # goods_last_price
                item['f_qty_cust'] = item_.f_qty_cust  # goods_total_sales
                item['q_date_cust'] = to_jalali(item_.quotation_date, "%Y-%m-%d")  # goods_q_last_sale
                item['q_fee_cust'] = item_.quotation_fee  # goods_q_last_price
                item['q_qty_cust'] = item_.quotation_qty  # goods_q_total_sales
                item['f_qty_all'] = item_.f_qty_all
                item['min_price'] = item_.min_price
                item['avg_price'] = item_.avg_price
                item['max_price'] = item_.max_price
                item['stock_qty'] = item_.stock_qty
                item['stock_qty_res'] = item_.stock_res_qty
                try:
                    price_inquiry_result: PriceInquiryResult = PriceInquiryResult.objects.filter(sku__sku=item_.code).first()
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
                except Exception as e:
                    show_error(e, __file__)

                obj['items'].append(item)
                count += 1
            except Exception as e:
                print(str(e))


    obj['total_count'] = count
    return JsonResponse(obj, safe=False)


class SupplierView(BaseView):
    model = Supplier
    form_struct = {
        'form': SupplierModelForm,
        'childes': [
            {
             'childes': [{}]
            },
        ]
    }
    # template_name = 'inquiry/supplier_create_or_update.html'

    def get_success_url(self):
        path = reverse_lazy('inquiry:supplier.list')
        if self.object:
            path += f'?name={self.object.name}'
        return path

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        return context


class SupplierListView(BaseView):
    model = Supplier
    form_class = SupplierModelForm
    template_name = 'inquiry/supplier_list_or_create.html'
    success_url = '.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if cache.get('submit/copy'):
            object_for_copy = self.model.objects.all().order_by('-last_update_date').first()
            context.update({
                'form': self.form_class(initial=dict(map(lambda x: x, [('name', object_for_copy.name), ])))
            })
        else:
            context.update({
                'form': self.form_class(initial=dict(map(lambda x: x, self.request.GET.items())))
            })
        context['submit_copy'] = True
        return context


class SupplierDataTableView(AjaxDatatableView):
    model = Supplier
    title = 'supplier_list'
    initial_order = [["name", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    def get_columns(self, fields):
        res = [AjaxDatatableView.render_row_tools_column_def()]
        for field in fields:
            col = dict()
            col['className'] = 'p-0 border'
            col['lookup_field'] = '__icontains'
            col['defaultContent'] = ''
            col['orderable'] = True
            col['searchable'] = True
            col['name'] = field if isinstance(field, str) else None
            col['visible'] = True
            if isinstance(field, dict):
                for key in field.keys():
                    col[key] = field[key]
            res.append(col)
        return res

    def get_column_defs(self, request):
        cols = self.get_columns([
            'name',
        ])
        return cols

    def get_initial_queryset(self, request=None):
        param: str = self.request.POST.get('name')
        if param:
            qs = self.model.objects.filter(name=param)
        else:
            qs = self.model.objects.all()
        return qs

    def customize_row(self, row, obj):
        row['name'] = '<a class="fw-bold" href="%s">%s</a>' % (
                      reverse('inquiry:supplier.detail_update', args=(obj.id,)),
                      obj.name if obj.name else '_'
                    )