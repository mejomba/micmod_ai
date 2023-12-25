from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views import View
from django.views.generic import TemplateView
from pprint import pprint
from _keenthemes.__init__ import KTLayout
from _keenthemes.libs.theme import KTTheme

from django.shortcuts import redirect, render
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from allauth.account.views import PasswordSetView, PasswordChangeView
from django_otp.plugins.otp_totp.models import TOTPDevice

class SystemView(TemplateView):
    template_name = 'pages/system/not-found.html'
    status = ''

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)

        # A function to init the global layout. It is defined in _keenthemes/__init__.py file
        context = KTLayout.init(context)

        # Define the layout for this module
        # _templates/layout/system.html
        context.update({
            'layout': KTTheme.setLayout('system.html', context),
            'status': self.status,
        })

        return context


class Settings(LoginRequiredMixin, View):
    template_name = "settings.html"

    def __init__(self, *args):
        super(Settings, self).__init__(*args)

    def get(self, request):
        k = TOTPDevice.objects.filter(user=request.user)
        context_data = {"k": k}
        return render(request, self.template_name, context_data)


class MyPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    success_url = reverse_lazy("dashboard")


class MyPasswordSetView(LoginRequiredMixin, PasswordSetView):
    success_url = reverse_lazy("dashboard")
