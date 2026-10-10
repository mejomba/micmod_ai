from django.urls import path

from .views import SupplyTrackingDetailView, SupplyTrackingListView

app_name = "supply_tracking"

urlpatterns = [
    path("", SupplyTrackingListView.as_view(), name="list"),
    path("<str:tracking_id>/", SupplyTrackingDetailView.as_view(), name="detail"),
]
