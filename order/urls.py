from django.urls import path
from . import views


app_name = 'order'
urlpatterns = [
    path('view/', views.OrderView.as_view(), name='order.view'),
]