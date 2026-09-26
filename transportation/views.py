from ajax_datatable import AjaxDatatableView
from django.urls import reverse_lazy, reverse

from core.views import BaseView
from transportation.forms import TradeTransportationMethodModelForm, TransportationCalenderModelForm
from transportation.models import TradeTransportationMethod, TransportationCalender


class TradeTransportationMethodView(BaseView):
    template_name = 'trade_transportation_method.html'
    model = TradeTransportationMethod
    form_struct = {
        'form': TradeTransportationMethodModelForm,
        'childes': [
            {
                'childes': [{}]
            },
        ]
    }

    def get_success_url(self):
        path = reverse_lazy('transportation:trade_transportation_method.view')
        self.success_url = path
        return path

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        return context


class TradeTransportationMethodDataTableView(AjaxDatatableView):
    model = TradeTransportationMethod
    title = 'trade transportation method'
    initial_order = [["last_update_date", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    def get_columns(self, fields):
        res = [AjaxDatatableView.render_row_tools_column_def()]
        for field in fields:
            col = dict()
            col['className'] = ''
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
            'origin_area',
            "method",
            {'name': 'currency_type', 'lookup_field': '__title__icontains'},
            'fixed_cost',
            'variable_cost',
            'access_type',
            'created_date',
            'last_update_date'
        ])
        return cols

    def get_initial_queryset(self, request=None):
        qs = self.model.objects.filter(is_public=True, is_deleted=False)
        return qs

    def customize_row(self, row, obj):
        row['origin_area'] = '<a class="fw-bold" href="%s">%s</a>' % (
            reverse('transportation:trade_transportation_method.update', args=(obj.id,)),
            obj.get_origin_area_display() if obj.origin_area else '_'
        )


class TransportationCalenderView(BaseView):
    template_name = 'trade_transportation_calender.html'
    model = TransportationCalender
    form_struct = {
        'form': TransportationCalenderModelForm,
        'childes': [
            {
                'childes': [{}]
            },
        ]
    }

    def get_success_url(self):
        path = reverse_lazy('transportation:transportation_calender.view')
        self.success_url = path
        return path

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class TransportationCalenderViewDataTableView(AjaxDatatableView):
    model = TransportationCalender
    title = 'trade transportation calender'
    initial_order = [["last_update_date", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    def get_columns(self, fields):
        res = [AjaxDatatableView.render_row_tools_column_def()]
        for field in fields:
            col = dict()
            col['className'] = ''
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
            "title",
            'deliver_to_shipping_company_date',
            'estimate_start_shipping_date',
            'estimate_arrive_date',
            'start_date',
            "arrive_date",
            "capacity_kg",
            'shipment_type',
            'description',
            'created_date',
            'last_update_date',
            'creator_user'
        ])
        return cols

    def get_initial_queryset(self, request=None):
        qs = self.model.objects.filter(is_deleted=False)
        return qs

    def customize_row(self, row, obj):
        pass
        row['title'] = '<a class="fw-bold" href="%s">%s</a>' % (
            reverse('transportation:transportation_calender.update', args=(obj.id,)),
            obj.title if obj.title else '_'
        )