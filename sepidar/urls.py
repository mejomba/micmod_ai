from django.urls import path
from .views import *
from .views import *
from .ajax_datatable_views import AjaxSalesHistory
app_name = "sepidar"
urlpatterns = [
    # Ecommerce
    path(
        "customers_list",
        view=get_customers,
        name="customers_list",
    ),
    path(
        "customers_for_shop_list",
        view=get_customers_for_shop,
        name="customers_for_shop_list",
    ),
    path(
        "user_for_shop_list",
        view=get_user_for_shop,
        name="user_for_shop_list",
    ),
    path("items_list", view=get_items, name="get_items"),
    path("items_list2", view=get_items2, name="get_items2", ),
    path("item_list2", view=get_item2, name="get_items2",),
    path("item_list", view=get_item, name="get_items"),
    path(r"dl/accounting", view=SuppliersAccountingList.as_view(), name="dl.accounting"),
    path(r"ajax/sales_history/", view=AjaxSalesHistory.as_view(), name="ajax_sales_history"),
    path(r"sales_history/", view=SalesHistory.as_view(), name="sales_history"),
    path(r"buy_history/", view=BuyHistory.as_view(), name="buy_history"),
    path(r"api_call/", view=test_get, name="test_get"),
    ]