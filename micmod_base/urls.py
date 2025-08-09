from django.urls import path, include

from .views import *

from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'customer-requests', CustomerRequestViewSet, basename='customer-request')
router.register(r'customer-request-quotation', CustomerRequestQuotationViewSet, basename='customer-quotation')

app_name = "micmod_base"
urlpatterns = [
    path('', include(router.urls)),
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
    path('quotationitem/sales_history', QuotationsSalesHistoryList.as_view(), name='quotationitem.list.sales.history'),
    path('quotationitem/list/sales_history/datatable', QuotationSalesHistoryDatatable.as_view(), name='quotationitem.sales.history.datatable'),
    path('get_sku/', get_sku, name='get_sku'),
    path('quotation/print/<int:id>/', print_view, name='print'),
    path('quotationitem/inquiry/report/', inquiry_report, name='inquiry_report'),
    path('quotation/print/customer/<int:id>/', print_view, name='print_customer'),
    path('ajax/save_parent_item/', save_parent_item, name='save_parent_item'),
    path('sale_user_report/', sale_user_report, name='sale_user_report'),
    path('repeated/goods_code/', repeated_goods_code_view, name='repeated_goods_code'),
    path('ajax/inquiry_not_started/', inquiry_not_started, name='inquiry_not_started'),
    path('export_to_excel/<int:quotation_id>/', export_quotation_items_to_excel, name='export.qi.to.excel'),
    path('get_model_fields_config/', get_model_fields_config, name='get.model.fields.config'),
    path('ajax/customer_accounting_info/', get_customer_accounting_info, name='get_customer_accounting_info'),
    # path('api/', ExportQuotation.as_view(), name='api'),
    # path("customer_request/view/", view=CurrencyExchangeView.as_view(), name="currency_exchange"),
    path("customer_request/view/<int:pk>/", view=CustomerRequestView.as_view(), name="customer_request.view"),
    path('customer_request/list/', CustomerRequestList.as_view(), name="customer_request.list"),
    path('customer_request/list/datatable', CustomerRequestDatatableView.as_view(), name="customer_request.list.datatable"),
    path('quotation_from_customer_request/<int:pk>/', QuotationFromCustomerRequestView.as_view(), name="quotation_from_customer_request.view"),
]
