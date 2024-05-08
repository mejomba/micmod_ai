from django.urls import path, re_path

from .views import *

app_name = "sls"
urlpatterns = [
    # Ecommerce
    path(
        r"quotation/view/<int:pk>",
        view=QuotationsView.as_view(),
        name="quotations.view",
    ),
    path(
        r"quotations/print-view/<id>",
        view=print_view,
        name="quotations.print-view",
    ),
    path(
        r"quotations/delete/<id>",
        view=QuotationsView.as_view(),
        name="quotations.delete",
    ),
    path(
        r"quotations/create",
        view=QuotationsView.as_view(),
        name="quotations.create",
    ),
    path(
        r"quotations/list",
        view=QuotationsList.as_view(),
        name="quotations.list",
    ),
    path("currency/exchange/", view=CurrencyExchangeView.as_view(), name="currency_exchange"),
    path("currency/exchange/<int:pk>/", view=CurrencyExchangeView.as_view(), name="currency_exchange"),
    path('currency_exchange_list_datatable/', CurrencyExchangeDataTableView.as_view(), name="currency_exchange.list.datatable"),
    path('quotationitem/list/pending/', QuotationItemPending.as_view(), name='quotationitem.pending'),
    # path('quotationitem/list/form/pending/', QuotationItemFormPending.as_view(), name='quotationitem.form.pending'),
    path('quotationitem/list/form/pending/', QuotationItemFormPending2.as_view(), name='quotationitem.form.pending'),
    # path('quotationitem/list/form/pending2/', QuotationItemFormPending2.as_view(), name='quotationitem.form.pending2'),
    path('quotationitem/past/quotationitems', QuotationItemFormPending2.as_view(), name='quotationitem.form.past'),
    path('quotation/list/datatable', QuotationListDatatable.as_view(), name='quotation.list.datatable'),
    path('get_sku/', get_sku, name='get_sku'),
    path('quotation/print/<int:id>/', print_view, name='print')
]
