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
]
