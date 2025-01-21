import datetime
import threading

from django.shortcuts import render

from tools.utils import build_column_filter
from django.core.cache import cache
from django.conf import settings
from django.db.models.lookups import LessThan
from django.forms import inlineformset_factory
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.urls import reverse_lazy, reverse
from django.views import generic
from django.views.generic import View
from django.contrib.auth.mixins import LoginRequiredMixin
from accounts.templatetags.accounts_tag import has_one_group
from ajax_datatable.views import AjaxDatatableView

from jalali_date.templatetags.jalali_tags import to_jalali
from django.db.models import Min, IntegerField, F, Q, ExpressionWrapper, FloatField, When, Case, Subquery, Value
from django.db.models.functions import Cast, Abs, Coalesce

from micmod_base.models import QuotationItem
from sepidar.models import Item as sepidar_item
from changelog.models import ChangeLog
from micmod_base.base import Currency
from sepidar.models import Item as SepidarItem, Dl
from tools.import_data import set_items_sepidar_id_from_sepidar
from .forms import PriceInquiryFileCreateForm, PriceInquiryResultCreateForm, SalesPriceInqueryLogForm, \
    InquiryResultForm, PriceInquiryResult2CreateForm, SupplierModelForm
from .models import PriceInquiryFile, PriceInquiryResult, SalesPriceInqueryLog, InquiryResult, Supplier, AllowedInquiry
from extra_data.models import Item, PriceSettings, ItemWeight
from core.views import BaseView, JsonTemplateResponseMixin, Base, CustomAjaxDataTable
from translator import get_text as _

from tools.utils import show_error, get_tuple_value_list, c_get
from tools.form_tools import get_choice_field, get_obj_from_dict
from .tasks import update_price_list, update_components, db_backup

from tools.utils import round_price


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
                    # form=PriceInquiryResultCreateForm,
                    form=PriceInquiryResult2CreateForm,
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
            context['related_price_inquiry_files'] = PriceInquiryResult.objects.filter(
                price_inquiry_file=self.kwargs['pk'])
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


