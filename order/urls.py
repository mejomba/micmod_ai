from django.urls import path
from . import views
from .views import PaymentView, PaymentListView, PaymentDataTableListView, PaymentItemView

app_name = 'order'
urlpatterns = [
    #  order
    path('view/', views.OrderView.as_view(), name='order.view'),
    path('view/<int:pk>/', views.OrderView.as_view(), name='order.view'),
    path('list/', views.OrderListView.as_view(), name='order.list'),
    path('list/action/', views.OrderAction.as_view(), name='order.list.action'),
    path('list/datatable/', views.OrderDataTableListView.as_view(), name='order.list.datatable'),
    path('ajax/order_order/add/', views.ajax_order_order_add, name='order_order.add'),

    #  packing
    path('packing/view/', views.PackingView.as_view(), name='packing.view'),
    path('packing/view/<int:pk>/', views.PackingView.as_view(), name='packing.update'),
    path('packing/list/', views.PackingListView.as_view(), name='packing.list'),
    path('packing/list/datatable/', views.PackingDataTableListView.as_view(), name='packing.list.datatable'),

    #  packingitem
    path('packingitem/view/', views.packing_list_form.as_view(), name='packingitem.view'),
    path('packingitem/update/<int:pk>/', views.packing_list_form.as_view(), name='packingitem.update'),

    #  GIO
    path('gio/view/', views.GIOView.as_view(), name='gio.view'),
    path('gio/view/<int:pk>/', views.GIOView.as_view(), name='gio.update'),
    path('gio/list/', views.GIOListView.as_view(), name='gio.list'),
    path('gio/list/datatable/', views.GIODataTableListView.as_view(), name='gio.list.datatable'),

    #  gioitem
    path('gioitem/view/', views.GIOItemView.as_view(), name='gioitem.view'),
    path('gioitem/update/<int:pk>/', views.GIOItemView.as_view(), name='gioitem.update'),

    #  order payment
    path('payment/view/', PaymentView.as_view(), name='order.payment.view'),
    path('payment/view/<int:pk>/', PaymentView.as_view(), name='order.payment.update'),
    path('payment/list/', PaymentListView.as_view(), name='order.payment.list'),
    path('payment/list/datatable/', PaymentDataTableListView.as_view(), name='order.payment.list.datatable'),

    #  order paymentitem
    path('paymentitem/view/', PaymentItemView.as_view(), name='order.paymentitem.view'),
    path('paymentitem/update/<int:pk>/', PaymentItemView.as_view(), name='order.paymentitem.update'),
]