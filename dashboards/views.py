from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404
from django.views import View
from django.views.generic import TemplateView
from django.http import HttpResponse
from django.conf import settings
from django.urls import resolve, reverse
from _keenthemes.__init__ import KTLayout
from _keenthemes.libs.theme import KTTheme
from pprint import pprint
from django.core.paginator import Paginator
from urllib.parse import urlencode

from core.views import BaseView
from dashboards.models import BIReport

"""
This file is a view controller for multiple pages as a module.
Here you can override the page view layout.
Refer to dashboards/urls.py file for more pages.
"""


class DashboardsView(LoginRequiredMixin, TemplateView):
    """Landing page; operational metrics are temporarily disabled by default."""
    template_name = 'pages/dashboards/index.html'
    legacy_template_name = 'pages/dashboards/legacy_index.html'

    def get_template_names(self):
        # Preserve explicit non-home template overrides (e.g. the error route).
        if (self.template_name == DashboardsView.template_name
                and not getattr(settings, 'OPERATIONAL_DASHBOARD_ENABLED', False)):
            return [self.legacy_template_name]
        return super().get_template_names()

    def get_context_data(self, **kwargs):
        context = KTLayout.init(super().get_context_data(**kwargs))

        # Keep authentication and the complete theme/layout initialization, but
        # bypass report imports, database queries and calculations while disabled.
        if not getattr(settings, 'OPERATIONAL_DASHBOARD_ENABLED', False):
            if self.template_name == DashboardsView.template_name:
                # Restore the original vendors used by the legacy admin widgets.
                KTTheme.addVendors(['amcharts', 'amcharts-maps', 'amcharts-stock'])
            return context

        from dashboards.operational_reports import build_report

        context['report'] = build_report(
            self.request.user,
            days=self.request.GET.get('days', 30),
            selected_user_id=self.request.GET.get('user_id'),
        )
        return context



class SalesWorkItemsView(LoginRequiredMixin, TemplateView):
    """Paginated, permission-scoped links to the user's *current* sales work."""
    template_name = 'pages/dashboards/sales_work_items.html'

    def get_context_data(self, **kwargs):
        from dashboards.operational_reports import (
            active_sales_queryset, clamp_days, visible_users,
        )
        from factor.models import Factor
        from micmod_base.models import Quotation

        context = KTLayout.init(super().get_context_data(**kwargs))
        user_qs, scope = visible_users(self.request.user)
        target = get_object_or_404(user_qs, pk=self.kwargs['user_id'])

        kind = self.request.GET.get('type', 'factor')
        if kind not in ('factor', 'quotation'):
            kind = 'factor'

        model = Factor if kind == 'factor' else Quotation
        route = 'factor:factor.view' if kind == 'factor' else 'micmod_base:quotations.view'
        base_qs = active_sales_queryset(model, [target.pk])
        qs = base_qs.select_related('customer_party_id', 'last_work_flow').order_by(
            '-last_update_date', '-pk'
        )
        page = Paginator(qs, 20).get_page(self.request.GET.get('page'))
        documents = [
            {
                'id': doc.pk,
                'url': reverse(route, kwargs={'pk': doc.pk}),
                'customer': getattr(doc.customer_party_id, 'title', '') or '',
                'state': doc.last_work_flow.current_state_name or 'در جریان',
            }
            for doc in page.object_list
        ]
        days = clamp_days(self.request.GET.get('days', 30))
        base_url = reverse('dashboards:sales_work_items',
                           kwargs={'user_id': target.pk})
        common = {'days': days}
        context.update({
            'subject_user': target,
            'kind': kind,
            'scope': scope,
            'days': days,
            'documents': documents,
            'page_obj': page,
            'factor_count': active_sales_queryset(Factor, [target.pk]).count(),
            'quotation_count': active_sales_queryset(Quotation, [target.pk]).count(),
            'factor_tab_url': base_url + '?' + urlencode({**common, 'type': 'factor'}),
            'quotation_tab_url': base_url + '?' + urlencode({**common, 'type': 'quotation'}),
            'back_url': reverse('dashboards:index') + '?' + urlencode(
                {'days': days, 'user_id': target.pk}
            ),
        })
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