class SkuListDataTableView(CustomAjaxDataTable):
    model = Item
    title = 'sku_list'
    # initial_order = [["id", "des"], ]
    length_menu = [[25, 50, 100, -1], [25, 50, 100, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    not_search_values_separator = '|'
    render_row_details_template_name = 'sku_list_detail.html'
    from translator import get_text as _
    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'id', 'visible': False, "orderable": True},
        {'name': 'sku_int', 'searchable': True, 'visible': True, 'title': _('sku'), 'className': 'py-1 ',
         'defaultContent': '<a href"#">test</a>'},
        {'name': 'part_number', 'visible': True, 'title': _('part_number'), 'className': 'py-1 part_number_search'},
        {'name': 'parent', 'visible': True, 'searchable': True, 'lookup_field': '__sku__icontains'},
        {'name': 'brand', 'visible': True, 'title': _('brand'), 'className': 'py-1 ', 'lookup_field': '__title__icontains'},
        {'name': 'sale_group', 'visible': True, 'title': _('group sell'), 'className': 'py-1 sale_group_search', 'lookup_field': '__title__icontains'},
        {'name': 'purchase_group', 'visible': True, 'title': _('group buy'), 'className': 'py-1 purchase_group_search', 'lookup_field': '__title__icontains'},
        {'name': 'package', 'visible': True, 'title': _('package'), 'className': 'py-1 package_search'},
        {'name': 'created_date', 'visible': True, },
        {'name': 'sepidar_id_0', 'visible': True, },
        {'name': 'weight', 'visible': True, 'searchable': False, 'orderable': False},
        {'name': 'trade_last_weight', 'visible': True, 'searchable': False, 'orderable': False},
        {'name': 'wh_last_weight', 'visible': True, 'searchable': False, 'orderable': False},
        {'name': 'weight_percentage', 'visible': True, 'searchable': False, 'orderable': True},
        {'name': 'duplicate_item', 'visible': True, 'searchable': False},
    ]

    def get(self, request, *args, **kwargs):
        res = super().get(request, *args, **kwargs)
        return res

    def get_initial_order(self, request):
        res = super().get_initial_order(request)
        return []

    def get_initial_queryset(self, request=None):
        import json
        status_array = json.loads(self.request.POST.get('status_array'))
        search_list = []
        # if status_array:
        #     part_number = self.request.POST.get('columns[3][search][value]') or None
        #     sale_group = self.request.POST.get('columns[6][search][value]') or None
        #     purchase_group = self.request.POST.get('columns[7][search][value]') or None
        #     package = self.request.POST.get('columns[8][search][value]') or None
        #     if part_number:
        #         search_list.append(~Q(part_number__icontains=part_number)) if status_array[0] else search_list.append(Q(part_number__icontains=part_number))
        #     if sale_group:
        #         search_list.append(~Q(sale_group__title__icontains=sale_group)) if status_array[1] else search_list.append(Q(sale_group__title__icontains=sale_group))
        #     if purchase_group:
        #         search_list.append(~Q(purchase_group__title__icontains=purchase_group)) if status_array[2] else search_list.append(Q(purchase_group__title__icontains=purchase_group))
        #     if package:
        #         search_list.append(~Q(package__icontains=package)) if status_array[3] else search_list.append(Q(package__icontains=package))

        qs = self.model.objects.get_access_object(self.request.user)
        qs = qs.filter(*search_list)
        qs = qs.annotate(sku_int=Cast('sku', IntegerField()))
        q = self.request.POST.get('q')

        if q == 'sales_user':
            qs = qs.filter(creator_user__groups__name=q)
        elif q == 'not_confirm':
            qs = qs.filter(technical_confirm=False)
        elif q == 'weight_percentage':
            self.initial_order = [["id", "des"], ]
            qry = """
            select distinct(WH.sku_id), WH.id, WH.sku_id sku from
	(
	SELECT  "extra_data_itemweight"."id", "extra_data_itemweight"."created_date", "extra_data_itemweight"."last_update_date", "extra_data_itemweight"."is_deleted",
	"extra_data_itemweight"."creator_user_id", "extra_data_itemweight"."editor_user_id", "extra_data_itemweight"."sku_id", "extra_data_itemweight"."weight"
	FROM "extra_data_itemweight" 
	INNER JOIN "auth_user" ON ("extra_data_itemweight"."creator_user_id" = "auth_user"."id") 
	INNER JOIN "auth_user_groups" ON ("auth_user"."id" = "auth_user_groups"."user_id") 
	INNER JOIN "auth_group" ON ("auth_user_groups"."group_id" = "auth_group"."id") 
	WHERE (NOT "extra_data_itemweight"."is_deleted" AND "extra_data_itemweight"."sku_id" in (select id from extra_data_item ) AND "extra_data_itemweight"."creator_user_id" IS NOT NULL AND "auth_group"."name" in ('trade_user', 'trade_admin') ) ORDER BY "extra_data_itemweight"."id" asc
) TRADE,
	(
	SELECT  "extra_data_itemweight"."id", "extra_data_itemweight"."created_date", "extra_data_itemweight"."last_update_date", "extra_data_itemweight"."is_deleted",
	"extra_data_itemweight"."creator_user_id", "extra_data_itemweight"."editor_user_id", "extra_data_itemweight"."sku_id", "extra_data_itemweight"."weight"
	FROM "extra_data_itemweight" 
	INNER JOIN "auth_user" ON ("extra_data_itemweight"."creator_user_id" = "auth_user"."id") 
	INNER JOIN "auth_user_groups" ON ("auth_user"."id" = "auth_user_groups"."user_id") 
	INNER JOIN "auth_group" ON ("auth_user_groups"."group_id" = "auth_group"."id") 
	WHERE (NOT "extra_data_itemweight"."is_deleted" AND "extra_data_itemweight"."sku_id" in (select id from extra_data_item ) AND "extra_data_itemweight"."creator_user_id" IS NOT NULL AND "auth_group"."name" in ('wh_user', 'wh_admin')) ORDER BY "extra_data_itemweight"."id" asc
	) WH
	where TRADE.sku_id=WH.sku_id """

            #"""and abs(((WH.weight-TRADE.weight)/Trade.weight)*100)::integer>10"""
            raw = self.model.objects.raw(qry)
            ids = [x.sku for x in raw]
            qs = qs.filter(id__in=ids)
            qs = sorted(qs, key=lambda x: x.weight_percentage, reverse=True)
            qs = filter(lambda x: x.weight_percentage > 10, qs)
            pk_list = [item.pk for item in qs]
            preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(pk_list)])
            qs = self.model.objects.filter(pk__in=pk_list).order_by(preserved)

        return qs

    def get_column_defs(self, request):
        column = super().get_column_defs(request)
        print('get_column')
        if (request.user.is_superuser or 'total_admin' in request.user.groups.values_list('name', flat=True)) and 'express_extra_cost_percentage' != column[-1].get('name'):
            column.append({'name': 'extra_cost_percentage', 'visible': True})
            column.append({'name': 'sea_extra_cost_percentage', 'visible': True})
            column.append({'name': 'air_extra_cost_percentage', 'visible': True})
            column.append({'name': 'express_extra_cost_percentage', 'visible': True})
        elif request.user.is_superuser or 'total_admin' in request.user.groups.values_list('name', flat=True) and 'express_extra_cost_percentage' == column[-1].get('name'):
            pass
        else:
            column = column[:16]

        if request.user.groups.filter(name='CEO').exists():
            for row in self.column_defs:
                if row.get('name') == 'part_number':
                    row.update({'lookup_field': '__icontains'})
                if row.get('name') == 'purchase_group':
                    row.update({'lookup_field': '__title__iexact'})
                if row.get('name') == 'sale_group':
                    row.update({'lookup_field': '__title__iexact'})
                if row.get('name') == 'package':
                    row.update({'lookup_field': '__iexact'})
        return column

    def customize_row(self, row, obj):
        row['sku_int'] = '<a class="fw-bold" href="%s">%s</a>' % (
            reverse('extra_data:sku.update', args=(obj.id,)),
            obj.sku if obj.sku else '_'
        )
        row['technical_confirm'] = f'<b class="text-success" >Yes</b>' if obj.technical_confirm else '<p>No</p>'
        x = 'text-danger' if abs(obj.weight_percentage or 0) >= 20 else ''
        row['weight_percentage'] = f'<b class="{x}">% {obj.weight_percentage}</b>' \
            if obj.weight_percentage else '<p>-</p>'
        row['duplicate_item'] = f'<a href="/extra_data/item/create/?object_id={obj.pk}&ctt_id={obj.content_type().id}&request_type=duplicate" class="" target="_blank"><i class="ki-duotone ki-copy fs-2qx"></i></a>'


