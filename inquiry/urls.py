from django.urls import path, re_path
from . import views

app_name = 'inquiry'

urlpatterns = [
    # path('sku/create/', views.SkuCreateView.as_view(), name='sku.create'),
    # path('sku/list/', views.SkuListView.as_view(), name='sku.list'),
    # path('sku/update/<int:pk>/', views.SkuUpdateView.as_view(), name='sku.update'),
    # path('sku/view/<int:pk>/', views.SkuRelatedView.as_view(), name='sku.view-related'),

    path('priceinquiryfile/create/', views.PriceInquiryFileCreateView.as_view(), name='price_inquiry_file.create'),
    path('priceinquiryfile/list/', views.PriceInquiryFileListView.as_view(), name='price_inquiry_file.list'),
    re_path(r'^priceinquiryfile/update/(?P<pk>[0-9]*)$', views.PriceInquiryFileUpdateView.as_view(), name='price_inquiry_file.update'),
    path('priceinquiryfile/view/<int:pk>/', views.PriceInquiryFileRelatedView.as_view(), name='price_inquiry_file.view-related'),

    path('inquiryresult/view/', views.InquiryResultListView.as_view(), name='inquiry_result.list_create'),
    path('inquiryresult/view/<int:pk>/', views.InquiryResultUpdateView.as_view(), name='inquiry_result.update'),
    path('inquiryresult_list_datatable/', views.InquiryResultDataTableView.as_view(), name='inquiry_result.list.datatable'),
    path('price_list/', views.get_price_list, name='inquiry_result.price_list'),
    path('export_items/', views.update_components_view, name='inquiry_result.export_items'),


    # path('inquiryresult/create/', views.InquiryResultCreateView.as_view(), name='inquiry_result.create'),
    path('inquiryresult/list/', views.InquiryResultListView.as_view(), name='inquiry_result.list'),
    # path('inquiryresult/view/<int:pk>/', views.InquiryResultView.as_view(), name='inquiry_result.view'),
    # path('inquiryresult/update/<int:pk>/', views.InquiryResultUpdateView.as_view(), name='inquiry_result.update'),

    path('inquiryresult/forsale/', views.InquiryResultSaleView.as_view(), name='inquiry_result.sale'),
    path('ajax/inquiryresult/forsale/', views.inquiry_result_sale_ajax, name='inquiry_result.sale.ajax'),

    path('inquiryresult/forsale/list/', views.InquiryResultSaleListView.as_view(), name='inquiry_result_sale_list'),
    path('ajax/inquiryresult/forsale/list/', views.SalesPriceInqueryLogDataTableView.as_view(), name='ajax_inquiry_result_sale_list'),

    path('sku_list_datatable/', views.SkuListDataTableView.as_view(), name="sku.list.datatable"),

    path('item_list/', views.get_item, name='item_list'),
    path('items_list/', views.get_items, name='items_list'),

    path('sku/list/', views.sku_list, name='sku_list'),
    path('all_prices/', views.all_prices, name='trade_all_prices'),
    path('trade_all_prices/', views.trade_all_prices, name='trade_all_prices'),
    path('bazar_all_prices/', views.bazar_all_prices, name='bazar_all_prices'),

    # path('supplier/view/', views.SupplierView.as_view(), name='supplier.view'),
    path('supplier/view/<int:pk>/', views.SupplierView.as_view(), name='supplier.detail_update'),
    path('supplier/list/', views.SupplierListView.as_view(), name='supplier.list'),
    path('supplier_list_datatable/', views.SupplierDataTableView.as_view(), name='supplier.datatable'),
    path('ajax/inquiryresult/list/data/', views.AjaxInquiryResultListData.as_view(), name='ajax.inquiryresult'),
    path('ajax/count/', views.inquiry_count, name='inquiry.count'),
    path('ajax/sepidar_api/last_receipt/', views.get_last_receipt_from_sepidar, name='last_receipt'),
    path('variant/title/', views.get_inquiry_title, name='inquiry.title'),
    path('transportation_method/title/', views.get_transportation_method_title, name='transportation.title'),
    path('supplier/region/', views.get_supplier_region, name='supplier.region'),
    path('trade_transportation_method/json/', views.get_trade_transportation_method_json, name='get_trade_transportation_method_json'),
    path('pg_backup/', views.pg_backup, name='pg_backup'),
    path('currency_amount/', views.CurrencyAmountList.as_view(), name='currency_amount.view'),
    path('currency_amount/<int:pk>/', views.CurrencyAmountList.as_view(), name='currency_amount.update'),
    path('currency_amount/datatable/', views.CurrencyAmountDatatableView.as_view(), name='currency_amount.datatable'),

    path('override_all_supplier_from_sepidar/', views.override_all_supplier_from_sepidar, name='override_all_supplier_from_sepidar'),

    # dal auto complete
    path('supplier-autocomplete/', views.SupplierAutocomplete.as_view(), name='supplier-autocomplete'),
]
