from django.urls import path

from . import views

app_name = 'core'
urlpatterns = [
    path('excel/download/', views.download_excel, name='export_excel'),
    path('<str:app_label>/<str:model_name>/<int:content_type>/<int:object_id>/', views.CommentsFormView.as_view(), name='comment.form'),

    # path("ajax/<str:app_label>/<str:model_name>/list",views.BaseCustomListView.as_view(), name='ajax_objects_list'),
    # path("<str:app_label>/<str:model_name>/list",views.download_excel, name='objects_list'),
    # path("ajax/<str:app_label>/<str:model_name>/create",views.download_excel, name='ajax_object_create'),
    path("ajax/<str:app_label>/<str:model_name>/up_create", views.CustomCreateViewAjax.as_view(), name='ajax_object_create'),
    # path("<str:app_label>/<str:model_name>/create",views.BaseCustomCreateView.as_view(), name='object_create'),
    # path("ajax/<str:app_label>/<str:model_name>/update/<int:pk>",views.download_excel, name='ajax_object_update'),
    # path("<str:app_label>/<str:model_name>/update/<int:pk>", views.BaseCustomCreateView.as_view(), name='object_update'),
    path("<str:app_label>/<str:model_name>/up_create", views.CustomCreateView.as_view(), name='object_update'),
    # path("ajax/<str:app_label>/<str:model_name>/view/<int:pk>",views.download_excel, name='ajax_object_view'),
    # path("<str:app_label>/<str:model_name>/view/<int:pk>",views.download_excel, name='object_view'),
    # path("ajax/<str:app_label>/<str:model_name>/view/<int:pk>",views.download_excel, name='ajax_object_delete'),
    # path("<str:app_label>/<str:model_name>/view/<int:pk>",views.download_excel, name='object_delete'),
    # path('excel/download/', views.download_excel, name='export_excel'),
]
