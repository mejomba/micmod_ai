from ajax_datatable import AjaxDatatableView
from django.shortcuts import render
from django.urls import reverse_lazy, reverse

from core.views import BaseView
from transportation.forms import TradeTransportationMethodModelForm
from transportation.models import TradeTransportationMethod


# Create your views here.
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


# class TradeTransportationMethodListView(BaseView):
#     model = TradeTransportationMethod
#     form_class = TradeTransportationMethodModelForm
#     template_name = 'trade_transportation_method.html'
#     success_url = '.'
#
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         return context


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
            'created_date',
            'last_update_date'
        ])
        return cols

    # def get_initial_queryset(self, request=None):
    #     qs = self.model.objects.filter(base_group=self.request.user.base_group)
    #     # param: str = self.request.POST.get('title')
    #     # if param:
    #     #     qs = self.model.objects.filter(title=param)
    #     # else:
    #     #     qs = self.model.objects.all()
    #     return qs
    #
    def customize_row(self, row, obj):
        row['origin_area'] = '<a class="fw-bold" href="%s">%s</a>' % (
            reverse('transportation:trade_transportation_method.update', args=(obj.id,)),
            obj.get_origin_area_display() if obj.origin_area else '_'
        )