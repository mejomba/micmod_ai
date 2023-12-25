from django.urls import path
from .views import *
from django.views.decorators.cache import cache_page

app_name = "IMEI"
urlpatterns = [
    path(r"imei_list_reg/view/<int:id>/", view=IMEIListRegView.as_view(), name="imei_list_reg.view",),
    path(r"imei_list_reg/delete/<int:id>/", view=IMEIListRegView.as_view(), name="imei_list_reg.delete",),
    path(r"imei_list_reg/create/", view=IMEIListRegCreateView.as_view(), name="imei_list_reg.create",),
    path(r"imei_list_reg/", view=IMEIListRegShowView.as_view(), name="imei_list_reg.list",),

    path(r"imei_ntsw_reg/view/<int:id>/", view=IMEIINTSWReg.as_view(), name='imei_ntsw_reg.view',),
    path(r"imei_ntsw_reg/delete/<int:id>/", view=IMEIINTSWReg.as_view(), name='imei_ntsw_reg.delete',),
    path(r"imei_ntsw_reg/create/", view=IMEIINTSWCreatReg.as_view(), name='imei_ntsw_reg.create',),
    path(r"imei_ntsw_reg/", view=IMEIINTSWRegShowView.as_view(), name="imei_ntsw_reg.list"),

    path(r"imei_sale_reg/view/<int:id>/", view=IMEISaleRegView.as_view(), name="imei_sale_reg.view",),
    path(r"imei_sale_reg/delete/<int:id>/", view=IMEISaleRegView.as_view(), name="imei_sale_reg.delete",),
    path(r"imei_sale_reg/create/", view=IMEISaleCreatReg.as_view(), name="imei_sale_reg.create",),
    path(r"imei_sale_reg/", view=IMEISaleRegShowView.as_view(), name="imei_sale_reg.list",),

    path(r"imei_err_reg/view/<int:id>/", view=IMEIErrRegView.as_view(), name="imei_err_reg.view",),
    path(r"imei_err_reg/delete/<int:id>/", view=IMEIErrRegView.as_view(), name="imei_err_reg.delete",),
    path(r"imei_err_reg/create/", view=IMEIErrCreatReg.as_view(), name="imei_err_reg.create",),
    path(r"imei_err_reg/", view=IMEIErrRegShowView.as_view(), name="imei_err_reg.list",),

    path(r"imei_all_list/", IMEIAllListShowView.as_view(), name="imei_all_list",),

    # path(r"box_imei/<str:box_number>/", view=imei_related_on_box, name="imei_related_on_box",),
    path(r"imei_sale_reg/view/<int:id>/<str:box_number>/", view=imei_related_on_box, name="imei_related_on_box",),

    path('test_ajax_datatable/', TestAjaxDatatableView.as_view(), name="test_ajax_datatable"),
    path('imei_reg_datatable/<int:id>/', ImeiRegDatatableView.as_view(), name="imei_reg_datatable.view"),

    path(r'icon/', icon, name='icon')
]
