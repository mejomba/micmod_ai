from django.urls import path

from . import views

app_name = 'core'
urlpatterns = [
    path('excel/download/', views.download_excel, name='export_excel')
]
