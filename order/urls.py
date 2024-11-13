from django.urls import path
from . import views


app_name = 'order'
urlpatterns = [
    path('view/', views.OrderView.as_view(), name='order.view'),
    path('view/<int:pk>/', views.OrderView.as_view(), name='order.view'),
    path('list/', views.OrderListView.as_view(), name='order.list'),
    path('list/action/', views.OrderAction.as_view(), name='order.list.action'),
    path('list/datatable/', views.OrderDataTableListView.as_view(), name='order.list.datatable'),
    path('ajax/order_order/add/', views.ajax_order_order_add, name='order_order.add'),
    path('packing/list', views.PackingView.as_view(), name='packing.view'),
    path('packing/list', views.PackingListView.as_view(), name='packing.list'),
    path('packing/list/datatable/', views.PackingDataTableListView.as_view(), name='packing.list.datatable'),
]