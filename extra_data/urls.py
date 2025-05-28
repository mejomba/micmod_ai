from django.urls import path

from . import views


app_name = 'extra_data'
urlpatterns = [
    path('item/create/', views.SkuCreateView.as_view(), name='sku.create'),
    path('item/list/', views.SkuListView.as_view(), name='sku.list'),
    path('item/update/<int:pk>/', views.SkuUpdateView.as_view(), name='sku.update'),
    path('item/view/<int:pk>/', views.SkuRelatedView.as_view(), name='sku.view-related'),

    path('item_weight/view/', views.ItemWeightUpdateView.as_view(), name='item_weight.list'),
    path('item_weight/view/<int:pk>/', views.ItemWeightUpdateView.as_view(), name='item_weight.update'),
    path('item_weight_list_datatable/', views.ItemWeightDataTableView.as_view(), name='item_weight.list.datatable'),

    path('item/list/json/', views.item_list_json, name='item_list.json'),
    path('item/list/update/', views.ItemListUpdate.as_view(), name='item_list.update'),

#     path('item/not/confirm/list', views.ItemNotConfirmedListView.as_view(), name='item.not-confirm.list')


    path('purchasegroup/update/<int:pk>/', views.PurchaseGroupView.as_view(), name='purchase_group.update'),
    path('purchasegroup/list/', views.PurchaseGroupListView.as_view(), name='purchase_group.list'),
    path('purchasegroup/datatable/', views.PurchaseGroupDataTableView.as_view(), name='purchase_group.datatable'),

    path('ajax/update_from_sepidar/', views.ajax_update_from_sepidar, name='update_from_sepidar'),

    path('hs/create/', views.HsView.as_view(), name='hs.create'),
    path('hs/update/<int:pk>/', views.HsView.as_view(), name='hs.update'),
    path('hs/list/', views.HsListView.as_view(), name='hs.list'),
    path('hs/datatable/', views.HsDataTableView.as_view(), name='hs.datatable'),

    path('customer/create/', views.CustomerView.as_view(), name='customer.create'),
    path('customer/update/<int:pk>/', views.CustomerView.as_view(), name='customer.update'),
    path('customer/list/', views.CustomerListView.as_view(), name='customer.list'),
    path('customer/datatable/', views.CustomerDataTableView.as_view(), name='customer.datatable'),

    path('customer/document/create/', views.CustomerDocumentView.as_view(), name='customer_document.create'),
    path('customer/document/update/<int:pk>/', views.CustomerDocumentView.as_view(), name='customer_document.update'),

    path('customer/change_marketer/create/', views.CustomerChangeMarketerView.as_view(), name='customer_change_marketer.create'),
    path('customer/change_marketer/update/<int:pk>/', views.CustomerChangeMarketerView.as_view(), name='customer_change_marketer.update'),

    path('customer/expert/create/', views.CustomerExpertView.as_view(), name='customer_expert.create'),
    path('customer/expert/update/<int:pk>/', views.CustomerExpertView.as_view(), name='customer_expert.update'),

    path('customer/contract/create/', views.CustomerContractView.as_view(), name='customer_contract.create'),
    path('customer/contract/update/<int:pk>/', views.CustomerContractView.as_view(), name='customer_contract.update'),
    path('customer/sepidar/insert/<int:pk>/', views.CustomerSepidarInsertView.as_view(), name='customer_sepidar.insert'),

    path('item_package/list_or_create/', views.ItemPackageView.as_view(), name='item_package_list_or_create.view'),
    path('item_package/list_or_create/<int:pk>/', views.ItemPackageView.as_view(), name='item_package_list_or_create.update'),
    path('item_package/datatable/', views.ItemPackageDatatableView.as_view(), name='item_package.datatable'),
    path('item_package_weight/', views.ItemPackageWeightSearchView.as_view(), name='item_package_weight.search'),

]