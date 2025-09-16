from django.urls import path, re_path
from . import views

app_name = 'transportation'

urlpatterns = [
    path('trade_transportation_method/view', views.TradeTransportationMethodView.as_view(), name='trade_transportation_method.view'),
    path('trade_transportation_method/view/<int:pk>', views.TradeTransportationMethodView.as_view(), name='trade_transportation_method.update'),
    path('trade_transportation_method/datatable', views.TradeTransportationMethodDataTableView.as_view(), name='trade_transportation_method.list.datatable'),

    path('trade_transportation_calender/view', views.TransportationCalenderView.as_view(), name='transportation_calender.view'),
    path('trade_transportation_calender/view/<int:pk>', views.TransportationCalenderView.as_view(), name='transportation_calender.update'),
    path('trade_transportation_calender/datatable', views.TransportationCalenderViewDataTableView.as_view(), name='transportation_calender.list.datatable')
]
