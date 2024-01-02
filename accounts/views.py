from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import render
from django.template import RequestContext
from django.views.generic.detail import SingleObjectTemplateResponseMixin
from django.views.generic.edit import ModelFormMixin, ProcessFormView

from accounts.mixins import FormFieldAccessMixin
from accounts.extra_models import Profile
from core.views import BaseView
from .forms import ProfileForm
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
        context['profile'], _ = Profile.objects.get_or_create(user=self.request.user)
        context['form'] = ProfileForm(instance=context['profile'])
        return context
