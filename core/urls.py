from django.urls import path

from . import views


app_name = 'core'
urlpatterns = [
    path('excel/download/', views.download_excel, name='export_excel'),
    path('<str:app_label>/<str:model_name>/<int:content_type>/<int:object_id>/', views.CommentsFormView.as_view(), name='comment.form'),
    path('<str:app_label>/<str:model_name>/<int:content_type>/<int:object_id>/<str:app_label_rel>/<str:model_name_rel>/<int:content_type_rel>/<int:object_id_rel>/', views.CommentsFormView.as_view(), name='comment.form.rel'),

    path('generic_payment/<str:app_label>/<str:model_name>/<int:content_type>/<int:object_id>/', views.PaymentFormView.as_view(), name='generic_payment.form'),

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
    path("ajax/changelog/<str:app_name>/<str:model_name>/<int:object_id>/", views.ajax_change_logs, name="changelog"),
    path('delete/confirm/', views.delete_confirm, name="delete.confirm"),
    path('delete/', views.delete_ajax, name="delete"),
    path('import_customer_from_sepidar/', views.ImportCustomerFromSepidar.as_view(), name='import_customer_from_sepidar'),
    path('select2/<str:app_name>/<str:model_name>/<str:title>/', views.Select2BaseSearch.as_view(), name='select2.base.search'),
    path('api_call/<str:app_name>/<str:model_name>/<str:function>/', views.GenericApiCall.as_view(), name='generic.api.call'),
    path('get_user_pin/', views.get_user_pins, name='get_user_pin'),
    # path("save_user_pins/", views.save_user_pins, name="save_user_pins"),
    path("add_pin/", views.add_pin, name="add_pin"),
    path("delete_pin/", views.delete_pin, name="delete_pin"),
    path("ajax/work_notify", views.WorkNotify.as_view(), name="work_notify"),
]