def sku_list(request):
    items = Item.objects.all()
    obj = dict()
    obj['items'] = []
    count = 0
    for item in items:
        item_json = dict()
        item_json['id'] = item.pk
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

    # success_url = '.'

    def get_success_url(self):
        sku = self.request.GET.get('sku')
        path = reverse('inquiry:inquiry_result.list')
        if 'submit/copy' in self.request.POST:
            path += f"?sku={sku if sku else self.object.sku.pk}"
        self.success_url = path
        # if cache.get(f'{self.request.user}__submit/copy'):
        #     pass
        return path

    def setup(self, request, *args, **kwargs):
        if request.POST.get('obj_pk') and request.POST.get('obj_pk') != 'None':
            kwargs.update({'pk': request.POST.get('obj_pk')})
        if request.GET.get('pk') and not request.POST:
            kwargs.update({'pk': request.GET.get('pk')})
        super().setup(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        object_id = self.request.GET.get('pk')
        obj = PriceInquiryResult.objects.filter(pk=object_id).first()
        if not obj:
            obj = self.model(sku_id=self.request.GET.get('sku'), active=True)
            obj.is_new = True
        obj.user = self.request.user
        if obj:
            context.update({
                'form': self.form_class(instance=obj)
            })
        if self.request.GET.get('pk'):
            context['submit_copy'] = False
            context['form'].instance.submit_copy = False
        context['app_name'] = self.request.resolver_match.app_name

        # if cache.get(f'{self.request.user}__submit/copy'):
        #     object_for_copy = self.model.objects.all().order_by('-last_update_date').first()
        #     context.update({
        #         'form': self.form_class(initial=dict(map(lambda x: x, [('sku', object_for_copy.sku),
        #                                                                ('sku_c', object_for_copy.sku),
        #                                                                ]
        #                                                  )
        #                                              )
        #                                 )
        #     })
        # else:
        #     context.update({
        #         'form': self.form_class(initial=dict(map(lambda x: x, self.request.GET.items())))
        #     })
        # context['submit_copy'] = True
        return context

    def post(self, request, *args, **kwargs):
        print('post')
        return super().post(request, *args, **kwargs)

    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)

    def form_valid(self, form):
        from django.utils import timezone
        qi_id = self.request.GET.get('qi_id')
        submit_for_qi = self.request.POST.get('submit_for_qi')
        last_price = self.object.price if self.object else 0
        res = super().form_valid(form)

        if self.object and last_price and self.object.price != last_price:
            self.object.price_update_date = timezone.now()
            self.object.save()

        if form.cleaned_data['update_price'] and self.object:
            self.object.price_update_date = timezone.now()
            self.object.save()

        if self.object and self.object.item_weight and 'item_weight' in form.changed_data and self.object.sku.weight != self.object.item_weight:
            item_weight = ItemWeight.objects.create(sku=self.object.sku, weight=self.object.item_weight)
            item_weight.extra_data.request = self.request
            item_weight.save()
            # item_weight.save_user(request=self.request)

        """save quotation_item inquiry result"""
        if submit_for_qi and qi_id:
            qi_obj = QuotationItem.objects.filter(pk=qi_id).first()
            qi_obj.extra_data.request = self.request
            if self.request.user.base_group == 'bazar':
                qi_obj.local_price_inquiry_done = True  # آقای اسدی گفتن وقتی ثبت برای پیش فاکتور رو میزنن لزومی نداره که دوباره برن ذخیره کنن پس خودکار تایید بشه
                qi_obj.bazar_price_code = self.object
                qi_obj.save()
            elif self.request.user.base_group == 'trade':
                # qi_obj.foreign_price_inquiry_done = True  # خانم شیوا ابراهیمی گفتن این مورد رو لازم ندارن و خودشون باید تیک تایید رو بزنن
                qi_obj.trade_price_code = self.object
                qi_obj.save()

            iqr_obj = qi_obj.quotation_item_rel.first()
            iqr_form = InquiryResultForm(self.request.POST, instance=iqr_obj)
            if iqr_form.is_valid():
                iqr_obj = iqr_form.save()
                iqr_obj.quotation_item = qi_obj
                iqr_obj.extra_data.request = self.request
                iqr_obj.save()

        return res


class InquiryResultUpdateView(BaseView):
    model = PriceInquiryResult
    form_class = PriceInquiryResult2CreateForm
    template_name = 'inquiry/inquiry_result_update.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # self.request.GET._mutable = True
        # self.request.GET.update({'user': self.request.user})
        context.update({
            'form': self.form_class(instance=self.object, data={'sku': self.object.sku},
                                    initial={'user': self.request.user})
        })
        # self.request.GET._mutable = False
        context['submit_copy'] = False
        # if not self.object.item_weight:
        sku = self.object.sku
        # TODO: filter by user type
        qry = f"select * from((select * from(SELECT distinct iw.*FROM public.extra_data_itemweight as iw left join public.auth_user_groups as ug on ug.user_id = iw.creator_user_id left join public.auth_group as g_ on g_.id = ug.group_id where g_.name = 'wh_user' order by iw.id desc) a1) union (select * from(SELECT distinct iw.*FROM public.extra_data_itemweight as iw left join public.auth_user_groups as ug on ug.user_id = iw.creator_user_id left join public.auth_group as g_ on g_.id = ug.group_id where not g_.name = 'wh_user' or g_.name is null order by iw.id desc) a2)) a3 where sku_id = {sku.pk}"
        # context['pre_item_weight'] = ItemWeight.objects.filter(sku=sku).first()
        try:
            context['pre_item_weight'] = ItemWeight.objects.raw(qry)[0]
        except Exception:
            context['pre_item_weight'] = []
        return context

    def get_success_url(self):
        # sku = self.request.GET.get('sku')
        path = reverse('inquiry:inquiry_result.list')
        # path += f"?sku={sku if sku else self.object.sku.pk}"
        return path

    def form_valid(self, form):
        from django.utils import timezone
        from extra_data.models import ItemWeight
        if form.cleaned_data['update_price']:
            obj = form.save(commit=False)
            obj.price_update_date = timezone.now()
            obj.save()
        else:
            pass
        res = super().form_valid(form)
        sku = self.object.sku
        item_weight = self.object.item_weight
        if item_weight:
            ItemWeight.objects.create(sku=sku, weight=item_weight)

        return res


