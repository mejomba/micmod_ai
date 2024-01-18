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

    # path('inquiryresult/create/', views.InquiryResultCreateView.as_view(), name='inquiry_result.create'),
    path('inquiryresult/list/', views.InquiryResultListView.as_view(), name='inquiry_result.list'),
    # path('inquiryresult/view/<int:pk>/', views.InquiryResultView.as_view(), name='inquiry_result.view'),
    # path('inquiryresult/update/<int:pk>/', views.InquiryResultUpdateView.as_view(), name='inquiry_result.update'),

    path('inquiryresult/forsale/', views.InquiryResultSaleView.as_view(), name='inquiry_result.sale'),
    path('ajax/inquiryresult/forsale/', views.inquiry_result_sale_ajax, name='inquiry_result.sale.ajax'),

    path('sku_list_datatable/', views.SkuListDataTableView.as_view(), name="sku.list.datatable"),

    path('item_list/', views.get_item, name='item_list'),
    path('items_list/', views.get_items, name='items_list'),

    path('sku/list/', views.sku_list, name='sku_list'),

    # path('supplier/view/', views.SupplierView.as_view(), name='supplier.view'),
    path('supplier/view/<int:pk>/', views.SupplierView.as_view(), name='supplier.detail_update'),
    path('supplier/list/', views.SupplierListView.as_view(), name='supplier.list'),
    path('supplier_list_datatable/', views.SupplierDataTableView.as_view(), name='supplier.datatable')
]
