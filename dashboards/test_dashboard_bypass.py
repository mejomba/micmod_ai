"""Regression coverage for the temporary home-page dashboard bypass."""
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from dashboards.views import DashboardsView


class DashboardBypassUnitTests(SimpleTestCase):
    def view(self, **kwargs):
        view = DashboardsView(**kwargs)
        request = RequestFactory().get('/', {'days': '7', 'user_id': 'invalid'})
        request.user = SimpleNamespace(is_authenticated=True)
        view.setup(request)
        return view

    @override_settings(OPERATIONAL_DASHBOARD_ENABLED=False)
    @patch('dashboards.operational_reports.build_report')
    @patch('dashboards.views.KTTheme.addVendors')
    @patch('dashboards.views.KTLayout.init', side_effect=lambda context: {**context, 'layout': 'default.html'})
    def test_disabled_skips_report_and_preserves_layout(self, layout, vendors, report):
        view = self.view()
        context = view.get_context_data()
        self.assertEqual(view.get_template_names(), ['pages/dashboards/legacy_index.html'])
        self.assertEqual(context['layout'], 'default.html')
        self.assertNotIn('report', context)
        layout.assert_called_once()
        vendors.assert_called_once_with(['amcharts', 'amcharts-maps', 'amcharts-stock'])
        report.assert_not_called()

    @override_settings(OPERATIONAL_DASHBOARD_ENABLED=False)
    def test_explicit_error_template_is_not_replaced(self):
        view = self.view(template_name='non-exist-file.html')
        self.assertEqual(view.get_template_names(), ['non-exist-file.html'])

    @override_settings(OPERATIONAL_DASHBOARD_ENABLED=True)
    @patch('dashboards.operational_reports.build_report', return_value={'days': 7})
    @patch('dashboards.views.KTLayout.init', side_effect=lambda context: {**context, 'layout': 'default.html'})
    def test_enabled_retains_operational_report(self, layout, report):
        view = self.view()
        context = view.get_context_data()
        self.assertEqual(view.get_template_names(), ['pages/dashboards/index.html'])
        self.assertEqual(context['report'], {'days': 7})
        report.assert_called_once_with(view.request.user, days='7', selected_user_id='invalid')


@override_settings(OPERATIONAL_DASHBOARD_ENABLED=False)
class DashboardBypassPageTests(TestCase):
    @patch('dashboards.operational_reports.build_report')
    def test_authenticated_home_renders_legacy_for_regular_and_superuser(self, report):
        User = get_user_model()
        for admin in (False, True):
            with self.subTest(admin=admin):
                user = User.objects.create_user(username='legacy-home-' + str(admin),
                                                password='pass', is_superuser=admin, is_staff=admin)
                self.client.force_login(user)
                response = self.client.get(reverse('dashboards:index'), {'days': '7', 'user_id': 'invalid'})
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, 'pages/dashboards/legacy_index.html')
                self.assertNotContains(response, 'id="op-dashboard"')
                self.assertNotContains(response, 'operational-dashboard.js')
                self.assertNotContains(response, 'operational-dashboard.css')
                self.assertTrue(response.context['layout'])
                self.client.logout()
        report.assert_not_called()

    @patch('dashboards.operational_reports.build_report')
    def test_anonymous_home_still_redirects(self, report):
        response = self.client.get(reverse('dashboards:index'))
        self.assertEqual(response.status_code, 302)
        report.assert_not_called()
