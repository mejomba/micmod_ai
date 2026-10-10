from django.urls import include, path

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from .views import *

app_name = 'api'
urlpatterns = [
    # jwt auth
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),

    # shop tracking
    path('v1/shop/supply-tracking/', include('api.supply_tracking.urls')),

    # my api
    path('telbot/customer_register', TelBotRegisterUserAPI.as_view(), name='telbot.customer.register'),
    path('ajax/call/<str:app>/<str:model>/', AjaxInquiryResult.as_view(), name='ajax_call'),
    path('customer/list/', CustomerListAPI.as_view(), name='customer.list')
]
