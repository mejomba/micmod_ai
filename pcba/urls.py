from django.urls import path

from pcba.views import *

app_name = 'pcba'


urlpatterns = [
    path('contracts/list/', ContractsList.as_view(), name='contracts.list'),
    path('contract/list/datatable', ContractListDatatable.as_view(), name='contract.list.datatable'),
    path('contracts/', ContractView.as_view(), name='contracts.view'),
    path('contracts/<int:pk>/', ContractView.as_view(), name='contracts.view'),
    path('customer/item/receipt/list/datatable', CustomerItemReceiptListDatatable.as_view(), name='customer.item.receipt.list.datatable'),
    path('customer/item/receipt/list/', CustomerItemReceiptList.as_view(), name='customer.item.receipt.list'),
    path('customer/item/receipt/', CustomerItemReceiptView.as_view(), name='customer.item.receipt.view'),
    path('customer/item/receipt/<int:pk>/', CustomerItemReceiptView.as_view(), name='customer.item.receipt.view'),
    path('project/item/list/', ProjectItemListView.as_view(), name='project.item.list'),
    path('project/item/list/<int:pk>/', ProjectItemListView.as_view(), name='project.item.list'),
    path('production/day/activities/', ProductionDayActivitiesView.as_view(), name='production.day.activities.view'),
    path('production/day/activities/<int:pk>/', ProductionDayActivitiesView.as_view(), name='production.day.activities.view'),
    path('production/day/activities/list/', ProductionDayActivityList.as_view(), name='production.day.activities.list'),
    path('production/day/activities/list/datatable', ProductionDayActivityListDatatable.as_view(), name='production.day.activities.list.datatable'),
    path('item/in/customer/receipt/', ItemInCustomerReceiptView.as_view(), name='item.in.customer.receipt.view'),
    path('item/in/customer/receipt/<int:pk>/', ItemInCustomerReceiptView.as_view(), name='item.in.customer.receipt.view'),
    path('contracts/select2/', get_contracts, name='contracts.select2.view'),
    path('parent/select2/', get_parents, name='parent.select2.view')
]

