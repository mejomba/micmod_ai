from ajax_datatable import AjaxDatatableView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views.generic import ListView

import sepidar.models
from translator import get_text as _
from .models import *
# Create your views here.
from django.views import View


class Item(LoginRequiredMixin,View):
    template_name = 'dw/view.html'

    def get(self, request):
        greeting = {}
        greeting['heading'] = 'Items'
        greeting['pageview'] = 'Inquery'
        sku = self.request.GET.get("sku", 0)
        sku = int(sku) if sku else 0
        if sku > 0:
            greeting['order_data'] = ItemModel.get_item(sku)
            sepidar_data = sepidar.models.Item.get_item(sku,0)
            greeting['sepidar_data'] = sepidar.models.Item.get_item(sku,0)[0] if sepidar_data else None
            greeting['sku'] = sku
        else:
            greeting['order_data'] = None
        return render(request, self.template_name, greeting)

    def post(self, request):
        print('saving')
        return render(request, self.template_name)


class OrderList(LoginRequiredMixin, ListView):
    template_name = 'dw/order_list.html'
    queryset = []


class OrderListDatatable(AjaxDatatableView):
    model = OrderListDatatableModel
    title = 'order_list'
    # initial_order = [["status", "asc"], ]
    length_menu = [[25, 50, 100], [25, 50, 100]]
    search_values_separator = '+'
    render_row_details_template_name = 'order_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'status_icon', 'visible': True, 'title': _('status icon'), 'className': 'py-1 border', },
        {'name': 'status', 'visible': True, 'title': _('status'), 'className': 'py-1 border'},
        {'name': 'customer', 'visible': True, 'title': _('customer'), 'className': 'py-1 border', },
        {'name': 'sku', 'visible': True, 'title': _('sku'), 'className': 'py-1 border'},
        {'name': 'part_number', 'visible': True, 'title': _('part number'), 'className': 'py-1 border'},
        {'name': 'pre_invoice_number', 'visible': True, 'title': _('pre invoice number'), 'className': 'py-1 border'},
        {'name': 'jalali_create_date', 'visible': True, 'title': _('create date'), 'className': 'py-1 border'},
        {'name': 'jalali_duty_date', 'visible': True, 'title': _('duty date'), 'className': 'py-1 border'},
        {'name': 'order_quantity', 'visible': True, 'title': _('order quantity'), 'className': 'py-1 border'},
        {'name': 'total_packed_count', 'visible': True, 'title': _('total packed count'), 'className': 'py-1 border'},
        {'name': 'total_arrived_count', 'visible': True, 'title': _('total arrived count'), 'className': 'py-1 border'},
        {'name': 'pack_numbers', 'visible': True, 'title': _('pack numbers'), 'className': 'py-1 border'},
        # all invisible field must be end of config
        {'name': 'id', 'visible': False, },
    ]

    def get_initial_queryset(self, request=None):
        qs = self.model.select_all()
        return qs


class CargoList(LoginRequiredMixin, ListView):
    template_name = 'dw/cargo_list.html'
    queryset = []

    def get(self, request, *args, **kwargs):
        print('get all')
        super().get(request, *args, **kwargs)
        context = dict()
        return render(request, self.template_name, context)


class CargoListDatatable(AjaxDatatableView):
    model = CargoListDatatableModel
    title = 'cargo_list'
    length_menu = [[25, 50, 100, -1], [25, 50, 100, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'cargo_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'id', 'visible': True, 'title': _('number'), 'className': 'py-1 border', 'autofilter': True},
        {'name': 'active', 'visible': True, 'title': _('active'), 'className': 'py-1 border', },
        {'name': 'invoice_number', 'visible': True, 'title': _('invoice_number'), 'className': 'py-1 border'},
        {'name': 'jalali_new_doc_date', 'visible': True, 'title': _('new_doc_date'), 'className': 'py-1 border'},
        {'name': 'in_person', 'visible': True, 'title': _('in_person'), 'className': 'py-1 border'},
        {'name': 'in_office', 'visible': True, 'title': _('in_office'), 'className': 'py-1 border'},
        {'name': 'force', 'visible': True, 'title': _('force'), 'className': 'py-1 border'},
        {'name': 'delete_doc', 'visible': True, 'title': _('delete_doc'), 'className': 'py-1 border'},
        {'name': 'jalali_delete_doc_date', 'visible': True, 'title': _('delete_doc_date'), 'className': 'py-1 border'},
        {'name': 'financial_cond', 'visible': True, 'title': _('financial_cond'), 'className': 'py-1 border'},
        {'name': 'financial_confirm', 'visible': True, 'title': _('financial_confirm'), 'className': 'py-1 border'},
        {'name': 'paking', 'visible': True, 'title': _('paking'), 'className': 'py-1 border'},
        {'name': 'final_check', 'visible': True, 'title': _('final_check'), 'className': 'py-1 border'},
        {'name': 'official_number', 'visible': True, 'title': _('official_number'), 'className': 'py-1 border'},
        {'name': 'send_delivery', 'visible': True, 'title': _('send_delivery'), 'className': 'py-1 border'},
        {'name': 'jalali_send_delivery_date', 'visible': True, 'title': _('send_delivery_date'), 'className': 'py-1 border'},
        {'name': 'confirmed_based_7_day', 'visible': True, 'title': _('confirmed_based_7_day'), 'className': 'py-1 border'},
        {'name': 'jalali_confirm_date', 'visible': True, 'title': _('confirm_date'), 'className': 'py-1 border'},
        {'name': 'collector', 'visible': True, 'title': _('collector'), 'className': 'py-1 border'},
        # all invisible field must be end of config
        # {'name': 'id', 'visible': False, },
    ]

    def get_initial_queryset(self, request=None):
        param = self.request.POST.get('q', '').strip('/')
        qs = self.model.select_all(param)
        return qs
