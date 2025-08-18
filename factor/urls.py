from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views
from .views import CustomerRequestFactorViewSet

router = DefaultRouter()
router.register(r'customer-request-factor', CustomerRequestFactorViewSet, basename='customer-factor')

app_name = 'factor'

urlpatterns = [
    path('', include(router.urls)),
    path('view/', views.FactorView.as_view(), name='factor.view'),
    path('view/<int:pk>/', views.FactorView.as_view(), name='factor.view'),
    path('direct/', views.DirectFactorView.as_view(), name='factor.direct'),
    path('list/', views.FactorsList.as_view(), name='factor.list'),
    path('search/', views.search_factor_view, name='factor.search'),
    path('ajax/get_quotation_items_for_factor/<int:pk>/', views.get_quotation_items_for_factor, name='factor.get_quotation_items_for_factor'),
    path('factor/list/datatable/', views.FactorListDatatable.as_view(), name='factor.list.datatable'),
    path('factor/print/<int:id>/', views.print_view, name='factor.print'),
    path('delivery/', views.DeliveryList.as_view(), name='delivery.view'),
    path('delivery/<int:pk>/', views.DeliveryList.as_view(), name='delivery.update'),
    path('delivery/datatable/', views.DeliveryDatatableView.as_view(), name='delivery.datatable'),
    path('wh/packing/', views.WhPacking.as_view(), name='wh.packing'),
]