class InquiryResultDataTableView(AjaxDatatableView):
    model = PriceInquiryResult
    title = 'inquiry_list'
    initial_order = [["price_update_date", "des"], ]
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
            {'name': 'sku', 'lookup_field': '__sku__iexact', 'className': 'sku-search w-15px'},
            # {'name': 'last_update_date', 'data': 'last_update_date', 'orderable': True, 'visible': True, 'className': 'w-10px'},
            {'name': 'price_update_date', 'data': 'price_update_date', 'orderable': True, 'visible': True,
             'className': 'w-10px'},
            {'name': 'editor_user', 'lookup_field': '__username__icontains', 'className': 'w-10px'},
            {'name': 'part_number', 'searchable': True, 'orderable': True, 'lookup_field': '__icontains',
             'className': 'w-20'},
            # 'part_number',
            # {"name": "purchase_group", "lookup_field": "sku__purchase_group__title__icontains"},
            # {"name": "purchase_group", "searchable": False},
            {'name': 'purchase_group', 'searchable': True, 'orderable': True, 'className': 'w-20px'},
            {'name': 'active', 'className': 'w-7px'},
            {'name': 'price', 'className': 'w-15px'},
            {'name': 'currency_type', 'lookup_field': '__title__icontains', 'className': 'w-10px'},
            {'name': 'weight', 'searchable': False, 'className': 'w-10px'},
            {'name': 'id', 'visible': False},
            {'name': 'inquiry_type', 'orderable': True, 'searchable': True, 'visible': True,
             'lookup_field': '__title__icontains', 'className': 'w-10px'},
            'variants_json',
            'description',
            {'name': 'supplier', 'lookup_field': '__title__icontains'},
            {'name': 'qi_count', 'title': 'تعداد در پیش فاکتور', 'searchable': False, 'orderable': False},
            {'name': 'delete', 'title': 'حذف', 'searchable': False, 'orderable': False}
        ]
        if request.user.is_superuser or 'total_admin' in request.user.groups.values_list('name', flat=True):
            cols.append({'name': 'rial_final_price_rendered', 'searchable': False, 'orderable': False})
            cols.append({'name': 'rmb_final_price_rendered', 'searchable': False, 'orderable': False})
        return self.get_columns(cols)

    def get_initial_queryset(self, request=None):
        sku: str = self.request.POST.get('sku')
        try:
            if sku and sku.isdigit():
                sku = int(sku)
            else:
                sku = ''
        except TypeError as e:
            show_error(e, __file__)
        if sku:
            qs = self.model.inquiry_list_datatable(user=self.request.user, param={"sku": sku})
        else:
            qs = self.model.inquiry_list_datatable(user=self.request.user)
        # qs = qs.extra(select={'m_part_number': f'select part_number from extra_data_Item where extra_data_Item.id = inquiry_PriceInquiryResult.sku_id'}).filter()
        qs = qs.annotate(part_number=F('sku__part_number'), purchase_group=F('sku__purchase_group__title'))
        return qs.order_by('last_update_date')

    def customize_row(self, row, obj):
        delete_url = reverse('core:delete.confirm')
        row['delete'] = f"""
        <a href="#" onclick="delete_inquiry(event)" target="_blank" class="delete-inquiry-result text-danger tooltip_ py-3" data-url="{delete_url}?model={obj.__class__.__name__}&object_id={obj.pk}&app_label=inquiry" data-bs-toggle="modal" data-bs-target="#id_kt_empty_modal_sm">
                            <span class="tooltiptext">حذف</span>
                            <i class="ki-duotone ki-trash fs-2 text-danger">
                                <span class="path1"></span>
                                <span class="path2"></span>
                                <span class="path3"></span>
                                <span class="path4"></span>
                                <span class="path5"></span>
                            </i>
                        </a>
                        """
        qi = obj.trade_quotation_rel.first() or obj.bazar_quotation_rel.first()
        row['qi_count'] = f"<span class='d-flex flex-column'><span>{qi.quantity} - {qi.quotation.pk}</span>" \
                          f"<hr class='text-muted'><span>تعداد - پیش</span></span>" if qi else '-'
        row['sku'] = '<a class="fw-bold" href="%s">%s</a>' % (
            f"/inquiry/inquiryresult/list/?pk={obj.id}", obj.sku if obj.sku else '_'
        )
        if self.request.user.is_superuser or 'total_admin' in self.request.user.groups.values_list('name', flat=True):
            row['rmb_final_price_rendered'] = obj.rmb_final_price_rendered()
            row['rial_final_price_rendered'] = obj.rial_final_price_rendered()
        if obj.active:
            row['active'] = """<b class="text-success">Yes</b>"""

        if obj.active:
            row['active'] = """<b class="text-success">Yes</b>"""

        html = '<div class="d-flex flex-column">'
        for k, v in obj.variants_json.items() if obj.variants_json else []:
            html += f'''<span class="d-flex justify-content-start">
                            <span class="me-1 px-1">{k}</span>
                            <span>{v}</span>
                        </span>'''
        else:
            html += '</div>'
        row['variants_json'] = html


class InquiryResultSaleView(JsonTemplateResponseMixin, BaseView):
    model = SalesPriceInqueryLog
    form_class = SalesPriceInqueryLogForm
    template_name = 'inquiry/inquiry_result_for_sales.html'

    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.form_class(initial={'currency': 1, 'request':self.request})
        return context


