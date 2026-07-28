from ajax_datatable import AjaxDatatableView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import Permission
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import render
from django.template import RequestContext
from django.views.generic.detail import SingleObjectTemplateResponseMixin
from django.views.generic.edit import ModelFormMixin, ProcessFormView

from accounts.mixins import FormFieldAccessMixin
from accounts.extra_models import Profile
from core.views import BaseView
from .forms import ProfileForm, PermissionForm
from workflow.views import FlowBaseView
from django.http import HttpResponseRedirect


# Create your views here.

# def handler404(request, exception, template_name="404.html"):
#     response = render_to_response(template_name)
#     response.status_code = 404
#     return response


class ProfileView(BaseView):
    template_name = 'accounts/profile_page.html'
    model = Profile
    form_class = ProfileForm
    success_url = '#'

    # def get(self,request, *args, **kwargs):
    #     ...
    def post(self, request, *args, **kwargs):
        frm = self.form_class(self.request.POST,self.request.FILES, instance=self.request.user.profile)
        if frm.is_valid():
            return self.form_valid(frm)
        return HttpResponseRedirect(self.success_url)

    def form_valid(self, form):
        form.save()
        return HttpResponseRedirect(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile'] = Profile.get_or_create(user=self.request.user)
        context['form'] = ProfileForm(instance=context['profile'])
        return context


class PermissionView(BaseView):
    template_name = 'permissions.html'
    model = Permission
    form_class = PermissionForm
    success_url = '#'

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        obj = form.save()
        return HttpResponseRedirect(self.success_url)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class PermissionDataTableView(AjaxDatatableView):
    model = Permission
    title = 'permission'
    initial_order = [["name", "des"], ]
    length_menu = [[15, 25, 50, -1], [15, 25, 50, 'همه (ممکن است کمی طول بکشد)']]
    search_values_separator = '+'
    render_row_details_template_name = 'sku_list_detail.html'

    column_defs = [
        AjaxDatatableView.render_row_tools_column_def(),
        # {'name': 'id', 'visible': True, 'title': 'pk', 'className': 'py-1 border', },
        {'name': 'name', 'visible': True, 'title': 'name', 'className': 'py-1 border', 'defaultContent': '<a href"#">test</a>', 'lookup_field': '__icontains'},
        {'name': 'content_type', 'visible': True, 'title': 'content_type', 'className': 'py-1 border',},
        {'name': 'codename', 'visible': True, 'title': 'codename', 'className': 'py-1 border', },
    ]

    def get_initial_queryset(self, request=None):
        return Permission.objects.all()
