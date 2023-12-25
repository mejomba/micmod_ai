from ajax_datatable.views import AjaxDatatableView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Permission
from sepidar.models import Dl, SalesHistory


class AjaxSalesHistory(AjaxDatatableView):

    model = SalesHistory
    title = 'Sales History'
    initial_order = [["Date", "asc"], ]
    length_menu = [[10, 20, 50, 100, -1], [10, 20, 50, 100, 'all']]
    search_values_separator = '+'

    column_defs = [
         AjaxDatatableView.render_row_tools_column_def(),
        {'name': 'itemId', 'visible': False, },
        {'name': 'Date', 'visible': True, },
        {'name': 'customer_creation_date', 'visible': False, },
        {'name': 'customer_title', 'visible': True, },
        {'name': 'customer_code', 'visible': True, },
        {'name': 'sales_user_group', 'visible': True, },
        {'name': 'item_code', 'visible': True, },
        {'name': 'item_title', 'visible': True, },
        {'name': 'purchase_group', 'visible': True, },
        {'name': 'sales_group', 'visible': True, },
        {'name': 'year_title', 'visible': False, },
        {'name': 'doc_type', 'visible': True, },
        {'name': 'coef', 'visible': True, },
        {'name': 'sales_type', 'visible': True, },
        {'name': 'Number', 'visible': True, },
        {'name': 'Rate', 'visible': True, },
        {'name': 'Quantity', 'visible': True, },
        {'name': 'Fee', 'visible': True, },
        {'name': 'Price', 'visible': False, },
        {'name': 'PriceInBaseCurrency', 'visible': True, },
        {'name': 'NetPrice', 'visible': False, },
        {'name': 'NetPriceInBaseCurrency', 'visible': True, },

    ]

    def get_initial_queryset(self, *args, **kwargs):
        # qs = super(AjaxSalesHistory, self).get_initial_queryset(*args, **kwargs)
        # print(qs)
        qs = (SalesHistory.get_sales_history_list())
        # print(qs)
        # print(qs)
        # print(qs.fetchall())
        return qs
