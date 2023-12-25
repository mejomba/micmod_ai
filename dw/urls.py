from django.urls import path
from .views import *

app_name = "dw"
urlpatterns = [
    # Ecommerce
    path(
        r"item",
        view=Item.as_view(),
        name="quotations.view",
    ),
    path(r"order_list", view=OrderList.as_view(), name="order.list",),
    path(r"order_list_datatable/", view=OrderListDatatable.as_view(), name="order_list.datatable",),

    path(r"cargo_list", view=CargoList.as_view(), name="cargo.list",),
    path(r"cargo_list_datatable/", view=CargoListDatatable.as_view(), name="cargo_list.datatable",),
    ]
