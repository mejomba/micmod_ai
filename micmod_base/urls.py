from django.urls import path, re_path

from .views import *

app_name = "micmod_base"
urlpatterns = [
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
    path('quotationitem/list/form/item_in_china/', QuotationItemFormPending2.as_view(), name='quotationitem.item_in_china'),
    path('quotationitem/list/form/pending/', QuotationItemFormPending2.as_view(), name='quotationitem.form.pending'),
    path('quotationitem/past/quotationitems', QuotationItemFormPending2.as_view(), name='quotationitem.form.past'),
    path('quotation/list/datatable', QuotationListDatatable.as_view(), name='quotation.list.datatable'),
    path('get_sku/', get_sku, name='get_sku'),
    path('quotation/print/<int:id>/', print_view, name='print'),
    path('quotationitem/inquiry/report/', inquiry_report, name='inquiry_report'),
    path('quotation/print/customer/<int:id>/', print_view, name='print_customer'),
    path('ajax/save_parent_item/', save_parent_item, name='save_parent_item'),
    path('sale_user_report/', sale_user_report, name='sale_user_report'),
    path('repeated/goods_code/', repeated_goods_code_view, name='repeated_goods_code'),
    path('ajax/inquiry_not_started/', inquiry_not_started, name='inquiry_not_started'),
]
