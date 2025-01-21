from ajax_datatable import AjaxDatatableView
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.db.models import Sum, F, ExpressionWrapper, FloatField, Q
from django.db.models.functions import Coalesce
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse_lazy, reverse
from django.utils.safestring import mark_safe
from django.views import View
from django.views.generic import ListView

from core.views import BaseView, Base
from micmod_base.models import QuotationItem
from tools.utils import is_ajax
from workflow.models import WorkFlow
# from order.models import OrderItem
from .forms import OrderForm, PackingForm, PackingItemForm, GIOForm, GIOItemForm, OrderPaymentForm, OrderPaymentItemForm
from .models import Order, OrderOrder, Packing, PackingItem, GIO, GIOItem, OrderPayment, OrderPaymentItem
from translator import get_text as _

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
        if 'mohandes_confirmation' not in self.request.POST and self.state_index == 2 and 'change_user' not in self.request.POST and 'back' not in self.request.POST:
            flow_data = {
                "wf_status": 3, # next
                "action": 'ایجاد خودکار',
                "flow_name": 'سفارش',
                "state": const.WF__ORDER__4_STATE,
                "wf_description": "بدون نیاز به تایید مهندس",
                "belong_to_group": 'order_admin',
                "object_id": self.object.pk,
                "content_type": ContentType.objects.get_for_model(self.object),
                "creator_user": self.request.user,
                "editor_user": self.request.user,
                "from_user": self.request.user,
                "to_user": self.request.user,  # get_user_model().objects.filter(groups__name='order_admin').first(),
                "current_state_name": const.WF__ORDER__3_CURRENT_STATE_NAME,
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
        {'name': 'order_title', 'orderable': True, 'visible': True, },
        {'name': 'last_work_flow', 'title': 'status', 'visible': True, 'orderable': True,
         'lookup_field': '__current_state_name__icontains'},
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
        {'name': 'xxx', 'orderable': True, 'visible': True, 'title': 'دلیل تاخیر'},
        {'name': 'quantity_trade', 'orderable': True, 'visible': True, 'title': 'Order Qty (T)', },
        {'name': 'co_conf', 'orderable': False, 'visible': True, 'title': 'زمان تایید مهندس', },

        # {'name': 'id', 'orderable': True, 'visible': True, },
        # # {'name': 'edit', 'orderable': False, 'visible': True, },
        # {'name': 'last_work_flow','title': 'status', 'visible': True, 'orderable': True, 'lookup_field': '__current_state_name__icontains'},
        # {'name': 'order_number', 'orderable': True, 'visible': True, },
        # {'name': 'order_title', 'orderable': True, 'visible': True, },
        # {'name': 'is_bazar', 'orderable': True, 'visible': True, },
        # # {'name': 'status', 'orderable': True, 'visible': True, },
        # {'name': 'item', 'orderable': True, 'title': 'sku' , 'visible': True, 'lookup_field': '__sku__icontains'},
        # {'name': 'qi', 'title': 'customer', 'orderable': True, 'visible': True, 'lookup_field': '__quotation__customer_party_id__title__icontains'},
        # {'name': 'transportation_method', 'orderable': True, 'visible': True, },
        # {'name': 'production_lead_time', 'orderable': True, 'visible': True, },
        # {'name': 'trade_commitment_date', 'orderable': True, 'visible': True, },
        # {'name': 'commitment_date_to_customer', 'orderable': True, 'visible': True, },
        # {'name': 'quantity', 'orderable': True, 'visible': True, },
        # {'name': 'description_sale', 'orderable': True, 'visible': True, },
        # {'name': 'order_type', 'orderable': True, 'visible': True, },
        # {'name': 'sales_admin_confirmation', 'orderable': True, 'visible': True, },
        # {'name': 'cancel', 'orderable': True, 'visible': True, },
        # {'name': 'is_over', 'orderable': True, 'visible': True, },
        # {'name': 'created_date', 'orderable': True, 'visible': True, },
        # {'name': 'qi__quotation', 'orderable': True, 'visible': True, 'lookup_field': '__id__icontains', 'title': "پیش فاکتور"},

        # {'name': 'sepidar_dl_code', 'orderable': True, 'visible': True, 'width': 600, },
        # {'name': 'title', 'title': '<div class="px-15">عنوان</div>', 'orderable': True, 'visible': True,
        #  'className': 'text-center'},
    ]

    def get_initial_queryset(self, request=None):
        qs = super().get_initial_queryset(request)
        q = request.POST.get('q')
        if q == 'sales_admin':
            return qs.filter(cancel=True)
        elif q == 'bazar_user':
            return qs.filter(is_bazar=True)
        elif q == 'all':
            return qs
        elif q == 'not_complete':
            not_complete_order = Q()
            qs = qs.filter(cancel=True)
            for order in qs:
                not_complete = 0
                for item in order.order_base_items.all():
                    not_complete += item.quantity
                res = not_complete - order.quantity
                if res < 0:
                    not_complete_order |= Q(id=order.id)
            return Order.objects.filter(not_complete_order) if not_complete_order else Order.objects.none()

        else:
            return qs
        return qs

    def customize_row(self, row, obj):
        row['part_number_s'] = f'<span>{obj.item.part_number}</span>' if obj.item else ""
        row['qi__quotation__customer_party_id'] = f'<span>{obj.qi.quotation.customer_party_id.title}</span>' if obj.qi else ""
        row['qi__quotation__id'] = f'<span>{obj.qi.quotation.id}</span>' if obj.qi else ""
        row['item_trade__part_number'] = f'<span>{obj.item_trade.part_number}</span>' if obj.item_trade else ""
        o = obj.workflows.filter(current_state_name='تایید مهندس').first()
        row['co_conf'] = f'<span>{o.created_date}</span>' if o else ""

        row['order_title'] = '<a class="fw-bold" target=_blank href="%s">%s</a>' % (
            reverse('order:order.view', args=(obj.id,)),
            obj.order_title if obj.order_title else 'بدون عنوان'
        )
        row['qi'] = f'<span>{obj.qi.quotation.customer_party_id.title}</span>' if obj.qi else ""
        row['qi__quotation'] = f'<span>{obj.qi.quotation.id}</span>' if obj.qi else ""
        # row['edit'] = mark_safe(f"""
        # <a href="#" target="_blank" class="me-3 edit-packing-item tooltip_" data-url="/order/packingitem/update/1/" data-bs-toggle="modal" data-bs-target="#id_kt_empty_modal_lg">
        #     <i class="ki-duotone ki-pencil fs-2 text-info">
        #         <span class="path1"></span>
        #         <span class="path2"></span>
        #     </i>
        # </a>
        # """)


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
        {'name': 'id', 'visible': False, 'title': _('id'), 'className': 'py-1 border',},
        {'name': 'pk', 'visible': True, 'title': _('id'), 'className': 'py-1 border',},
        {'name': 'sum_qty', 'visible': True, 'title': _('sum_qty'), 'className': 'py-1',},
        {'name': 'sum_arrived_qty', 'visible': True, 'title': _('sum_arrived_qty'), 'className': 'py-1', },
        {'name': 'tp_method', 'title': _('tp_method'), 'className': 'py-1', },
        {'name': 'pack_date', 'title': _('pack_date'), 'className': 'py-1', },
        {'name': 'bl_number', 'title': _('bl_number'), 'className': 'py-1', },
        {'name': 'sales_manager_needed', 'title': _('sales_manager_needed'), 'className': 'py-1', },
        {'name': 'creator_user', 'title': _('creator_user'), 'className': 'py-1', },
        {'name': 'created_date', 'orderable': True, 'visible': True, },
    ]

    def customize_row(self, row, obj):
        row['pk'] = '<a class="fw-bold" target=_blank href="%s">%s</a>' % (
            reverse('order:packing.update', args=(obj.id,)),
            obj.id if obj.id else 'بدون عنوان'
        )


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
        {'name': 'id', 'visible': False, 'title': _('id'), 'className': 'py-1 border',},
        {'name': 'pk', 'visible': True, 'title': _('id'), 'className': 'py-1 border',},
        {'name': 'gio_date', 'visible': True, 'title': _('gio_date'), 'className': 'py-1',},
        {'name': 'total_quantity', 'visible': True, 'title': _('total_quantity'), 'className': 'py-1', },
        {'name': 'creator_user', 'title': _('creator_user'), 'className': 'py-1', },
        {'name': 'created_date', 'orderable': True, 'visible': True, },
    ]

    def customize_row(self, row, obj):
        row['pk'] = '<a class="fw-bold" target=_blank href="%s">%s</a>' % (
            reverse('order:gio.update', args=(obj.id,)),
            obj.id if obj.id else 'بدون عنوان'
        )


class PaymentView(LoginRequiredMixin, BaseView):
    template_name = 'order/payment_view.html'
    form_class = OrderPaymentForm
    model = OrderPayment
    # wf_last_step_is_open = True
    # has_flow = True
    success_message = 'با موفقیت ذخیره شد'
    form_struct = {
        'form': OrderPaymentForm,
        'childes': [
            {},
        ]
    }
    # flow_config = Base.get_flow_config(settings.BASE_DIR/'_keenthemes/view_config.json', 'GIOView')

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
            reverse('order:order.payment.update', args=(obj.id,)),
            obj.id if obj.id else 'بدون عنوان'
        )
