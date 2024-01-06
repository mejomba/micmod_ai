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
    # path('currency_exchange/view/<int:pk>/', CurrencyExchangeUpdateView.as_view(), name='currency_exchange.update'),
]
