from django.urls import path
from .views import PaymentOrderView, PaymentOrderListView

app_name = 'payment'

urlpatterns = [
    path('local/payment/', PaymentOrderView.as_view(), name='local.payment'),
    path('local/payment/list/', PaymentOrderListView.as_view(), name='local.payment.list'),
]
