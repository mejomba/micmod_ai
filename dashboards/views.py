from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views import View
from django.views.generic import TemplateView
from django.http import HttpResponse
from django.conf import settings
from django.urls import resolve
from _keenthemes.__init__ import KTLayout
from _keenthemes.libs.theme import KTTheme
from pprint import pprint

from core.views import BaseView
from dashboards.models import BIReport

"""
This file is a view controller for multiple pages as a module.
Here you can override the page view layout.
Refer to dashboards/urls.py file for more pages.
"""


class DashboardsView(LoginRequiredMixin, TemplateView):
    # Default template file
    # Refer to dashboards/urls.py file for more pages and template files
    template_name = 'pages/dashboards/index.html'

    # Predefined function
    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)

        """
        # Example to get page name. Refer to dashboards/urls.py file.
        url_name = resolve(self.request.path_info).url_name

        if url_name == 'dashboard-2':
            # Example to override settings at the runtime
            settings.KT_THEME_DIRECTION = 'rtl'
        else:
            settings.KT_THEME_DIRECTION = 'ltr'
        """

        # A function to init the global layout. It is defined in _keenthemes/__init__.py file
        context = KTLayout.init(context)

        # Include vendors and javascript files for dashboard widgets
        KTTheme.addVendors(['amcharts', 'amcharts-maps', 'amcharts-stock'])

        return context


class BIView(View):
    def get(self, request, pk):
        from urllib.parse import urlparse, urlencode, urlunparse, quote
        from tools.utils import generate_powerbi_filter

        bi_obj = BIReport.objects.filter(pk=pk).first()
        url = bi_obj.url if bi_obj else ''

        if request.user:
            if bi_filter := generate_powerbi_filter(request.user.bi_filter, pk):
                url += bi_filter

        host = request.META.get('HTTP_HOST')
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        print("x_forwarded_for: ", x_forwarded_for)
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR")

        if not ip:
            ip = x_forwarded_for.split(",")[1].strip()

        # if host.split(':')[0] == '94.182.194.120':
        is_external = False
        # if '192.168.1.9' in ip: # == '94.182.194.120':
        # url = url.replace('192.168.1.80', '94.182.194.120:4040')
        # is_external = True
        print('url:====== ', url, 'is_external:=======', is_external)
        parsed = urlparse(url)
        encoded_query = quote(parsed.query, safe="=&:")
        valid_url = urlunparse(parsed._replace(query=encoded_query))
        context = {'url': valid_url, 'title': bi_obj.name, 'is_external': is_external}
        return render(request, 'dashboards/bi_report.html', context)
