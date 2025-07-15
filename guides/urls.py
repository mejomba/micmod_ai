from django.urls import path

from . import views

app_name = 'guides'

urlpatterns = [
    path('guides/', views.GuidesList.as_view(), name='guides.view'),
    path('guides/<int:pk>/', views.GuidesList.as_view(), name='guides.update'),
    path('guides/datatable/', views.GuidesDatatableView.as_view(), name='guides.datatable'),

]
