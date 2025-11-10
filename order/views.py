from datetime import timedelta

from ajax_datatable import AjaxDatatableView
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.contrib import messages
from django.db.models import Sum, F, ExpressionWrapper, FloatField, Q
from django.db.models.functions import Coalesce
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views import View
from django.views.generic import ListView
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import HasShopPermission
from core.views import BaseView, Base
from factor.models import Factor, FactorItem
from inquiry.models import Supplier
from micmod_base.models import QuotationItem, SupplyStatus
from sepidar.api_call import SepidarApiCall
from tools.utils import is_ajax
from workflow.models import WorkFlow
from .forms import OrderForm, PackingForm, PackingItemForm, GIOForm, GIOItemForm, OrderPaymentForm, \
    OrderPaymentItemForm, OrderPaymentItemFormSet, BazarBuyFactorForm, \
    TradeBuyFactorForm, TradePurchaseItemFormSet, BazarPurchaseItemFormSet, ACNTForm
from .models import Order, OrderOrder, Packing, PackingItem, GIO, GIOItem, OrderPayment, OrderPaymentItem, ACNT
from translator import get_text as _
from .serializers import OrderSerializer
import json

# def factor_order_item(request, sku, quantity):
#     items = get_object_or_404(QuotationItem, goods_code=sku)
#
#     for item in items.goods_code:
#         order_item = OrderItem.objects.create(order__title=item)


