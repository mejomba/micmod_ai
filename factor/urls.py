from django.urls import path
from . import views

app_name = 'factor'

urlpatterns = [
    path('view/', views.FactorView.as_view(), name='factor.view'),
    path('view/<int:pk>/', views.FactorView.as_view(), name='factor.view'),
    path('direct/', views.DirectFactorView.as_view(), name='factor.direct'),
    path('list/', views.FactorsList.as_view(), name='factor.list'),
    path('search/', views.search_factor_view, name='factor.search'),
    path('ajax/get_quotation_items_for_factor/<int:pk>/', views.get_quotation_items_for_factor, name='factor.get_quotation_items_for_factor'),
    path('factor/list/datatable/', views.FactorListDatatable.as_view(), name='factor.list.datatable'),
]
