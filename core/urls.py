from django.urls import path

from . import views

app_name = 'core'
urlpatterns = [
    path('excel/download/', views.download_excel, name='export_excel'),
    path('<str:app_label>/<str:model_name>/<int:content_type>/<int:object_id>/', views.CommentsFormView.as_view(), name='comment.form')
]