class OrderView(LoginRequiredMixin, BaseView):
    template_name = 'order/view.html'
    form_class = OrderForm
    model = Order
    wf_last_step_is_open = True
    has_flow = True
    form_struct = {
        'form': OrderForm,
        'childes': [
            {},
        ]
    }
    flow_config = Base.get_flow_config(settings.BASE_DIR/'_keenthemes/view_config.json', 'OrderView')

    def get_success_url(self):
        return reverse_lazy('order:order.view', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        from tools import const
        res = super().form_valid(form)
        if 'back' in self.request.POST and self.state_index == 4 and not self.object.mohandes_confirmation:
            flow_data = {
                "wf_status": 2,  # back
                "action": 'ایجاد خودکار',
                "flow_name": 'سفارش',
                "state": const.WF__ORDER__4_STATE,
                "wf_description": "بدون نیاز به تایید مهندس",
                "belong_to_group": 'trade_order',
                "object_id": self.object.pk,
                "content_type": ContentType.objects.get_for_model(self.object),
                "creator_user": self.request.user,
                "editor_user": self.request.user,
                "from_user": self.request.user,
                "to_user": self.request.user,  # get_user_model().objects.filter(groups__name='order_admin').first(),
                "current_state_name": const.WF__ORDER__5_CURRENT_STATE_NAME,
            }

            wf = WorkFlow.objects.create(**flow_data)
            self.object.last_work_flow = wf
            self.object.extra_data.request = self.request
            self.object.save()
        if 'mohandes_confirmation' not in self.request.POST and self.state_index == 2 and 'change_user' not in self.request.POST and 'back' not in self.request.POST and 'next' in self.request.POST:
            flow_data = {
                "wf_status": 3,  # next
                "action": 'ایجاد خودکار',
                "flow_name": 'سفارش',
                "state": const.WF__ORDER__4_STATE,
                "wf_description": "بدون نیاز به تایید مهندس",
                "belong_to_group": 'trade_order',
                "object_id": self.object.pk,
                "content_type": ContentType.objects.get_for_model(self.object),
                "creator_user": self.request.user,
                "editor_user": self.request.user,
                "from_user": self.request.user,
                "to_user": self.request.user,  # get_user_model().objects.filter(groups__name='order_admin').first(),
                "current_state_name": const.WF__ORDER__5_CURRENT_STATE_NAME,
            }

            wf = WorkFlow.objects.create(**flow_data)
            self.object.last_work_flow = wf
            self.object.extra_data.request = self.request
            self.object.save()
        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        context['trade_price_list'] = self.object.item.items.filter(active=True) if self.object else []
        if self.state_index == 7:
            context['packing_items'] = PackingItem.objects.filter(order=self.object).order_by('-id')
            context['gio_items'] = GIOItem.objects.filter(order=self.object).order_by('-id')
            context['payment_items'] = OrderPaymentItem.objects.filter(order=self.object).order_by('-id')
            # context['payment_items'] = OrderPaymentItem.objects.filter(order=self.object).annotate(Sum(')).order_by('-id')
        return context


class BazarBuyFactorView(LoginRequiredMixin, View):
    template_name = 'order/bazar_view.html'
    form_class = OrderForm
    model = Order
    # wf_last_step_is_open = True
    has_flow = False
    form_struct = {
        'form': OrderForm,
        'childes': [
            {},
        ]
    }
    # flow_config = Base.get_flow_config(settings.BASE_DIR/'_keenthemes/view_config.json', 'OrderView')

    def get_success_url(self):
        return reverse_lazy('order:bazar_order.view', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        invoice_form = BazarBuyFactorForm(request.POST)
        item_formset = BazarPurchaseItemFormSet(request.POST)

        if invoice_form.is_valid() and item_formset.is_valid():
            invoice_data = invoice_form.cleaned_data
            items_data = [f.cleaned_data for f in item_formset if f.cleaned_data]
            print(invoice_data, items_data)
            # اینجا می‌تونی پردازش دلخواه رو انجام بدی
            return self.get_success_url()
        return super().post(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        invoice_form = BazarBuyFactorForm()
        item_formset = BazarPurchaseItemFormSet()

        context = {
            'form': invoice_form,
            'formset': item_formset,
        }
        return render(request, self.template_name, context)

    def form_valid(self, form):
        res = super().form_valid(form)
        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        return context


class TradeBuyFactorView(LoginRequiredMixin, View):
    template_name = 'order/trade_buy_factor_view.html'
    form_class = OrderForm
    model = Order
    # wf_last_step_is_open = True
    has_flow = False
    form_struct = {
        'form': OrderForm,
        'childes': [
            {},
        ]
    }
    # flow_config = Base.get_flow_config(settings.BASE_DIR/'_keenthemes/view_config.json', 'OrderView')

    def get_success_url(self):
        return reverse_lazy('order:bazar_order.view', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        invoice_form = TradeBuyFactorForm(request.POST)
        item_formset = TradePurchaseItemFormSet(request.POST)

        if invoice_form.is_valid() and item_formset.is_valid():
            invoice_data = invoice_form.cleaned_data
            items_data = [f.cleaned_data for f in item_formset if f.cleaned_data]
            print(invoice_data, items_data)
            # اینجا می‌تونی پردازش دلخواه رو انجام بدی
            return self.get_success_url()
        return super().post(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        invoice_form = TradeBuyFactorForm()
        item_formset = TradePurchaseItemFormSet()

        context = {
            'form': invoice_form,
            'formset': item_formset,
        }
        return render(request, self.template_name, context)

    def form_valid(self, form):
        res = super().form_valid(form)
        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        return context


class OrderListView(LoginRequiredMixin, ListView):
    model = Order
    template_name = 'order/list.html'


class OrderDataTableListView(AjaxDatatableView):
    model = Order
    title = 'order_list'
    initial_order = [["created_date", "des"], ]
    length_menu = [[10, 20, 50, -1], [10, 20, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'
    show_column_filters = True
    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'id', 'title': "id", 'orderable': True, 'visible': True, },
        {'name': 'order_title', 'orderable': True, 'visible': True, },
        {'name': 'order_method', 'orderable': False, 'visible': True, 'searchable': False},
        {'name': 'last_work_flow', 'title': 'status', 'visible': True, 'orderable': True,
         'lookup_field': '__current_state_name__icontains'},
        {'name': 'estimated_arrive_date', 'title': 'Estimated Arrive Date', 'visible': True},
        {'name': 'creator_user', 'title': 'creator_user', 'visible': True, 'orderable': True, 'lookup_field': '__username__icontains'},
        {'name': 'order_number', 'orderable': True, 'title': 'Order No', 'visible': True},
        {'name': 'item', 'orderable': True, 'title': 'SKU', 'visible': True, 'lookup_field': '__sku__icontains'},
        {'name': 'part_number_s', 'orderable': True, 'title': 'Part Number(S)', 'visible': True, 'lookup_field': '__part_number__icontains'},
        {'name': 'qi__quotation__customer_party_id', 'orderable': True, 'title': 'Customer', 'visible': True, 'lookup_field': '__title__icontains'},
        {'name': 'item_trade', 'orderable': True, 'title': 'SKU (T)', 'visible': True, 'lookup_field': '__sku__icontains'},
        {'name': 'item_trade__part_number', 'orderable': True, 'title': 'part number(T)', 'visible': True, 'lookup_field': '__icontains'},
        {'name': 'qi__quotation__id', 'orderable': True, 'title': 'Pre Invoice No', 'visible': True, 'lookup_field': '__icontains'},
        {'name': 'created_date', 'orderable': True, 'visible': True, },
        {'name': 'transportation_method', 'orderable': True, 'visible': True, 'title': 'Transportation Method'},
        {'name': 'quantity', 'orderable': True, 'visible': True, 'title': 'Request Qty', },
        {'name': 'description_sale', 'orderable': True, 'visible': True, 'title': 'Sales Description'},
        # {'name': 'xxx', 'orderable': True, 'visible': True, 'title': 'دلیل تاخیر'},
        {'name': 'quantity_trade', 'orderable': True, 'visible': True, 'title': 'Order Qty (T)', },
        {'name': 'co_conf', 'orderable': False, 'visible': True, 'title': 'زمان تایید مهندس', },
    ]

    def get_initial_queryset(self, request=None):
        qs = self.model.get_qs(self.request, lst=False)  # super().get_initial_queryset(request)
        # if request.user.is_superuser:
        #     return qs

        q = request.POST.get('q')
        user_group = request.user.base_group
        if user_group == 'trade':
            user_groups = request.user.groups.filter(name='trade_user')
        elif user_group == 'bazar':
            user_groups = request.user.groups.filter(name='bazar_user')
            qs = self.model.objects.filter(is_bazar=True)
            return qs
        else:
            user_groups = None
        # elif user_groups == 'sales':
        #     user_groups = request.user.groups.filter(name='sales_user')
        if user_groups:
            qs = self.model.get_qs(self.request, lst=False, groups_list=user_groups)
        else:
            qs = self.model.get_qs(self.request, lst=False)

        if q == 'all':
            qs = qs
        elif q == 'dependent':
            qs = qs.filter(cancel=True, last_work_flow__current_state_name='تایید مدیر فروش')
        elif q == 'sales_admin':
            qs = qs.filter(cancel=False, last_work_flow__current_state_name='تایید مدیر فروش')
        elif user_groups and (q == 'bazar_user' or 'bazar_user' in user_groups):
            qs = qs.filter(is_bazar=True)
        elif q == 'not_complete':
            not_complete_order = Q()
            qs = self.model.get_qs(self.request, lst=False).filter(cancel=True)
            for order in qs:
                not_complete = 0
                for item in order.order_base_items.all():
                    not_complete += item.quantity
                res = not_complete - order.quantity
                if res < 0:
                    not_complete_order |= Q(id=order.id)
            return Order.objects.filter(not_complete_order) if not_complete_order else Order.objects.none()
        elif q == 'bazar_user':
            qs = qs.filter(is_bazar=True)
        elif q == 'is_wh':
            qs = qs.filter(is_wh=True)
        elif q == 'is_trade':
            qs = self.model.get_qs(self.request, lst=False, groups_list=user_groups).filter(is_wh=False, is_bazar=False)
            # return qs.filter(is_wh=False, is_bazar=False, cancel=False).filter(~Q(last_work_flow__current_state_name='تایید مدیر فروش') & ~Q(last_work_flow__current_state_name='پیش نویس'))

        # if request.user.groups.filter(name='trade_user'):
        #     return self.model.get_qs(self.request, lst=False, groups_list=user_groups)
        #     return qs.filter(is_wh=False, is_bazar=False, cancel=False)

        # else:
        #     return self.model.get_qs(self.request, lst=False, groups_list=user_groups)
        #     return qs
        return qs

    def customize_row(self, row, obj):
        row['order_method'] = f'<span>{obj.order_method}</span>'
        row['part_number_s'] = f'<span>{obj.item.part_number}</span>' if obj.item else ""
        row['qi__quotation__customer_party_id'] = f'<span>{obj.qi.quotation.customer_party_id.title}</span>' if obj.qi else ""
        row['qi__quotation__id'] = f'<span>{obj.qi.quotation.id}</span>' if obj.qi else ""
        row['item_trade__part_number'] = f'<span>{obj.item_trade.part_number}</span>' if obj.item_trade else ""
        o = obj.workflows.filter(current_state_name='تایید مهندس').first()
        row['co_conf'] = f'<span>{o.created_date.strftime("%Y-%b-%d %H:%m")}</span>' if o else ""

        row['order_number'] = '<a class="fw-bold" target=_blank href="%s">%s</a>' % (
            reverse('order:order.view', args=(obj.id,)),
            obj.order_number if obj.order_number else 'بدون عنوان'
        )
        row['qi'] = f'<span>{obj.qi.quotation.customer_party_id.title}</span>' if obj.qi else ""
        row['qi__quotation'] = f'<span>{obj.qi.quotation.id}</span>' if obj.qi else ""
        row['estimated_arrive_date'] = obj.estimate_arrive_at
        # row['edit'] = mark_safe(f"""
        # <a href="#" target="_blank" class="me-3 edit-packing-item tooltip_" data-url="/order/packingitem/update/1/" data-bs-toggle="modal" data-bs-target="#id_kt_empty_modal_lg">
        #     <i class="ki-duotone ki-pencil fs-2 text-info">
        #         <span class="path1"></span>
        #         <span class="path2"></span>
        #     </i>
        # </a>
        # """)
        
    def get_column_defs(self, request):
        if self.request.user.base_group == 'bazar':
            self.column_defs = [
                AjaxDatatableView.render_row_tools_column_def(),
                {'name': 'id', 'title': "شناسه", 'orderable': True, 'visible': True, },
                {'name': 'order_number', 'orderable': True, 'title': 'Order No', 'visible': True},
                {'name': 'order_title', 'orderable': True, 'visible': True, 'title': "عنوان سفارش"},
                {'name': 'last_work_flow', 'title': 'وضعیت', 'visible': True, 'orderable': True, 'lookup_field': '__current_state_name__icontains'},
                {'name': 'item', 'orderable': True, 'title': 'کد کالا', 'visible': True, 'lookup_field': '__sku__icontains'},
                {'name': 'part_number_s', 'orderable': True, 'title': 'پارت نامبر', 'visible': True, 'lookup_field': '__part_number__icontains'},
                # {'name': 'qi__quotation__customer_party_id', 'orderable': True, 'title': 'مشتری', 'visible': True, 'lookup_field': '__title__icontains'},
                {'name': 'qi__quotation__id', 'orderable': True, 'title': 'پیش فاکتور', 'visible': True, 'lookup_field': '__icontains'},
                {'name': 'created_date', 'orderable': True, 'visible': True, },
                {'name': 'quantity', 'orderable': True, 'visible': True, 'title': 'تعداد', },
                {'name': 'description_sale', 'orderable': True, 'visible': True, 'title': 'توضیحات فروش'},
            ]
        elif self.request.user.base_group == 'sales':
            self.column_defs = [
                AjaxDatatableView.render_row_tools_column_def(),
                {'name': 'id', 'title': "id", 'orderable': True, 'visible': True, },
                {'name': 'order_number', 'orderable': True, 'title': 'Order No', 'visible': True},
                {'name': 'order_title', 'orderable': False, 'visible': True, },
                {'name': 'order_method', 'title': 'Order Type', 'visible': True, 'searchable': False, 'orderable': False, },
                {'name': 'last_work_flow', 'title': 'status', 'visible': True, 'orderable': True, 'lookup_field': '__current_state_name__icontains'},
                {'name': 'estimated_arrive_date', 'title': 'Estimated Arrive Date', 'visible': True, 'searchable': False, 'orderable': False, },
                {'name': 'creator_user', 'title': 'creator_user', 'visible': True, 'orderable': True},
                {'name': 'item', 'orderable': True, 'title': 'SKU', 'visible': True, 'lookup_field': '__sku__icontains'},
                {'name': 'part_number_s', 'orderable': True, 'title': 'Part Number(S)', 'visible': True, 'lookup_field': '__part_number__icontains'},
                {'name': 'qi__quotation__customer_party_id', 'orderable': True, 'title': 'Customer', 'visible': True, 'lookup_field': '__title__icontains'},
                {'name': 'item_trade', 'orderable': True, 'title': 'SKU (T)', 'visible': True, 'lookup_field': '__sku__icontains'},
                {'name': 'item_trade__part_number', 'orderable': True, 'title': 'part number(T)', 'visible': True, 'lookup_field': '__icontains'},
                {'name': 'qi__quotation__id', 'orderable': True, 'title': 'Pre Invoice No', 'visible': True, 'lookup_field': '__icontains'},
                {'name': 'created_date', 'orderable': True, 'visible': True, },
                {'name': 'transportation_method', 'orderable': True, 'visible': True, 'title': 'Transportation Method'},
                {'name': 'quantity', 'orderable': True, 'visible': True, 'title': 'Request Qty', },
                {'name': 'description_sale', 'orderable': True, 'visible': True, 'title': 'Sales Description'},
                {'name': 'quantity_trade', 'orderable': True, 'visible': True, 'title': 'Order Qty (T)', },
                {'name': 'co_conf', 'orderable': False, 'visible': True, 'title': 'زمان تایید مهندس', },
            ]
        elif self.request.user.base_group == 'trade':
            self.column_defs = [
                AjaxDatatableView.render_row_tools_column_def(),
                {'name': 'id', 'title': "id", 'orderable': True, 'visible': True, },
                {'name': 'order_number', 'orderable': True, 'title': 'Order No', 'visible': True},
                {'name': 'order_title', 'orderable': False, 'visible': True, },
                {'name': 'order_method', 'title': 'Order Type', 'visible': True, 'searchable': False, 'orderable': False,},
                {'name': 'last_work_flow', 'title': 'status', 'visible': True, 'orderable': True,
                 'lookup_field': '__current_state_name__icontains'},
                {'name': 'estimated_arrive_date', 'title': 'Estimated Arrive Date', 'visible': True, 'searchable': False, 'orderable': False,},
                {'name': 'creator_user', 'title': 'creator_user', 'visible': True, 'orderable': True},
                {'name': 'item', 'orderable': True, 'title': 'SKU', 'visible': True, 'lookup_field': '__sku__icontains'},
                {'name': 'part_number_s', 'orderable': True, 'title': 'Part Number(S)', 'visible': True, 'lookup_field': '__part_number__icontains'},
                # {'name': 'qi__quotation__customer_party_id', 'orderable': True, 'title': 'Customer', 'visible': True, 'lookup_field': '__title__icontains'},
                {'name': 'item_trade', 'orderable': True, 'title': 'SKU (T)', 'visible': True, 'lookup_field': '__sku__icontains'},
                {'name': 'item_trade__part_number', 'orderable': True, 'title': 'part number(T)', 'visible': True, 'lookup_field': '__icontains'},
                {'name': 'qi__quotation__id', 'orderable': True, 'title': 'Pre Invoice No', 'visible': True, 'lookup_field': '__icontains'},
                {'name': 'created_date', 'orderable': True, 'visible': True, },
                {'name': 'transportation_method', 'orderable': True, 'visible': True, 'title': 'Transportation Method'},
                {'name': 'quantity', 'orderable': True, 'visible': True, 'title': 'Request Qty', },
                {'name': 'description_sale', 'orderable': True, 'visible': True, 'title': 'Sales Description'},
                {'name': 'quantity_trade', 'orderable': True, 'visible': True, 'title': 'Order Qty (T)', },
                {'name': 'co_conf', 'orderable': False, 'visible': True, 'title': 'زمان تایید مهندس', },
            ]

        return super().get_column_defs(request)


class BazarOrderDataTableListView(AjaxDatatableView):
    model = Order
    title = 'order_list'
    initial_order = [["id", "des"], ]
    length_menu = [[10, 25, 50, -1], [10, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'
    show_column_filters = True
    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'id', 'title': "id", 'orderable': True, 'visible': True, "className": 'id'},
        {'name': 'quantity', 'orderable': True, 'visible': True, 'title': 'تعداد', 'className': 'quantity'},
        {'name': 'buy_factor_quantity_in_sepidar', 'orderable': True, 'visible': True, 'title': '<div class="px-0">تعداد در<br>فاکتور خرید</div>', 'className': 'buy_factor_quantity_in_sepidar'},
        {'name': 'item', 'orderable': True, 'title': 'کد کالا', 'visible': True, 'lookup_field': '__sku__icontains', 'className': 'item'},
        {'name': 'item__sepidar_id_0', 'visible': True, 'className': 'itemref d-none'},
        {'name': 'part_number_s', 'orderable': True, 'title': 'نام کالا', 'visible': True,
         'lookup_field': '__part_number__icontains', 'className': 'partnumber'},
        {'name': 'qi__quotation__id', 'orderable': True, 'title': 'پیش فاکتور', 'visible': True,
         'lookup_field': '__icontains'},
        {'name': 'creator_user', 'title': 'ایجاد کننده', 'visible': True, 'orderable': True,
         'lookup_field': '__username__icontains'},
        {'name': 'created_date', 'orderable': True, 'visible': True, 'searchable': False},
        {'name': 'description_sale', 'orderable': True, 'visible': True, 'title': 'توضیحات'},
        {'name': 'buy_factor', 'orderable': False, 'visible': True, 'title': '<div class="px-0">فاکتور خرید</div>', },
    ]

    def get_initial_queryset(self, request=None):
        qs = self.model.objects.filter(is_bazar=True, is_deleted=False, is_wh=False).filter(
            Q(buy_factor_quantity_in_sepidar__lt=F('quantity')) | Q(buy_factor_quantity_in_sepidar__isnull=True)
        )
        return qs

    def customize_row(self, row, obj):
        from tools.utils import to_jalali_date
        row['created_date'] = to_jalali_date(obj.created_date)
        row['item__sepidar_id_0'] = obj.item.sepidar_id_0
        row['order_method'] = f'<span>{obj.order_method}</span>'
        row['part_number_s'] = f'<span>{obj.item.part_number}</span>' if obj.item else ""
        row['qi__quotation__customer_party_id'] = f'<span>{obj.qi.quotation.customer_party_id.title}</span>' if obj.qi else ""
        row['qi__quotation__id'] = f'<span>{obj.qi.quotation.id}</span>' if obj.qi else ""
        row['estimated_arrive_date'] = obj.estimate_arrive_at
        row['buy_factor'] = '<span class="fw-bold p-3 cursor-pointer font-size-20 action" onclick="bazar_buy_factor(event);calculate_price()" >➕</span>'


class TradeOrderDataTableListView(AjaxDatatableView):
    model = Order
    title = 'order_list'
    initial_order = [["id", "des"], ]
    length_menu = [[10, 25, 50, -1], [10, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'
    show_column_filters = True
    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'id', 'title': "id", 'orderable': True, 'visible': True, "className": 'id'},
        {'name': 'quantity', 'orderable': True, 'visible': True, 'title': 'تعداد', 'className': 'quantity'},
        {'name': 'buy_factor_quantity_in_sepidar', 'orderable': True, 'visible': True, 'title': '<div class="px-0">تعداد در<br>فاکتور خرید</div>', 'className': 'buy_factor_quantity_in_sepidar'},
        {'name': 'item', 'orderable': True, 'title': 'کد کالا', 'visible': True, 'lookup_field': '__sku__icontains', 'className': 'item'},
        {'name': 'item__sepidar_id_0', 'visible': True, 'className': 'itemref d-none'},
        {'name': 'part_number_s', 'orderable': True, 'title': 'نام کالا', 'visible': True,
         'lookup_field': '__part_number__icontains', 'className': 'partnumber'},
        {'name': 'qi__quotation__id', 'orderable': True, 'title': 'پیش فاکتور', 'visible': True,
         'lookup_field': '__icontains'},
        {'name': 'creator_user', 'title': 'ایجاد کننده', 'visible': True, 'orderable': True,
         'lookup_field': '__username__icontains'},
        {'name': 'created_date', 'orderable': True, 'visible': True, 'searchable': False},
        {'name': 'description_sale', 'orderable': True, 'visible': True, 'title': 'توضیحات'},
        {'name': 'buy_factor', 'orderable': False, 'visible': True, 'title': '<div class="px-0">فاکتور خرید</div>', },
    ]

    def get_initial_queryset(self, request=None):
        qs = self.model.objects.filter(is_bazar=False, is_deleted=False, is_wh=False).filter(
            Q(buy_factor_quantity_in_sepidar__lt=F('quantity')) | Q(buy_factor_quantity_in_sepidar__isnull=True)
        )
        return qs

    def customize_row(self, row, obj):
        from tools.utils import to_jalali_date
        row['created_date'] = to_jalali_date(obj.created_date)
        row['item__sepidar_id_0'] = obj.item.sepidar_id_0
        row['order_method'] = f'<span>{obj.order_method}</span>'
        row['part_number_s'] = f'<span>{obj.item.part_number}</span>' if obj.item else ""
        row['qi__quotation__customer_party_id'] = f'<span>{obj.qi.quotation.customer_party_id.title}</span>' if obj.qi else ""
        row['qi__quotation__id'] = f'<span>{obj.qi.quotation.id}</span>' if obj.qi else ""
        row['estimated_arrive_date'] = obj.estimate_arrive_at
        row['buy_factor'] = '<span class="fw-bold p-3 cursor-pointer font-size-20 action" onclick="bazar_buy_factor(event);calculate_price()" >➕</span>'


class OrderAction(ListView):
    model = Order
    template_name = 'order/order_action.html'
    paginate_by = 50

    def get_queryset(self):
        x = Order.objects.filter(order_base_items__isnull=False).distinct()
        return x

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(**kwargs)
        context['forms'] = []
        for o in context['object_list']:
            f = OrderForm(instance=o)
            context['forms'].append(f)
        context['form'] = True
        return context


def ajax_order_order_add(request):
    import json
    data = json.loads(request.body)
    data['creator_user'] = request.user
    data['editor_user'] = request.user
    quantity = data.get('quantity')
    obj, created = OrderOrder.objects.get_or_create(defaults=data, order_base_id=data.get('order_base_id'), order_rel_id=data.get('order_rel_id'))
    if quantity and not created:
        obj.quantity += quantity
        obj.save()
    form = OrderForm(instance=obj.order_base)
    html = render_to_string('order/partial/order_order_report.html', context={'form': form})
    return JsonResponse({'res': html})


class PackingView(LoginRequiredMixin, BaseView):
    template_name = 'order/packing_view.html'
    form_class = PackingForm
    model = Packing
    wf_last_step_is_open = True
    has_flow = True
    success_message = 'با موفقیت ذخیره شد'
    form_struct = {
        'form': PackingForm,
        'childes': [
            {
                'form': PackingItemForm,
                'childes': [{}]
            },
        ]
    }
    flow_config = Base.get_flow_config(settings.BASE_DIR/'_keenthemes/view_config.json', 'PackingView')

    def get_success_url(self):
        return reverse_lazy('order:packing.update', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        res = super().form_valid(form)
        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        return context


class packing_list_form(LoginRequiredMixin, BaseView):
    template_name = 'order/packing_item_form.html'
    form_class = PackingItemForm
    model = PackingItem
    # wf_last_step_is_open = True
    # has_flow = False
    form_struct = {
        'form': PackingItemForm,
        'childes': [
            {},
        ]
    }
    # flow_config = Base.get_flow_config(settings.BASE_DIR/'_keenthemes/view_config.json', 'PackingView')

    def get_success_url(self):
        return reverse_lazy('order:packingitem.update', kwargs={'pk': self.object.packing.pk})

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
            # packing = Packing.objects.filter(pk=self.request.GET.get('pk')).first()
            # form = PackingItemForm(initial={'packing': packing or self.object.packing}, instance=self.object)
            # context = self.get_context_data()
            # context = {}
            # context['form'] = form
            res = render_to_string(self.template_name, context=self.get_context_data())
            return JsonResponse({'res': res})
        return JsonResponse({'res': 'only ajax request'})

    def get_context_data(self, **kwargs):
        context = {}
        # context = super().get_context_data(**kwargs)
        packing = Packing.objects.filter(pk=self.request.GET.get('pk')).first()
        form = PackingItemForm(initial={'packing': packing or self.object.packing}, instance=self.object)
        context['app_name'] = self.request.resolver_match.app_name
        context['form'] = form
        return context


class PackingListView(LoginRequiredMixin, ListView):
    """
    sku list view
    """
    model = Packing
    template_name = 'order/packing_list.html'
    context_object_name = 'items'


class PackingDataTableListView(AjaxDatatableView):
    model = Packing
    title = 'packing'
    initial_order = [["created_date", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'id', 'visible': False, 'title': "packing_id", 'className': 'py-1', },
        {'name': 'pk', 'visible': True, 'title': _('id'), 'className': 'py-1', },
        # {'name': 'packing', 'visible': True, 'title': 'packing_id', 'className': 'py-1', },
        {'name': 'carton_qty', 'visible': True, 'title': "Carton Qty", 'className': 'py-1', },
        {'name': 'weight', 'visible': True, 'title': "weight(KG)", 'className': 'py-1', },
        {'name': 'packing_number', 'visible': True, 'title': "packing_no", 'className': 'py-1', },
        {'name': 'created_date', 'visible': True, 'title': "pack_date", 'className': 'py-1', },
        {'name': 'shipment_type', 'visible': True, 'title': "shipment type", 'className': 'py-1', },
        {'name': 'bl_number', 'title': "BL Number", 'className': 'py-1', },
        {'name': 'departure_date', 'title': "<div style='width:100px:'>Departure from origin port Date</div>", 'className': 'py-1', },
        {'name': 'arrival_date', 'title': "Arrival to destination port Date", 'className': 'py-1', },
        {'name': 'sales_manager_needed', 'title': "Sales manager Needed", 'className': 'py-1', },
        {'name': 'sales_manager_check_date', 'title': "Sales manager check Date", 'className': 'py-1', },
        {'name': 'delivery_to_salehi_date', 'title': "Delivered to Mr Salehi Date", 'className': 'py-1', },
        {'name': 'cl_90_date', 'title': "Clearance Date 90%", 'className': 'py-1', },
        {'name': 'cl_10_date', 'title': "Clearance Date 10%", 'className': 'py-1', },
        {'name': 'cl_100_date', 'title': "Clearance Date 100%", 'className': 'py-1', },
        {'name': 'arrive_to_wh_date', 'title': "Arrive to wherehouse Date", 'className': 'py-1', },
        {'name': 'estimated_delivery_date', 'title': "Est Delivery Date", 'className': 'py-1', },
        {'name': 'creator_user', 'title': _('creator_user'), 'className': 'py-1', },
    ]

    def customize_row(self, row, obj):
        row['pk'] = '<a class="fw-bold" target=_blank href="%s">%s</a>' % (
            reverse('order:packing.update', args=(obj.id,)),
            obj.id if obj.id else 'بدون عنوان'
        )
        row['carton_qty'] = f'{obj.computed_carton_qty}' if obj.computed_carton_qty else '-'
        row['weight'] = f'{obj.computed_weight_kg}' if obj.computed_weight_kg else '-'


class GIOView(LoginRequiredMixin, BaseView):
    template_name = 'order/gio_view.html'
    form_class = GIOForm
    model = GIO
    # wf_last_step_is_open = True
    # has_flow = True
    success_message = 'با موفقیت ذخیره شد'
    form_struct = {
        'form': GIOForm,
        'childes': [
            {},
        ]
    }
    # flow_config = Base.get_flow_config(settings.BASE_DIR/'_keenthemes/view_config.json', 'GIOView')

    def get_success_url(self):
        return reverse_lazy('order:gio.update', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        res = super().form_valid(form)
        return res

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = self.request.resolver_match.app_name
        return context


class GIOItemView(LoginRequiredMixin, BaseView):
    template_name = 'order/gio_item.html'
    form_class = GIOItemForm
    model = GIOItem
    form_struct = {
        'form': GIOItemForm,
        'childes': [
            {},
        ]
    }

    def get_success_url(self):
        return reverse_lazy('order:gio.update', kwargs={'pk': self.object.gio.pk})

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
        gio = GIO.objects.filter(pk=self.request.GET.get('pk')).first()
        form = self.form_class(initial={'gio': gio or self.object.gio}, instance=self.object)
        context['app_name'] = self.request.resolver_match.app_name
        context['form'] = form
        return context


class GIOListView(LoginRequiredMixin, View):
    """
    sku list view
    """
    # model = Packing
    template_name = 'order/gio_list.html'
    context_object_name = 'items'

    def get(self, request, *args, **kwargs):
        context = {}
        return render(request, self.template_name, context)


class GIODataTableListView(AjaxDatatableView):
    model = GIO
    title = 'GIO'
    initial_order = [["created_date", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'id', 'visible': False, 'title': _('id'), 'className': 'py-1',},
        {'name': 'pk', 'visible': True, 'title': _('id'), 'className': 'py-1',},
        {'name': 'gio_date', 'visible': True, 'title': _('gio_date'), 'className': 'py-1',},
        {'name': 'gioitems__order', 'visible': True, 'title': _('Order'), 'className': 'py-1'},
        {'name': 'creator_user', 'title': _('creator_user'), 'className': 'py-1', },
        {'name': 'created_date', 'orderable': True, 'visible': True, },
    ]

    def customize_row(self, row, obj):
        row['pk'] = '<a class="fw-bold" target=_blank href="%s">%s</a>' % (
            reverse('order:gio.update', args=(obj.id,)),
            obj.id if obj.id else 'بدون عنوان'
        )
        order_ids = list(set(obj.gioitems.filter(order__isnull=False).values_list('order_id', flat=True)))
        order_links = [
            f'<a class="fw-bold" target=_blank href="{reverse("order:order.view", args=(order_id,))}">{order_id}</a>'
            for order_id in order_ids
        ]
        row['gioitems__order'] = ", ".join(order_links)


class PaymentView(LoginRequiredMixin, BaseView):
    template_name = 'order/payment_view.html'
    form_class = OrderPaymentForm
    model = OrderPayment
    wf_last_step_is_open = True
    has_flow = True
    has_formset = True
    formset_form = OrderPaymentItemFormSet
    formset_model = OrderPaymentItem
    formset_fk_field = 'payment'
    related_name_fk = 'payment_item'
    success_message = 'با موفقیت ذخیره شد'
    form_struct = {
        'form': OrderPaymentForm,
        'childes': [
            {
                'form': OrderPaymentItemFormSet,
                'childes': [{}]
            },
        ]
    }
    flow_config = Base.get_flow_config(settings.BASE_DIR/'_keenthemes/view_config.json', 'PaymentView')

    def get_success_url(self):
        return reverse_lazy('order:order.payment.update', kwargs={'pk': self.object.pk})

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
    template_name = 'order/payment_item_view.html'
    form_class = OrderPaymentItemForm
    model = OrderPaymentItem
    form_struct = {
        'form': OrderPaymentItemForm,
        'childes': [
            {},
        ]
    }

    def get_success_url(self):
        return reverse_lazy('order:order.paymentitem.update', kwargs={'pk': self.object.payment.pk})

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
        payment = OrderPayment.objects.filter(pk=self.request.GET.get('pk')).first()
        form = self.form_class(initial={'payment': payment or self.object.payment}, instance=self.object)
        context['app_name'] = self.request.resolver_match.app_name
        context['form'] = form
        return context


class PaymentListView(LoginRequiredMixin, View):
    """
    sku list view
    """
    model = OrderPayment
    template_name = 'order/payment_list.html'
    context_object_name = 'items'

    def get(self, request, *args, **kwargs):
        context = {}
        return render(request, self.template_name, context)


class PaymentDataTableListView(AjaxDatatableView):
    model = OrderPayment
    title = 'Payment'
    initial_order = [["created_date", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'id', 'visible': False, 'title': _('id'), 'className': 'py-1',},
        {'name': 'pk', 'visible': True, 'title': _('id'), 'className': 'py-1',},
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
            reverse('order:order.payment.update', args=(obj.id,)),
            obj.id if obj.id else 'بدون عنوان'
        )


class PaymentItemListView(LoginRequiredMixin, View):
    """
    sku list view
    """
    model = OrderPaymentItem
    template_name = 'order/payment_item_list.html'
    context_object_name = 'items'

    def get(self, request, *args, **kwargs):
        context = {}
        return render(request, self.template_name, context)


class PaymentItemDataTableListView(AjaxDatatableView):
    model = OrderPaymentItem
    title = 'PaymentItem'
    initial_order = [["created_date", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'id', 'visible': False, 'title': _('id'), 'className': '', },
        {'name': 'pk', 'visible': True, 'title': _('id'), 'className': '', },
        {'name': 'order__order_number', 'visible': True, 'title': 'Order-NO', 'className': '', },
        {'name': 'created_date', 'visible': True, 'title': 'Date', 'className': '', },
        {'name': 'order__supplier_trade', 'visible': True, 'title': 'Supplier', 'className': '', 'lookup_field': '__title__icontains', },
        {'name': 'order__po_number_trade', 'visible': True, 'title': 'PO NO.', 'lookup_field': '__icontains', 'searchable': True},
        {'name': 'order__transportation_method', 'visible': True, 'title': 'EXP', },
        {'name': 'order__item', 'visible': True, 'title': 'Part NO.', 'lookup_field': '__part_number__icontains'},
        {'name': 'order__quantity_trade', 'visible': True, 'title': 'QTY', 'className': '', },
        {'name': 'order__price_trade', 'visible': True, 'title': 'Price', 'className': '', },
        {'name': 'order_total_price', 'visible': True, 'title': 'Total', 'className': '', },

        # {'name': 'destination_currency', 'visible': True, 'title': 'Destination Currency', 'className': '', },
        {'name': 'payment__currency', 'visible': True, 'title': 'Destination Currency', 'className': '', 'lookup_field': '__title__icontains',  },
        {'name': 'order__currency', 'visible': True, 'title': 'Currency', 'className': '', 'lookup_field': '__title__icontains', },
        {'name': 'exchange_rate', 'visible': True, 'title': 'Rate', 'className': '', },
        {'name': 'total_amount', 'visible': True, 'title': 'Amount', 'className': '', },
        {'name': 'from_date', 'visible': True, 'title': 'Pay Date', 'className': '', },
        {'name': 'bank', 'visible': True, 'title': 'Bank Info', 'className': '', },
        {'name': 'paid_amount', 'visible': True, 'title': '<div class="px-8">Paid Amount</div>', 'className': '', },
        {'name': 'reference', 'visible': True, 'title': 'Reference', 'className': '', },
        {'name': 'attachment', 'visible': True, 'title': '<div class="px-6">Files</div>', 'className': '', },
        {'name': 'action', 'visible': True, 'title': '<div class="px-8">Action</div>', 'className': '', },
    ]

    def get_initial_queryset(self, request=None):
        payment_pk: str = self.request.POST.get('q')
        if payment_pk.isdigit():
            qs = self.model.objects.filter(payment=payment_pk)
        else:
            qs = self.model.objects.all()
        return qs

    def customize_row(self, row, obj):
        row['order__order_number'] = '<a class="fw-bold" href="%s">%s</a>' % (
            reverse('order:order.paymentitem.update', args=(obj.id,)),
            obj.order.order_number if obj.order else '_'
        )
        row['payment__currency'] = f'{obj.payment.currency}' if obj.payment else '_'
        row['order__supplier_trade'] = f'{obj.order.supplier_trade}' if obj.order.supplier_trade else '_'

        row['order__po_number_trade'] = f'{obj.order.po_number_trade}' if obj.order.po_number_trade else '_'

        row['order__transportation_method'] = '<a class="fw-bold" href="%s">%s</a>' % (
            reverse('order:order.paymentitem.update', args=(obj.id,)),
            obj.order.transportation_method if obj.order else '_'
        )

        row['order__item'] = '<a class="fw-bold" href="%s">%s</a>' % (
            reverse('order:order.paymentitem.update', args=(obj.id,)),
            obj.order.item.part_number if obj.order.item else '_'
        )

        row['order__quantity_trade'] = '<a class="fw-bold" href="%s">%s</a>' % (
            reverse('order:order.paymentitem.update', args=(obj.id,)),
            obj.order.quantity_trade if obj.order else '_'
        )

        row['order__price_trade'] = '<a class="fw-bold" href="%s">%s</a>' % (
            reverse('order:order.paymentitem.update', args=(obj.id,)),
            obj.order.price_trade if obj.order else '_'
        )

        row['order_total_price'] = '<a class="fw-bold" href="%s">%s</a>' % (
            reverse('order:order.paymentitem.update', args=(obj.id,)),
            round(obj.order.total_price, 4) if obj.order else '_'
        )

        row['order__currency'] = '<a class="fw-bold" href="%s">%s</a>' % (
            reverse('order:order.paymentitem.update', args=(obj.id,)),
            obj.order.currency if obj.order else '_'
        )

        row['paid_amount'] = f'{obj.total_amount/obj.exchange_rate:0.5f}'
        row['reference'] = '111'

        row['attachment'] = ""
        for file in obj.files.all():
            row['attachment'] += f"""<a href="{file.path.url}" class="me-2" target="_blank"><i class="fas fa-file-upload icon-lg fs-4"></i></a>"""

        row['action'] = f"""
            <span>
                <a href="#" target="_blank" class="edit-payment-item tooltip_" onclick="edit_with_modal(this)" data-url="{ reverse('order:order.paymentitem.update', kwargs={'pk': obj.pk})}" data-bs-toggle="modal" data-bs-target="#id_kt_empty_modal_lg">
                    <span class="tooltiptext">ویرایش</span>
                    <i class="ki-duotone ki-pencil fs-3 text-info">
                        <span class="path1"></span>
                        <span class="path2"></span>
                    </i>
                </a>
                <a class="tooltip_ cursor-pointer" onclick="change_log_with_modal(this)"
                    data-bs-toggle="modal"
                    data-bs-target="#id_kt_empty_modal_lg"
                    data-model_name="{self.model.__name__}"
                    data-object_id="{obj.pk}"
                    data-app_name="{self.request.resolver_match.app_name}"
                    name="name_change_log">
                    <span class="tooltiptext">تاریخچه تغییرات</span>
                    <i class="ki-duotone ki-book-open fs-3 text-primary">
                     <span class="path1"></span>
                     <span class="path2"></span>
                     <span class="path3"></span>
                     <span class="path4"></span>
                    </i>
                </a>
                <a href="#" target="_blank" class="me-3 delete-payment-item text-danger tooltip_" onclick="delete_with_modal(this)" data-url="{reverse('core:delete.confirm')}?model={self.model.__name__}&object_id={obj.pk}&app_label={self.request.resolver_match.app_name}" data-bs-toggle="modal" data-bs-target="#id_kt_empty_modal_sm">
                    <span class="tooltiptext">حذف</span>
                    <i class="ki-duotone ki-trash fs-3 text-danger">
                        <span class="path1"></span>
                        <span class="path2"></span>
                        <span class="path3"></span>
                        <span class="path4"></span>
                        <span class="path5"></span>
                    </i>
                </a>
            </span>
        """


class CustomerRequestOrderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasShopPermission]
    queryset = Order.objects.all().order_by('-created_date')
    serializer_class = OrderSerializer
    http_method_names = ['get']

    @action(detail=False, methods=['get'], url_path='by-request/(?P<customer_request_id>[^/.]+)')
    def list_by_request(self, request, customer_request_id=None):
        queryset = self.get_queryset().filter(customer_request_item_id=customer_request_id)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def list(self, request, *args, **kwargs):
        return JsonResponse({'detail': 'url with "pk" required'})


class SubmitBuyFactor(View):
    def post(self, request, *args, **kwargs):
        from tools import utils
        try:
            body = self.request.body or '{}'
            data = json.loads(body)
            grouped = utils.grouped_value(data, target_suffixes=('portal_order_id', '-quantity', '-itemref'))
            res = SepidarApiCall.buy_factor_to_sepidar(obj=data, request=self.request)
            if hasattr(res, 'errors'):
                # messages.error(self.request, res.get('errors'))
                return JsonResponse({'res': 'fail'})

            elif res and res.get('valid'):
                buy_factor_number = res.get('number')
                buy_factor_id = res.get('buy_factor_id')
                lookup = {(x[1].get('itemref'), x[1].get('quantity')): x[1] for x in grouped.items() if x[0] != '0'}
                """
                lookup output like this:
                lookup = {
                    (itemref, quantity): {itemref:'x', 'portal_order_id': 'y', 'quantity': 'z'}
                }
                """
                buy_factor_items = {key: value for x in res.get('buy_factor_items') for key, value in x.items()}
                for key, value in lookup.items():
                    buy_factor_item = buy_factor_items.get(key)
                    inventory_purchase_invoice_item_id = buy_factor_item.get('inventory_purchase_invoice_item_id')
                    order_pk = value.get('portal_order_id')
                    o = Order.objects.filter(pk=order_pk).first()
                    o.buy_factors.append({str((buy_factor_id, buy_factor_number)): (inventory_purchase_invoice_item_id, key[1])})
                    o.buy_factor_quantity_in_sepidar = (o.buy_factor_quantity_in_sepidar or 0) + int(key[1])
                    o.editor_user = self.request.user
                    o.save()
                new_btn = """
                <button 
                    type="button" 
                    id="submit-buy-factor" 
                    class="btn btn-secondary mt-5 me-5"
                    onclick="window.location.href = window.location.href">
                    جدید
                </button>
                """
                return JsonResponse({'res': f'<span class="ms-3"><span class="bg-success text-white rounded p-2">فاکتور خرید به سپیدار ارسال شد، کد: {buy_factor_number}</span></span>'}, status=201)
            else:
                return JsonResponse({'res': res}, status=400)
        except Exception as e:
            return JsonResponse({'res': {"error": e.args[0]}}, status=400)


class OrderOfFactor(BaseView):
    template = 'order/order_of_factors.html'
    model = Order

    def setup(self, request, *args, **kwargs):
        """Initialize attributes shared by all view methods."""
        if hasattr(self, "get") and not hasattr(self, "head"):
            self.head = self.get
        self.request = request
        self.args = args
        self.kwargs = kwargs
        self.flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json', 'OrderView')
        self.object = Order.objects.get(pk=kwargs.get('pk'))
        self.state_index = self.get_flow_index(self.object)

    def dispatch(self, request, *args, **kwargs):
        if kwargs.get('pk') == '0':
            return self.list(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)
    
    def list(self, request, *args, **kwargs):
        orders = self.model.objects.filter(pk__gt=100)
        forms = []
        for order in orders:
            form = dict()
            self.flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json', 'OrderView')
            self.state_index = self.get_flow_index(order)
            if order.cancel:
                form[order] = []
                m2m = order.order_m2m.distinct()
                for x in m2m:
                    oo = OrderOrder.objects.filter(order_base=order, order_rel=x,
                                                   is_deleted=False).first()
                    if not oo:
                        continue
                    x.oo = oo
                    x.flow_config = self.flow_config
                    x.state_pair = x.state(self.flow_config, self.get_flow_index(x), self.request, x)
                    form[order].append((OrderForm(instance=x), oo))
            else:
                order.state_pair = order.state(self.flow_config,
                                               self.get_flow_index(order),
                                               self.request, order)
                form = OrderForm(instance=order)

            forms.append(form)

        context = dict()
        context['factor_items'] = orders
        context['forms'] = forms
        context['access'] = True

        # if self.request.user == factor_items.first().creator_user or factor_items.first().creator_user in self.request.user.team.all():
        #     context['access'] = True

        return render(request, self.template, context)

        factor_items = (
            FactorItem.objects
            .select_related('supply_locations')
        )

        forms = []
        for fi in factor_items:
            form = dict()
            oo_list = list()
            if fi.supply_locations.cancel:
                form[fi.supply_locations] = []
                m2m = fi.supply_locations.order_m2m.distinct()
                for x in m2m:
                    oo = OrderOrder.objects.filter(order_base=fi.supply_locations, order_rel=x,
                                                   is_deleted=False).first()
                    if not oo:
                        continue
                    x.oo = oo
                    x.flow_config = self.flow_config
                    x.state_pair = x.state(self.flow_config, self.get_flow_index(x), self.request, x)
                    form[fi.supply_locations].append((OrderForm(instance=x), oo))
            else:
                fi.supply_locations.state_pair = fi.supply_locations.state(self.flow_config,
                                                                           self.get_flow_index(fi.supply_locations),
                                                                           self.request, fi.supply_locations)
                form = OrderForm(instance=fi.supply_locations)
            forms.append(form)

        context = dict()
        context['factor_items'] = factor_items
        context['forms'] = forms

        if self.request.user == factor_items.first().creator_user or factor_items.first().creator_user in self.request.user.team.all():
            context['access'] = True


        return render(request, self.template, context)

    def get(self, request, pk, *args, **kwargs):
        self.flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json', 'OrderView')
        if '__' in pk:
            pk = pk.split('__')[1]
        else:
            pk = int(pk)
        factor_items = (
            FactorItem.objects
            .select_related('supply_locations')  # join با جدول Order
            .filter(factor_id=pk)
        )

        forms = []
        for fi in factor_items:
            form = dict()
            oo_list = list()
            if fi.supply_locations.cancel:
                form[fi.supply_locations] = []
                m2m = fi.supply_locations.order_m2m.distinct()
                for x in m2m:
                    oo = OrderOrder.objects.filter(order_base=fi.supply_locations, order_rel=x, is_deleted=False).first()
                    if not oo:
                        continue
                    x.oo = oo
                    x.flow_config = self.flow_config
                    x.state_pair = x.state(self.flow_config, self.get_flow_index(x), self.request, x)
                    form[fi.supply_locations].append((OrderForm(instance=x), oo))
            else:
                fi.supply_locations.state_pair = fi.supply_locations.state(self.flow_config, self.get_flow_index(fi.supply_locations), self.request, fi.supply_locations)
                form = OrderForm(instance=fi.supply_locations)
            forms.append(form)

        context = dict()
        context['factor_items'] = factor_items
        context['forms'] = forms

        if self.request.user == factor_items.first().creator_user or factor_items.first().creator_user in self.request.user.team.all():
            context['access'] = True

        return render(request, self.template, context)

    def delete_order_order(self):
        pair_quantity = int(float((self.data.get('pair_quantity', 0))))
        main_order_pk = int(float((self.data.get('main_order_pk', 0))))
        main_order = Order.objects.filter(pk=main_order_pk).first()
        order = Order.objects.filter(pk=self.pk).first()

        if order.is_wh and main_order.order_m2m.exists():

            oo = OrderOrder.objects.filter(order_base_id=main_order_pk, order_rel_id=self.pk).first()
            oo.is_deleted = True
            oo.extra_data.request = self.request
            oo.save()
            order.is_deleted = True
            order.extra_data.request = self.request
            order.save()
        else:
            oo = OrderOrder.objects.filter(order_base_id=main_order_pk, order_rel_id=self.pk).first()
            oo.is_deleted = True
            oo.extra_data.request = self.request
            oo.save()

        # form = OrderForm(instance=order_rel)
        # html = render_to_string('order/partial/order_of_factors_row.html', context={})

        return JsonResponse({'res': ""})

    def _go_next(self, obj):
        self.state_index = self.get_flow_index(obj)
        group_name = self.flow_config.get('flow_users_groups')[self.state_index]
        next_group_name = self.flow_config.get('flow_users_groups')[self.state_index + 1]
        flow_data = {
            "wf_status": 3,  # next
            "action": 'ایجاد',
            "flow_name": 'سفارش',
            "state": self.flow_config.get('flow_state_list')[self.state_index],
            "wf_description": 'ارسال به مرحله بعد از لیست محل تامین های فاکتور',
            "belong_to_group": group_name,
            "object_id": obj.pk,
            "content_type": ContentType.objects.get_for_model(obj),
            "creator_user": self.request.user,
            "editor_user": self.request.user,
            "from_user": obj.last_work_flow.to_user,
            "to_user": self.get_flow_user(next_group_name),
            "current_state_name": obj.current_state_name(self.flow_config, self.state_index + 1),
            "deadline": timezone.now() + timedelta(days=1)
        }
        wf = WorkFlow.objects.create(**flow_data)
        obj.last_work_flow = wf
        obj.save()
        pass

    def _go_back(self, obj):
        self.state_index = self.get_flow_index(obj)
        group_name = self.flow_config.get('flow_users_groups')[self.state_index]
        back_group_name = self.flow_config.get('flow_users_groups')[self.state_index - 1]
        flow_data = {
            "wf_status": 2,  # back
            "action": 'ایجاد',
            "flow_name": 'سفارش',
            "state": self.flow_config.get('flow_state_list')[self.state_index],
            "wf_description": 'عودت از لیست محل تامین های فاکتور',
            "belong_to_group": group_name,
            "object_id": obj.pk,
            "content_type": ContentType.objects.get_for_model(obj),
            "creator_user": self.request.user,
            "editor_user": self.request.user,
            "from_user": obj.last_work_flow.to_user,
            "to_user": self.get_flow_user(back_group_name),
            "current_state_name": obj.current_state_name(self.flow_config, self.state_index - 1),
            "deadline": timezone.now() + timedelta(days=1)
        }
        wf = WorkFlow.objects.create(**flow_data)
        obj.last_work_flow = wf
        obj.save()
        pass

    def wf_action(self, obj):
        if self.submit_action == 'next':
            return self._go_next(obj)
        elif self.submit_action == 'back':
            return self._go_back(obj)

    def post(self, request, pk, *args, **kwargs):
        self.flow_config = Base.get_flow_config(settings.BASE_DIR / '_keenthemes/view_config.json', 'OrderView')
        self.state_index = self.get_flow_index(self.object)
        self.wh_code = None
        data = json.loads(self.request.body or {})
        self.data = data
        self.submit_action = self.data.get('submit_action')

        if '__' in pk:
            self.wh_code = int(pk.split('__')[1])
        else:
            self.pk = int(pk)

        if self.wh_code:
            """process wh oo"""
            pair_quantity = int(float((self.data.get('pair_quantity', 0))))
            main_order_pk = int(float((self.data.get('main_order_pk', 0))))
            main_order_obj = Order.objects.get(pk=main_order_pk)
            Order.objects.create({
                'item': main_order_obj.item
            })
            self.save_order_order()
        else:
            pair_quantity = int(float((self.data.get('pair_quantity', 0))))
            main_order_pk = int(float((self.data.get('main_order_pk', 0))))

            if self.data.get('submit_action', '') == 'delete':
                res = self.delete_order_order()
                return res

            if 'order_order' in self.data:
                res = self.save_order_order()
                main_order = res.get('main_order')
                oo = res.get('oo')
                order_rel = res.get('order_rel')
                self.wf_action(order_rel)
                order_rel.state_pair = order_rel.state(self.flow_config, self.get_flow_index(order_rel), self.request, order_rel)

                form = OrderForm(instance=order_rel)
                html = render_to_string('order/partial/order_of_factors_row.html',
                                        {'order_form': form, 'order_pair': oo, 'main_order': main_order}
                                        )

                return JsonResponse(
                    {'res': html, 'need_supply': main_order.needed_qty, 'supplied': main_order.total_supply_qty})

            if (pair_quantity or pair_quantity == 0) and main_order_pk:
                """update pair order"""
                data.pop('quantity')
                main_order = Order.objects.filter(pk=main_order_pk).first()
                order = Order.objects.filter(pk=pk).first()
                main_order_qty = main_order.quantity if main_order else 0
                total_supply_qty = main_order.total_supply_qty
                needed_qty = main_order_qty - total_supply_qty

                oo = OrderOrder.objects.filter(order_base_id=main_order_pk, order_rel_id=pk).first()
                if oo:
                    max_needed_qty = oo.quantity + needed_qty

                    order.oo = oo
                    if oo.sepidar_wh_code:
                        real_sepidar_wh_quantity = order.sepidar_wh_item_pair_quantity  # if order.is_wh else order.quantity
                        free_sepidar_wh_quantity = real_sepidar_wh_quantity - order.item.reserved_count_in_portal + oo.quantity

                        oo.quantity = min(pair_quantity, free_sepidar_wh_quantity, max_needed_qty)
                        order.quantity = min(pair_quantity, max_needed_qty, free_sepidar_wh_quantity)
                    else:
                        related_order_remaining_quantity = order.remaining_quantity  # if order.is_wh else order.quantity
                        free_related_order_quantity = related_order_remaining_quantity + oo.quantity

                        oo.quantity = min(pair_quantity, free_related_order_quantity, max_needed_qty)
                        # order.quantity = min(pair_quantity, max_needed_qty, free_related_order_quantity)

                    oo.extra_data.request = self.request
                    order.extra_data.request = self.request
                    order.save()
                    oo.save()

                    form = OrderForm(data=data, instance=order)
                    form_fields = set(form.fields.keys())
                    provided_fields = set(data.keys())
                    missing_fields = form_fields - provided_fields

                    # مقدار None برای فیلدهای غایب نمی‌ذاریم (برخلاف رفتار پیش‌فرض فرم)
                    for field in missing_fields:
                        form.fields.pop(field)

                    if form.is_valid():
                        form.instance.extra_data.request = self.request
                        obj = form.save()
                        self.wf_action(obj)
                        form.instance.state_pair = form.instance.state(self.flow_config, self.get_flow_index(form.instance), self.request, form.instance)
                        form = OrderForm(instance=obj)

                    html = render_to_string('order/partial/order_of_factors_row.html', {'order_form': form, 'order_pair': oo, 'main_order': main_order})
                    return JsonResponse({'res': html, 'need_supply': main_order.needed_qty, 'supplied': main_order.total_supply_qty})
            else:
                """update independent order"""
                order = Order.objects.get(pk=pk)
                form = OrderForm(data=data, instance=order)
                form_fields = set(form.fields.keys())
                provided_fields = set(data.keys())
                missing_fields = form_fields - provided_fields

                # مقدار None برای فیلدهای غایب نمی‌ذاریم (برخلاف رفتار پیش‌فرض فرم)
                for field in missing_fields:
                    form.fields.pop(field)

                if form.is_valid():
                    form.instance.extra_data.request = self.request
                    obj = form.save()
                    self.wf_action(obj)
                    obj.state_pair = obj.state(self.flow_config, self.get_flow_index(obj), self.request, obj)
                    form = OrderForm(instance=obj)
                html = render_to_string('order/partial/order_of_factors_row.html', {'order_form': form})
                return JsonResponse({'res': html})

    def save_order_order(self):
        main_order_pk = self.data.get('main_order_pk')
        order_rel_pk = self.data.get('order_rel_pk')
        main_order = Order.objects.filter(pk=main_order_pk).first()
        order_rel = Order.objects.filter(pk=order_rel_pk).first()
        pair_quantity = float(self.data.get('pair_quantity'))

        total_supply_qty = main_order.total_supply_qty
        main_order_qty = main_order.quantity if main_order else 0
        needed_qty = main_order_qty - total_supply_qty
        from django.db.models import Sum

        order_rel_used_quantity = order_rel.order_rel_items.aggregate(total=Sum('quantity'))['total'] or 0

        order_rel_max_available_qty = order_rel.quantity - order_rel_used_quantity

        oo = OrderOrder.objects.filter(order_base=main_order, order_rel=order_rel)
        oo_quantity = 0
        if oo:
            oo_quantity = oo.first().quantity

        order_order_data = {
            'order_base': main_order,
            'order_rel': order_rel,
            'creator_user': self.request.user,
            'editor_user': self.request.user,
            'quantity': min((pair_quantity + oo_quantity), order_rel_max_available_qty, needed_qty)
        }


        if oo:
            oo = oo.update(**order_order_data)
        else:
            oo = OrderOrder.objects.create(**order_order_data)
        return {'oo': oo, 'main_order': main_order, 'order_rel': order_rel}

    def save_order_as_wh(self):
        pair_quantity = self.data.get('pair_quantity')
        Order.objects.create()


def other_available_orders(request, main_order_pk, *args, **kwargs):
    main_order = Order.objects.get(pk=main_order_pk)
    item = main_order.item
    illegal_order_ids = [x.order_rel.pk for x in main_order.order_base_items.all()] if main_order.pk else []
    illegal_order_ids.append(main_order.pk)
    other_orders = main_order.__class__.objects.filter(item=item).exclude(pk__in=illegal_order_ids)
    stock_qty_api = SepidarApiCall.get_stock_quantity([item.sepidar_id_0]) if item else {}
    api_res = stock_qty_api.get('res')
    res = []
    if api_res:
        for name_code, stock_qty in api_res.items():
            if stock_qty:
                sepidar_wh_name = name_code[0]
                sepidar_wh_code = name_code[1]
                quantity_sum = item.reserved_count_in_portal
                if stock_qty.is_integer():
                    qty = int(stock_qty)
                    if qty - quantity_sum < 0:
                        res.append(
                            {sepidar_wh_code: f'☑️ {sepidar_wh_name} (کل:{qty:,}) - (آزاد: منفی{int(abs(qty - quantity_sum)):,})'})
                    else:
                        res.append({sepidar_wh_code: f'☑️ {sepidar_wh_name} (کل:{qty:,}) - (آزاد:{int(qty - quantity_sum):,})'})
                else:
                    res.append({sepidar_wh_code: (f'wh__{sepidar_wh_code}', f'☑️ {sepidar_wh_name} {stock_qty}')})


    context = dict({'other_wh': res})
    context['other_orders'] = other_orders

    html = render_to_string('order/partial/other_available_orders.html', context)
    return JsonResponse({'res': html})


def get_order_order(request, order_pk, *args, **kwargs):
    from types import SimpleNamespace
    wh_code = None
    main_order_pk = int(request.GET.get('main_order', 0))
    main_order_obj = Order.objects.get(pk=main_order_pk)
    context = dict()

    if "__" in order_pk:
        wh_code = int(order_pk.split('__')[1])
        # res = SepidarApiCall.get_stock_item_pair_quantity([main_order_obj.item.sepidar_id_0], wh_code)
        # if res:
        #     res = res.get('results')[0].get('quantity')

    if wh_code:
        """process wh reservation"""
        initial_data = {
            "item": main_order_obj.item,
            "quantity": 5,
            "transportation_method": None,
            "order_type": None
        }
        x = OrderForm(initial=initial_data, data=initial_data)
        x = OrderForm(data=initial_data)


        x = SimpleNamespace()
        x.instance = SimpleNamespace()
        x.instance.final_item = main_order_obj.final_item
        x.instance.item = main_order_obj.item
        x.instance.sepidar_wh_quantity = '-'
        x.instance.final_item.part_number = main_order_obj.item.part_number
        x.instance.quantity = 10

        context['order_form'] = x

        html = render_to_string('order/partial/selected_other_order.html', context)
        return JsonResponse({'res': html})
    else:
        """process order reservation"""
        order = Order.objects.get(pk=order_pk)
        item = order.item

        form = OrderForm(instance=order)
        context['order_form'] = form

        html = render_to_string('order/partial/selected_other_order.html', context)
        return JsonResponse({'res': html})


class ACNTView(LoginRequiredMixin, BaseView):
    template_name = 'order/acnt_list.html'
    form_class = ACNTForm
    model = ACNT
    form_struct = {
        'form': ACNTForm,
        'childes': [
            {},
        ]
    }

    def get_success_url(self):
        return reverse_lazy('order:acnt.update', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        x = super().post(request, *args, **kwargs)
        if is_ajax(request):
            return JsonResponse({'res': 'success'})
        else:
            return x

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs)


class ACNTListView(LoginRequiredMixin, View):
    """
    sku list view
    """
    model = ACNT
    template_name = 'order/acnt_list.html'
    context_object_name = 'items'

    def get(self, request, *args, **kwargs):
        context = {}
        return render(request, self.template_name, context)


class ACNTDataTableListView(AjaxDatatableView):
    model = ACNT
    title = 'ACNT'
    initial_order = [["created_date", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'id', 'visible': False, 'title': _('id'), 'className': 'py-1',},
        {'name': 'pk', 'visible': True, 'title': _('id'), 'className': 'py-1',},
        {'name': 'info_bank', 'visible': True, 'title': _('info_bank'), 'className': 'py-1',},
        {'name': 'currency', 'visible': True, 'title': _('currency'), 'className': 'py-1', },
        {'name': 'first_amount', 'title': _('first_amount'), 'className': 'py-1', },
        {'name': 'is_blocked', 'orderable': True, 'visible': True, },
        {'name': 'description', 'orderable': True, 'visible': True, },
        {'name': 'creator_user', 'orderable': True, 'visible': True, 'title': _('creator_user')},
        {'name': 'editor_user', 'orderable': True, 'visible': True, 'title': _('editor_user')},
        {'name': 'created_date', 'orderable': True, 'visible': True, },
    ]

    def customize_row(self, row, obj):
        row['pk'] = '<a class="fw-bold" target=_blank href="%s">%s</a>' % (
            reverse('order:acnt.update', args=(obj.id,)),
            obj.id if obj.id else 'بدون عنوان'
        )