def inquiry_result_sale_ajax(request, *args, **kwargs):
    if not has_one_group(request.user,
                         ["sales_user", "sales_admin", "total_admin", "store_admin", "bazar_user", "bazar_admin",
                          "store_user"]):
        return
    load_sepidar = request.GET.get('load_sepidar')
    dict_ = request.GET or request.POST
    prev_value = dict_.get('prev_value')
    sku = dict_.get('sku_c')
    party_code = dict_.get('party_code')
    quantity = dict_.get('quantity') or 1
    price_setting = dict_.get('price_setting')
    currency = dict_.get('currency')
    payment_method = dict_.get('payment_method')
    grade = dict_.get('grade')
    if prev_value.isdigit():
        search_sku = True
    else:
        search_sku = False
    if request.GET.get('sku_c') == request.GET.get('sku'):
        target_trade_price = request.GET.get('all_trade_prices')
        target_bazar_price = request.GET.get('all_bazar_prices')
    else:
        target_trade_price = ''
        target_bazar_price = ''

    currency_obj = Currency.objects.filter(pk=currency).first()

    if load_sepidar:
        dl_obj = Dl.get_dl(party_code)
        party_id = dl_obj[0].PartyId if len(dl_obj) else None

    sku_or_partnumber_filter = Q(sku=sku) | Q(part_number=sku)
    item_sku = Item.objects.filter(sku_or_partnumber_filter).first()
    # item_sku = Item.objects.filter(sku=sku).first()
    all_trade_active_prices = item_sku.all_trade_active_price_
    all_bazar_active_prices = item_sku.all_bazar_active_price_

    if not target_trade_price:
        price = item_sku.price if item_sku else None
    else:
        price = PriceInquiryResult.objects.filter(pk=target_trade_price).first()

    if not target_bazar_price:
        bazar_price = item_sku.bazar_price if item_sku else None
    else:
        bazar_price = PriceInquiryResult.objects.filter(pk=target_bazar_price).first()

    price_setting_obj = PriceSettings.objects.filter(pk=price_setting).first() if price_setting else None
    final_price_settings = price_setting_obj or price.price_settings if price else PriceSettings.setting()  # use default for price !?

    form = SalesPriceInqueryLogForm(initial={'sku': sku, 'sku_c': sku, 'currency': currency or 1,
                                             'price_setting': price_setting_obj,
                                             'quantity': quantity or 1, 'party_code': party_code,
                                             'payment_method': payment_method, 'grade': grade,
                                             'request': request, 'part_number': item_sku.part_number if item_sku else "",
                                             'trade_price': (price.pk, price.inquiry_type.title) if price else '',
                                             'bazar_price': (bazar_price.pk, bazar_price.inquiry_type.title) if bazar_price else '',
                                             'all_trade_active_prices': all_trade_active_prices,
                                             'all_bazar_active_prices': all_bazar_active_prices,
                                             'search_sku': search_sku
                                             })

    payment_methods = get_tuple_value_list(final_price_settings.discount_based_payment_method, 'title')
    grades = get_tuple_value_list(final_price_settings.discount_based_customer, 'title')
    form.fields['payment_method'] = get_choice_field(payment_methods, payment_method)
    form.fields['payment_method'].widget.attrs['onchange'] = "refresh_data(event)"
    form.fields['grade'] = get_choice_field(grades, grade)
    form.fields['grade'].widget.attrs['onchange'] = "refresh_data(event)"

    if item_sku and price is not None:
        price.set_discount_params(quantity=quantity, customer_grade=grade,
                                  payment_method=payment_method, currency=currency,
                                  price_setting=price_setting_obj)
    if item_sku and bazar_price is not None:
        bazar_price.set_discount_params(quantity=quantity, customer_grade=grade,
                                        payment_method=payment_method, currency=currency,
                                        price_setting=price_setting_obj)

    sepidar_inquiry_result = []
    if load_sepidar:
        sepidar_inquiry_result = SepidarItem.get_item(code=sku, party_id=party_id)
    if sepidar_inquiry_result:
        res = sepidar_inquiry_result[0]
        item = res.__dict__
        item['q_date_cust'] = res.quotation_date
        item['q_qty_cust'] = res.quotation_qty
        item['q_fee_cust'] = res.quotation_fee
    else:
        item = dict()
    if request.GET:
        html = render_to_string('inquiry/partial/partial_inquiry_result_for_sales.html', {'form': form,
                                                                                          "sku": item_sku,
                                                                                          'item': item,
                                                                                          'trade_price': price,
                                                                                          'bazar_price': bazar_price,
                                                                                          }, request)

        return JsonResponse({'res': html})
    if request.POST:
        inquiry_log_params = {
            'sku': item_sku, 'quantity': quantity, 'grade': grade, 'payment_method': payment_method,
            'currency': currency_obj, 'price_setting': price_setting_obj, 'party_code': party_code
        }
        inquiry_log_obj = SalesPriceInqueryLog.objects.create(**inquiry_log_params)
        inquiry_log_obj.extra_data.request = request
        inquiry_log_obj.save()
        # inquiry_log_obj.save_user(request)

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
        obj.extra_data.request = request
        obj.save()
        # obj.save_user(request)

    html = render_to_string('inquiry/partial/partial_inquiry_result_for_sales.html',
                            {'form': form, 'item': item, "sku": item_sku}, request)
    # inquiry_result = render_to_string('inquiry/partial/partial_result_inquiry_result_for_sales.html', {'d': price, 'items': inquiry_result_params})

    return JsonResponse({'res': html})  # , 'inquiry_result': inquiry_result})
    # return render(request, 'inquiry/partial/partial_inquiry_result_for_sales.html', {'d': price})


