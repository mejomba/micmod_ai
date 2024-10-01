from django.urls import path
from . import views


app_name = 'order'
urlpatterns = [
    path('view/', views.OrderView.as_view(), name='order.view'),
    path('view/<int:pk>/', views.OrderView.as_view(), name='order.view'),
    path('list/', views.OrderListView.as_view(), name='order.list'),
    path('list/datatable/', views.OrderDataTableListView.as_view(), name='order.list.datatable'),
]