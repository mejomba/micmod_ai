from django.urls import path
from .views import *
app_name = "notifications"
urlpatterns = [
    path("notification_menu_list", view=notification_menu_list, name="notification_menu_list"),
    ]