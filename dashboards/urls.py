from django.urls import path
from django.conf import settings
from dashboards.views import DashboardsView, BIView, SalesWorkItemsView

app_name = 'dashboards'

urlpatterns = [
    path('', DashboardsView.as_view(template_name='pages/dashboards/index.html'), name='index'),

    path('work-items/<int:user_id>/', SalesWorkItemsView.as_view(), name='sales_work_items'),

    path('error', DashboardsView.as_view(template_name = 'non-exist-file.html'), name='Error Page'),
    path('bi/report/<int:pk>/', BIView.as_view(), name='bi')
]