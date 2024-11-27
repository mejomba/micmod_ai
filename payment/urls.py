from django.urls import path
from .views import (LocalPaymentOrderView, PaymentOrderListView, PaymentOrderDatatableView, num_to_fa_words,
                    LocalPaymentDoc, CreditCardView, CreditCardDatatableView, CreditCardAjax, GenericPaymentView,
                    GenericPaymentListView, GenericPaymentDataTableListView)

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

    path('local/crdit_card/', CreditCardView.as_view(), name='credit_card'),
    path('local/crdit_card/<int:pk>/', CreditCardView.as_view(), name='credit_card.update'),
    path('local/crdit_card/datatable/', CreditCardDatatableView.as_view(), name='credit_card.datatable'),
    path('local/crdit_card/ajax/', CreditCardAjax.as_view(), name='credit_card.ajax'),

    #  generic payment
    path('generic/payment/view/', GenericPaymentView.as_view(), name='generic.payment.view'),
    path('generic/payment/view/<int:pk>/', GenericPaymentView.as_view(), name='generic.payment.update'),
    path('generic/payment/list/', GenericPaymentListView.as_view(), name='generic.payment.list'),
    path('generic/payment/list/datatable/', GenericPaymentDataTableListView.as_view(), name='generic.payment.list.datatable'),

     # paymentitem
    # path('paymentitem/view/', PaymentItemView.as_view(), name='paymentitem.view'),
    # path('paymentitem/update/<int:pk>/',PaymentItemView.as_view(), name='paymentitem.update'),
]
