from django.urls import path

from .views import ShowLogHistory

app_name = 'changelog'
urlpatterns = [
    path('', ShowLogHistory.as_view(), name='log.history')
]
