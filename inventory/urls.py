from django.urls import path

from .views import (ReceiptCreate,
                    ReceiptList,
                    ReceiptUpdate,
                    ReceiptDetailList,
                    receipt_list_json)


app_name = 'inventory'

urlpatterns = [
    path('receipt/create/', ReceiptCreate.as_view(), name='receipt.create'),
    path('receipt/update/<int:pk>/', ReceiptUpdate.as_view(), name='receipt.update'),
    path('receipt/list/', ReceiptList.as_view(), name='receipt.list'),

    path('receipt/list/json/', receipt_list_json, name='receipt_list.json'),

    path('receipt_detail/list/', ReceiptDetailList.as_view(), name='receipt_detail.list'),
]
