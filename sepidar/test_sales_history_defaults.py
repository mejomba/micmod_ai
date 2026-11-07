"""Default-window and filter-reset regression tests for sales history."""
from datetime import date, timedelta
from unittest.mock import patch

import jdatetime
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from sepidar.views import SalesHistory


class SalesHistoryDefaultWindowTests(SimpleTestCase):
    TODAY = date(2026, 11, 7)

    def _get(self, params=None, ajax=False):
        options = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'} if ajax else {}
        request = RequestFactory().get('/sepidar/sales-history/', params or {}, **options)
        with (
            patch('django.utils.timezone.localdate', return_value=self.TODAY),
            patch('sepidar.views.Dl.get_sales_history_list',
                  return_value=([], False)) as report,
            patch('sepidar.views.render', return_value=HttpResponse('OK')) as page,
            patch('django.template.loader.render_to_string', return_value=''),
        ):
            response = SalesHistory().get(request)
        filters = report.call_args.args[0]
        context = page.call_args.args[2] if not ajax else None
        return filters, context, response

    def test_initial_visit_loads_only_seven_calendar_days(self):
        filters, context, response = self._get()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(context['recent_default'])
        self.assertEqual(filters['date_from'], (self.TODAY - timedelta(days=6)).isoformat())
        self.assertEqual(filters['date_to'], self.TODAY.isoformat())
        self.assertEqual(
            context['recent_from'],
            jdatetime.date.fromgregorian(date=self.TODAY - timedelta(days=6)).strftime('%Y/%m/%d'),
        )

    def test_reset_request_without_filters_uses_same_seven_days(self):
        filters, context, _ = self._get(ajax=False)
        self.assertTrue(context['recent_default'])
        self.assertNotIn('all_dates', filters)
        self.assertEqual(filters['date_from'], '2026-11-01')

    def test_explicit_column_filter_searches_all_history(self):
        filters, context, _ = self._get({'col_4': '899'})
        self.assertFalse(context['recent_default'])
        self.assertEqual(filters['col_4'], '899')
        self.assertNotIn('date_from', filters)
        self.assertNotIn('date_to', filters)

    def test_explicit_custom_date_range_is_preserved(self):
        filters, context, _ = self._get(
            {'date_from': '1405/07/01', 'date_to': '1405/07/30'}
        )
        self.assertFalse(context['recent_default'])
        self.assertEqual(filters['date_from'], '1405/07/01')
        self.assertEqual(filters['date_to'], '1405/07/30')

    def test_explicit_all_history_link_remains_available(self):
        filters, context, _ = self._get({'all_dates': '1'})
        self.assertFalse(context['recent_default'])
        self.assertNotIn('date_from', filters)
        self.assertNotIn('date_to', filters)

    def test_ajax_default_includes_correct_seven_and_thirty_day_dates(self):
        import json
        filters, _, response = self._get(ajax=True)
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))
        self.assertTrue(payload['recent_default'])
        self.assertEqual(filters['date_from'], '2026-11-01')
        self.assertEqual(
            payload['recent_30_from'],
            jdatetime.date.fromgregorian(date=self.TODAY - timedelta(days=29)).strftime('%Y/%m/%d'),
        )
        self.assertEqual(
            payload['recent_to'],
            jdatetime.date.fromgregorian(date=self.TODAY).strftime('%Y/%m/%d'),
        )
