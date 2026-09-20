from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views
from .select2 import select2_search, select2_create_factor_from_quotation
from .views import CustomerRequestFactorViewSet, supply_fragment_view

router = DefaultRouter()
router.register(r'customer-request-factor', CustomerRequestFactorViewSet, basename='customer-factor')

app_name = 'factor'

urlpatterns = [
    path('', include(router.urls)),
    path('view/cancel/<int:pk>/', views.cancel_factor, name='factor.cancel'),
    path('view/', views.FactorView.as_view(), name='factor.view'),
    path('view/<int:pk>/', views.FactorView.as_view(), name='factor.view'),

    path('view/safe/', views.SafeFactorView.as_view(), name='safe.factor.view'),
    path('view/safe/<int:pk>/', views.SafeFactorView.as_view(), name='safe.factor.view'),

    path('direct/', views.DirectFactorView.as_view(), name='factor.direct'),
    path('list/', views.FactorsList.as_view(), name='factor.list'),
    path('search/', views.search_factor_view, name='factor.search'),

    path('ajax/get_quotation_items_for_factor/<int:pk>/', views.get_quotation_items_for_factor, name='factor.get_quotation_items_for_factor'),
    # path('ajax/get_quotation_items_for_factor_safe/<int:pk>/', views.get_quotation_items_for_factor_safe, name='factor.get_quotation_items_for_factor_safe'),
    # path('ajax/get_quotation_items_for_factor_safe/', views.SafeFactorView.as_view(), name='factor.get_quotation_items_for_factor_safe'),

    path('prefactor/<int:pk>/json/', views.prefactor_json, name='prefactor-json'),
    path('supply-fragment/', views.supply_fragment, name='supply-fragment'),
    path('<int:pk>/supply-fragment/', supply_fragment_view, name='factor_supply_fragment',),

    # path('ajax/get_quotation_items_for_factor/<int:pk>/safe/', views.safe_get_quotation_items_for_factor, name='safe.factor.get_quotation_items_for_factor'),

    path('factor/list/datatable/', views.FactorListDatatable.as_view(), name='factor.list.datatable'),
    path('factor/print/<int:id>/', views.print_view, name='factor.print'),
    path('delivery/', views.DeliveryList.as_view(), name='delivery.view'),
    path('delivery/<int:pk>/', views.DeliveryList.as_view(), name='delivery.update'),
    path('delivery/datatable/', views.DeliveryDatatableView.as_view(), name='delivery.datatable'),
    path('wh/packing/', views.WhPacking.as_view(), name='wh.packing'),
    path('ajax/get_supply_locations/<int:sku>/<int:factor_item_pk>/', views.get_supply_locations, name='get_supply_locations'),
    path('ajax/show_force_factor/', views.show_force_factor, name='show_force_factor'),
    path('ajax/show_accounting_confirm_factor/', views.show_accounting_confirm_factor, name='show_accounting_confirm_factor'),
    path("select2/<str:key>/", select2_search, name="select2-search"),
    # path("select2/create_factor_from_quotation/<str:key>/", select2_create_factor_from_quotation, name="select2_create_factor_from_quotation"),


    path('ajax/show_all_supplied_factor/', views.show_all_supplied_factor, name='show_all_supplied_factor'),
    path('ajax/empty_checker/', views.empty_checker, name='empty_checker'),
    path('ajax/factor_today_total_price/', views.factor_today_total_price, name='factor_today_total_price'),
    # path('ajax/factor_and_sepidar/', FactorAndSepidar.as_view(), name='factor_and_sepidar'),
    path('ajax/factor_today_total_price/', views.factor_today_total_price, name='factor_today_total_price'),
    path('ajax/product_select/<str:sku>/<int:factor_id>/', views.product_select, name='product.select'),

]