def get_item(request):
    trade_price_code = request.GET.get('trade_price_code')
    bazar_price_code = request.GET.get('bazar_price_code')
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
                item['f_fee_cust'] = round_price(item_.f_fee_cust)  # goods_last_price
                item['f_qty_cust'] = round_price(item_.f_qty_cust)  # goods_total_sales
                item['q_date_cust'] = to_jalali(item_.quotation_date, "%Y-%m-%d")  # goods_q_last_sale
                item['q_fee_cust'] = round_price(item_.quotation_fee)  # goods_q_last_price
                item['q_qty_cust'] = item_.quotation_qty  # goods_q_total_sales
                item['f_qty_all'] = item_.f_qty_all
                item['min_price'] = round_price(item_.min_price)
                item['avg_price'] = round_price(item_.avg_price)
                item['max_price'] = round_price(item_.max_price)
                item['stock_qty'] = item_.stock_qty
                item['stock_qty_res'] = item_.stock_res_qty
                try:
                    item_obj = old_item_obj = Item.objects.filter(sku=q).first()
                    if item_obj and item_obj.parent and item_obj.active_main_item:
                        item_obj = item_obj.parent

                    # if trade_price_code or bazar_price_code:
                    price_inquiry_result: PriceInquiryResult = PriceInquiryResult.objects.filter(
                        pk=trade_price_code).first() if (trade_price_code) else item_obj.price
                    price_inquiry_result_bazar: PriceInquiryResult = PriceInquiryResult.objects.filter(
                        pk=bazar_price_code).first() if (bazar_price_code) else old_item_obj.bazar_price
                    # price_inquiry_result: PriceInquiryResult = item_obj.price
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

                    if price_inquiry_result_bazar and price_inquiry_result_bazar.is_valid_time:
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
                        item["price_update_date"] = to_jalali(price_inquiry_result_bazar.price_update_date, "%Y-%m-%d")
                    else:
                        item["goods_price_market"] = None
                        item["goods_market_date"] = 'تاریخ نامعتبر'
                except Exception as e:
                    show_error(e, __file__)
                obj['items'].append(item)
                count += 1
            except Exception as e:
                print(str(e))

        if not items:
            for item_ in Item.objects.filter(Q(sku__iexact=q) | Q(part_number__iexact=q), sepidar_id_0__isnull=True):
                item = {}
                try:
                    item['id'] = item_.pk
                    item['itemid'] = item_.sepidar_id_0
                    item['text'] = item_.part_number
                    try:
                        item_obj: Item = item_
                        price_inquiry_result: PriceInquiryResult = PriceInquiryResult.objects.filter(
                            pk=trade_price_code).first() if (trade_price_code) else item_obj.price
                        price_inquiry_result_bazar: PriceInquiryResult = PriceInquiryResult.objects.filter(
                            pk=bazar_price_code).first() if (bazar_price_code) else item_obj.bazar_price
                        # price_inquiry_result: PriceInquiryResult = item_obj.price
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

                        if price_inquiry_result_bazar and price_inquiry_result_bazar.is_valid_time:
                            price_setting = price_inquiry_result_bazar.price_settings
                            price_inquiry_result_bazar.set_discount_params(
                                quantity=quantity,
                                customer_grade=id_customer_grade,
                                payment_method=id_payment_method,
                                currency=id_currency_ref,
                                price_setting=price_setting
                            )
                            item["goods_price_market"] = price_inquiry_result_bazar.bazar_price
                            item["goods_market_date"] = to_jalali(price_inquiry_result_bazar.price_update_date,
                                                                  "%Y-%m-%d")
                        else:
                            item["goods_price_market"] = None
                            item["goods_market_date"] = None

                    except Exception as e:
                        show_error(e, __file__)

                    obj['items'].append(item)
                    count += 1
                except Exception as e:
                    print(show_error(e, __file__))

    obj['total_count'] = count
    return JsonResponse(obj, safe=False)


