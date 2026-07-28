from django.urls import path
from .views import *
app_name = "accounts"
urlpatterns = [
    # Ecommerce
    # path(
    #     "404",
    #     view=handler404,
    #     name="404",
    # ),
    path(
        "profile/",
        view=ProfileView.as_view(),
        name="profile",
    ),
    path('permission/view/', PermissionView.as_view(), name="permission.view"),
    path('permission/view/<int:pk>/', PermissionView.as_view(), name="permission.view"),
    path('permission/list/datatable/', PermissionDataTableView.as_view(), name="permissions.datatable")
]
