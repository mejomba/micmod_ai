from django.urls import path
from .views import PaymentOrderView, PaymentOrderListView, PaymentOrderDatatableView

app_name = 'payment'

urlpatterns = [
    path('local/payment/', PaymentOrderView.as_view(), name='local.payment'),
    path('local/payment/<int:pk>/', PaymentOrderView.as_view(), name='local.payment.update'),
    path('local/payment/list/', PaymentOrderListView.as_view(), name='local.payment.list'),
    path('local/payment/datatable/', PaymentOrderDatatableView.as_view(), name='local.payment.datatable'),
]
