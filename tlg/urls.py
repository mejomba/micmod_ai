from django.urls import path

from . import views

app_name = 'tlg'
urlpatterns = [
    path('message/list/', views.MessageList.as_view(), name='message.list'),
    path('message_list_datatable/', views.MessageListDatatableView.as_view(), name='message.list.datatable'),
    path('message/create_update/', views.MessageView.as_view(), name='message.create_update'),
    path('message/create_update/<int:pk>/', views.MessageView.as_view(), name='message.create_update'),

    path('send_code/', views.send_code, name='send_code'),
    path('verify_code/', views.verify_code, name='verify_code'),

    path('receiver/list/', views.ReceiverListView.as_view(), name='receiver.list'),
    path('receiver/create_update/', views.ReceiverCreateOrUpdateView.as_view(), name='receiver.create_update'),
    path('receiver/create_update/<int:pk>/', views.ReceiverCreateOrUpdateView.as_view(), name='receiver.create_update'),
    path('receiver_list_datatable/', views.ReceiverListDatatableView.as_view(), name='receiver.list.datatable'),

    path('get_sender/', views.get_sender, name='message.get_sender'),
]