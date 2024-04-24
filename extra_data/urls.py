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

    path('purchasegroup/update/<int:pk>/', views.PurchaseGroupView.as_view(), name='purchase_group.update'),
    path('purchasegroup/list/', views.PurchaseGroupListView.as_view(), name='purchase_group.list'),
    path('purchasegroup/datatable/', views.PurchaseGroupDataTableView.as_view(), name='purchase_group.datatable'),

    path('hs/update/<int:pk>/', views.HsView.as_view(), name='hs.update'),
    path('hs/list/', views.HsListView.as_view(), name='hs.list'),
    path('hs/datatable/', views.HsDataTableView.as_view(), name='hs.datatable'),
]