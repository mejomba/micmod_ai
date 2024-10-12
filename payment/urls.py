from django.urls import path
from .views import (LocalPaymentOrderView, PaymentOrderListView, PaymentOrderDatatableView, num_to_fa_words,
                    LocalPaymentDoc)

app_name = 'payment'

urlpatterns = [
    path('local/payment/', LocalPaymentOrderView.as_view(), name='local.payment'),
    path('local/payment/<int:pk>/', LocalPaymentOrderView.as_view(), name='local.payment.update'),
    path('local/payment/list/', PaymentOrderListView.as_view(), name='local.payment.list'),
    path('local/payment/datatable/', PaymentOrderDatatableView.as_view(), name='local.payment.datatable'),
    path('toman/amount/', num_to_fa_words, name='toman.amount'),
    path('local/payment/doc/', LocalPaymentDoc.as_view(), name='local.payment.doc'),

    path('pay/document/create/', LocalPaymentDoc.as_view(), name='local.payment.doc.create'),
    path('pay/document/update/<int:pk>/', LocalPaymentDoc.as_view(), name='local.payment.doc.update'),
]