def get_items(request):
    q = request.GET.get('q', None)
    party_id = request.GET.get('party_id', 0)
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
                item['f_fee_cust'] = round_price(item_.f_fee_cust)  # goods_last_price
                item['f_qty_cust'] = round_price(item_.f_qty_cust)  # goods_total_sales
                item['q_date_cust'] = to_jalali(item_.quotation_date, "%Y-%m-%d")  # goods_q_last_sale
                item['q_fee_cust'] = round_price(item_.quotation_fee)  # goods_q_last_price
                item['q_qty_cust'] = item_.quotation_qty  # goods_q_total_sales
                item['f_qty_all'] = item_.f_qty_all
                item['min_price'] = round_price(item_.min_price)
                item['avg_price'] = round_price(item_.avg_price)
                item['max_price'] = round_price(item_.max_price)
                item['stock_qty'] = item_.stock_qty
                item['stock_qty_res'] = item_.stock_res_qty
                try:
                    sku_item = old_sku_item = Item.objects.filter(sku=item_.code).first()
                    if sku_item and sku_item.parent and sku_item.active_main_item:
                        sku_item = sku_item.parent
                        item['parent_sku'] = sku_item.sku
                        item['parent_part_number'] = sku_item.part_number
                    price_inquiry_result: PriceInquiryResult = sku_item.price if sku_item else None
                    price_inquiry_result_bazar: PriceInquiryResult = old_sku_item.bazar_price if old_sku_item else None
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

                    if price_inquiry_result_bazar and price_inquiry_result_bazar.is_valid_time:
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
                        item["price_update_date"] = to_jalali(price_inquiry_result_bazar.price_update_date, "%Y-%m-%d")
                    else:
                        item["goods_price_market"] = None
                        item["goods_market_date"] = None
                except Exception as e:
                    show_error(e, __file__)

                obj['items'].append(item)
                count += 1
            except Exception as e:
                print(show_error(e, __file__))

        # local items
        local_items = Item.objects.filter(Q(sku__icontains=q) | Q(part_number__icontains=q), sepidar_id_0__isnull=True)[:3] if len(q) > 2 else ''
        for item_ in local_items:
            item = {}
            try:
                item['id'] = item_.pk
                item['itemid'] = item_.sepidar_id_0
                item['text'] = item_.part_number
                # item['f_date_cust'] = to_jalali(item_.f_date_cust, "%Y-%m-%d")  # goods_last_sale
                # item['f_fee_cust'] = round_price(item_.f_fee_cust)  # goods_last_price
                # item['f_qty_cust'] = round_price(item_.f_qty_cust)  # goods_total_sales
                # item['q_date_cust'] = to_jalali(item_.quotation_date, "%Y-%m-%d")  # goods_q_last_sale
                # item['q_fee_cust'] = round_price(item_.quotation_fee)  # goods_q_last_price
                # item['q_qty_cust'] = item_.quotation_qty  # goods_q_total_sales
                # item['f_qty_all'] = item_.f_qty_all
                # item['min_price'] = round_price(item_.min_price)
                # item['avg_price'] = round_price(item_.avg_price)
                # item['max_price'] = round_price(item_.max_price)
                # item['stock_qty'] = item_.stock_qty
                # item['stock_qty_res'] = item_.stock_res_qty
                try:
                    sku_item: Item = item_
                    price_inquiry_result: PriceInquiryResult = sku_item.price if sku_item else None
                    price_inquiry_result_bazar: PriceInquiryResult = sku_item.bazar_price if sku_item else None
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

                    if price_inquiry_result_bazar and price_inquiry_result_bazar.is_valid_time:
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
                        item["price_update_date"] = to_jalali(price_inquiry_result_bazar.price_update_date, "%Y-%m-%d")
                    else:
                        item["goods_price_market"] = None
                        item["goods_market_date"] = None
                except Exception as e:
                    show_error(e, __file__)

                obj['items'].append(item)
                count += 1
            except Exception as e:
                print(show_error(e, __file__))

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
            path += f'?title={self.object.title}'
        self.success_url = path
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

        if cache.get(f'{self.request.user}__submit/copy'):
            object_for_copy = self.model.objects.all().order_by('-last_update_date').first()
            context.update({
                'form': self.form_class(initial=dict(map(lambda x: x, [('title', object_for_copy.name), ])))
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
    initial_order = [["title", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'inquiry/supplier_list_or_create.html'

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
            'title',
        ])
        return cols

    def get_initial_queryset(self, request=None):
        param: str = self.request.POST.get('title')
        if param:
            qs = self.model.objects.filter(title=param)
        else:
            qs = self.model.objects.all()
        return qs

    def customize_row(self, row, obj):
        row['title'] = '<a class="fw-bold" href="%s">%s</a>' % (
            reverse('inquiry:supplier.detail_update', args=(obj.id,)),
            obj.title if obj.title else '_'
        )


class AjaxInquiryResultListData(View):
    def get(self, request):
        # x = dict()
        # x.update(request.FILES)
        # x.update(request.POST)
        # form = PriceInquiryResult2CreateForm(initial=x).initial
        # render_to_string('inquiry/partial/')
        # sku = PriceInquiryResult.objects.filter(sku=request.GET.get('sku')).first()
        # if not sku:
        sku = Item.objects.filter(sku=(request.GET.get('sku'))).first()
        if sku:
            try:
                parent = sku.parent
                username = sku.weight_obj
                username = username.editor_user.username if username else ''
                if parent:
                    return JsonResponse(
                        {'sku_name': sku.part_number, 'item_weight': f'{username} ({sku.weight})', 'item_id': sku.id,
                         'parent': f'{parent.sku} - {parent.part_number}'})
                else:
                    return JsonResponse(
                        {'sku_name': sku.part_number, 'item_weight': f'{username} ({sku.weight})', 'item_id': sku.id, 'parent': '-'})
            except:
                pass
        return JsonResponse({'sku_name': sku.part_number, 'item_weight': None, 'item_id': sku.id, 'parent': None})


# Todo ino yadet nare shanbe
# class InquiryResultUpdateFormView(View):
#     def get(self, request):
#         sku = request.GET.get('sku')
#         obj = PriceInquiryResult.objects.filter(sku=sku).first()
#         form = PriceInquiryResult2CreateForm(instance=obj)
#         form_html = render_to_string('inquiry/partial/inquiry_result_update_form.html', context={'form': form})


def update_components_view(request, *args, **kwargs):
    # update_components()
    if cache.get('update_components'):
        print('task is running')
        return JsonResponse({'result': f'task_is running'})
    count = PriceInquiryResult.objects.raw('select 1 as id,count(*) as num from extra_data_item')[0].num
    update_time = datetime.datetime.now().strftime('%Y/%m/%d  %H:%M')
    sub_thread = threading.Thread(target=update_components.apply_async)
    sub_thread.start()
    return JsonResponse({'result': f'start updated at: {update_time}', 'Item\'s count': count,'celery task id': sub_thread.native_id})


def get_price_list(request, *args, **kwargs):
    update_price_list()
    if cache.get('task_is_running'):
        print('task is running')
        return JsonResponse({'result': f'task_is running'})
    count = PriceInquiryResult.objects.raw('select 1 as id,count(*) as num from inquiry_priceinquiryresult')[0].num
    update_time = datetime.datetime.now().strftime('%Y/%m/%d  %H:%M')
    sub_thread = threading.Thread(target=update_price_list.apply_async)
    sub_thread.start()
    # update_price_list.delay()
    # from tlg.task import add_new_order_receiver
    # add_new_order_receiver.delay()
    return JsonResponse({'result': f'start updated at: {update_time}', 'price_count': count,'celery task id': sub_thread.native_id})


class InquiryResultSaleListView(LoginRequiredMixin, generic.ListView):
    model = SalesPriceInqueryLog
    template_name = 'inquiry/partial/inquiry_result_sales_list.html'


class SalesPriceInqueryLogDataTableView(AjaxDatatableView):

    model = SalesPriceInqueryLog
    title = 'inquiry_result_sale_data'
    initial_order = [["sku", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'inquiry_result_sales_list.html'

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
            {'name': 'sku', 'lookup_field': '__sku__iexact', 'className': 'sku-search w-15px'},
            'party_code',
            'currency',
            'quantity',
            'grade',
            'payment_method',
        ]
        return self.get_columns(cols)

    # def get_initial_queryset(self, request=None):
    #     return self.model.objects.all()


def trade_all_prices(request):
    if request.method == 'GET':
        sku = request.GET.get('sku')
        if not sku.isdigit():
            return JsonResponse({'items': [{'invalid': 'item'}]})
        if q := request.GET.get('q'):
            try:
                trade_all_price = PriceInquiryResult.objects.filter(Q(inquiry_type__title__icontains='خارج'),
                                                                    Q(inquiry_type__title__icontains=q) | Q(pk__icontains=q),
                                                                    sku=sku,
                                                                    active=True,
                                                                    is_deleted=False)
            except Exception as e:
                trade_all_price = PriceInquiryResult.objects.filter(Q(inquiry_type__title__icontains='خارج'),
                                                                    sku=sku,
                                                                    active=True,
                                                                    is_deleted=False)
        else:
            trade_all_price = PriceInquiryResult.objects.filter(Q(inquiry_type__title__icontains='خارج'),
                                                                sku=sku,
                                                                active=True,
                                                                is_deleted=False)

        data = list()
        for item in trade_all_price:
            obj = dict()
            obj['id'] = item.pk
            obj['sku'] = item.sku.pk
            obj['last_update_date'] = item.jalali_last_update_date
            obj['inquiry_type'] = item.inquiry_type.title
            obj['variants_json'] = item.variants_json
            obj['editor_user'] = item.editor_user.username
            data.append(obj)
        return JsonResponse({'items': data})


def bazar_all_prices(request):
    if request.method == 'GET':
        sku = request.GET.get('sku')
        if not sku.isdigit():
            return JsonResponse({'items': [{'invalid': 'item'}]})
        if q := request.GET.get('q'):
            try:
                bazar_all_price = PriceInquiryResult.valid_bazar_inquiry().filter(Q(inquiry_type__title__icontains='داخل'),
                                                                    Q(inquiry_type__title__icontains=q) | Q(pk__icontains=q),
                                                                    sku=sku,
                                                                    active=True,
                                                                    is_deleted=False)
            except Exception as e:
                print('exception')
                bazar_all_price = PriceInquiryResult.valid_bazar_inquiry().filter(Q(inquiry_type__title__icontains='داخل'),
                                                                    sku=sku,
                                                                    active=True,
                                                                    is_deleted=False)
        else:
            bazar_all_price = PriceInquiryResult.valid_bazar_inquiry().filter(Q(inquiry_type__title__icontains='داخل'),
                                                                sku=sku,
                                                                active=True,
                                                                is_deleted=False)

        data = list()
        for item in bazar_all_price:
            obj = dict()
            obj['id'] = item.pk
            obj['sku'] = item.sku.pk
            obj['last_update_date'] = item.jalali_last_update_date
            obj['inquiry_type'] = item.inquiry_type.title
            obj['variants_json'] = item.variants_json
            obj['editor_user'] = item.editor_user.username
            data.append(obj)
        return JsonResponse({'items': data})


def all_prices(request):
    if request.method == 'GET':
        sku = request.GET.get('sku')
        if not sku.isdigit():
            return JsonResponse({'items': [{'invalid': 'item'}]})
        if q := request.GET.get('q'):
            try:
                bazar_all_price = PriceInquiryResult.valid_bazar_inquiry().filter(Q(inquiry_type__title__icontains=q) | Q(pk__icontains=q),
                                                                    sku=sku,
                                                                    active=True,
                                                                    is_deleted=False)
            except Exception as e:
                print('exception')
                bazar_all_price = PriceInquiryResult.valid_bazar_inquiry().filter(sku=sku,
                                                                    active=True,
                                                                    is_deleted=False)
        else:
            bazar_all_price = PriceInquiryResult.objects.filter(sku=sku,
                                                                active=True,
                                                                is_deleted=False,
                                                                inquiry_type__title__icontains='خارج')
            bazar_all_price |= PriceInquiryResult.valid_bazar_inquiry().filter(active=True, is_deleted=False, sku=sku)

        data = list()
        for item in bazar_all_price:
            obj = dict()
            obj['inquiry_type_detector'] = 1 if item.inquiry_type.title.lower().__contains__('خارج') else 2
            obj['id'] = item.pk
            obj['sku'] = item.sku.pk
            obj['last_update_date'] = item.jalali_last_update_date
            obj['inquiry_type'] = item.inquiry_type.title
            obj['variants_json'] = item.variants_json
            obj['editor_user'] = item.editor_user.username
            data.append(obj)
        return JsonResponse({'items': data})


def inquiry_count(request):
    count = 0
    if sku := request.GET.get('sku'):
        item = Item.objects.filter(pk=sku).first()
        count = item.inquiry_count
    return JsonResponse({'res': count})


def get_inquiry_title(request, *args, **kwargs):
    allowed_inquiry = AllowedInquiry.objects.all()
    res = dict()
    for idx, item in enumerate(allowed_inquiry):
        res[f'title_{idx}'] = item.title
    return JsonResponse(res)


def pg_backup(request, *args, **kwargs):
    if request.user.is_superuser:
        res = db_backup()
        return HttpResponse(res)

