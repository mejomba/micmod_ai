from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views
from .views import PaymentView, PaymentListView, PaymentDataTableListView, PaymentItemView, \
    PaymentItemDataTableListView, OrderAndSepidar, OrderOfFactor, other_available_orders, get_order_order, ACNTView, \
    ACNTListView, ACNTDataTableListView

from .views import CustomerRequestOrderViewSet

router = DefaultRouter()
router.register(r'customer-request-order', CustomerRequestOrderViewSet, basename='customer-order')


app_name = 'order'
urlpatterns = [
    path('', include(router.urls)),
    #  order
    path('view/', views.OrderView.as_view(), name='order.view'),
    path('bazar/buy_factor/view/', views.BazarBuyFactorView.as_view(), name='bazar_order.view'),
    # path('trade/buy_factor/view/', views.TradeBuyFactorView.as_view(), name='trade_buy_factor_order.view'),
    path('view/<int:pk>/', views.OrderView.as_view(), name='order.view'),
    path('list/', views.OrderListView.as_view(), name='order.list'),
    path('list/action/', views.OrderAction.as_view(), name='order.list.action'),
    path('list/datatable/', views.OrderDataTableListView.as_view(), name='order.list.datatable'),
    path('bazar/list/datatable/', views.BazarOrderDataTableListView.as_view(), name='bazar_order.list.datatable'),
    # path('trade/list/datatable/', views.TradeOrderDataTableListView.as_view(), name='trade_order.list.datatable'),
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
    path('payment_item/list/datatable/', PaymentItemDataTableListView.as_view(), name='order.payment_item.list.datatable'),

    #  order paymentitem
    path('paymentitem/view/', PaymentItemView.as_view(), name='order.paymentitem.view'),
    path('paymentitem/update/<int:pk>/', PaymentItemView.as_view(), name='order.paymentitem.update'),

    #  ACNT
    path('acnt/view/', ACNTView.as_view(), name='acnt.view'),
    path('acnt/view/<int:pk>/', ACNTView.as_view(), name='acnt.update'),
    path('acnt/list/', ACNTListView.as_view(), name='acnt.list'),
    path('acnt/list/datatable/', ACNTDataTableListView.as_view(), name='acnt.list.datatable'),
    # path('payment_item/list/datatable/', PaymentItemDataTableListView.as_view(), name='order.payment_item.list.datatable'),

    # path('ajax/submit_buy_factor/', OrderAndSepidar.as_view(), name='submit_buy_factor'),
    path('ajax/order_and_sepidar/', OrderAndSepidar.as_view(), name='order_and_sepidar'),

    path('order_of_factor/<str:pk>/', OrderOfFactor.as_view(), name='order_of_factor'),

    path('other_available_orders/<int:main_order_pk>/', other_available_orders, name='other_available_orders'),
    path('get_order_order/<str:order_pk>/', get_order_order, name='get_order_order'),
    path('get_wh_reserve_order/', views.get_wh_reserve_order, name='get_wh_reserve_order'),
    path('wh_packing_view/', views.wh_packing_view, name='wh_packing_view'),
    path('wh_packing_view/<int:sepidar_buy_factor_id>/', views.wh_packing_view, name='wh_packing_view'),
]