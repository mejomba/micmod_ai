from django.urls import path

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

    # my api
    path('telbot/customer_register', TelBotRegisterUserAPI.as_view(), name='telbot.customer.register'),
    path('ajax/call/<str:app>/<str:model>/', AjaxInquiryResult.as_view(), name='ajax_call')
]
