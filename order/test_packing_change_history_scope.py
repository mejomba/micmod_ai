"""Ensure that the Packing audit modal never receives another record's logs."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, sentinel

from django.http import Http404
from django.test import SimpleTestCase

from order.models import Packing, PackingItem
from order.views import QuickPackingView


class PackingChangeHistoryScopeTests(SimpleTestCase):
    def setUp(self):
        self.view = QuickPackingView()
        self.packing = SimpleNamespace(pk=77)

    def test_header_queries_only_packing_model_and_its_exact_id(self):
        request = SimpleNamespace(GET={'audit_scope': 'header'})
        with (
            patch('order.views.ContentType.objects.get_for_model', return_value=sentinel.type) as content_type,
            patch('order.views.ChangeLog.objects.filter') as logs,
            patch('order.views.PackingItem.objects.full_queryset') as rows,
            patch('order.views.build_packing_change_history', return_value=[]) as build,
            patch('order.views.render', return_value=sentinel.response) as render,
        ):
            result = self.view._render_change_history(request, self.packing)

        self.assertIs(result, sentinel.response)
        content_type.assert_called_once_with(Packing)
        logs.assert_called_once_with(content_type=sentinel.type, object_id=77)
        rows.assert_not_called()
        self.assertEqual(build.call_args.args[3], [])
        self.assertEqual(render.call_args.args[2]['change_history'], [])

    def test_item_queries_only_item_belonging_to_current_packing(self):
        request = SimpleNamespace(GET={'audit_scope': 'item', 'audit_item_id': '19'})
        item = {
            'id': 19, 'part_number': 'PN-19', 'order_id': 123,
            'order__order_number': 'ORD-123',
        }
        with (
            patch('order.views.ContentType.objects.get_for_model', return_value=sentinel.type) as content_type,
            patch('order.views.ChangeLog.objects.filter') as logs,
            patch('order.views.PackingItem.objects.full_queryset') as rows,
            patch('order.views.build_packing_change_history', return_value=[]) as build,
            patch('order.views.render', return_value=sentinel.response),
        ):
            rows.return_value.filter.return_value.values.return_value = [item]
            self.view._render_change_history(request, self.packing)

        rows.return_value.filter.assert_called_once_with(pk=19, packing_id=77)
        content_type.assert_called_once_with(PackingItem)
        logs.assert_called_once_with(content_type=sentinel.type, object_id=19)
        self.assertEqual(build.call_args.args[3], [item])

    def test_item_from_another_packing_is_rejected_before_audit_query(self):
        request = SimpleNamespace(GET={'audit_scope': 'item', 'audit_item_id': '19'})
        with (
            patch('order.views.PackingItem.objects.full_queryset') as rows,
            patch('order.views.ChangeLog.objects.filter') as logs,
        ):
            rows.return_value.filter.return_value.values.return_value = []
            with self.assertRaises(Http404):
                self.view._render_change_history(request, self.packing)
            logs.assert_not_called()

    def test_non_numeric_item_id_cannot_query_audit(self):
        request = SimpleNamespace(GET={'audit_scope': 'item', 'audit_item_id': '19xyz'})
        with patch('order.views.ChangeLog.objects.filter') as logs:
            with self.assertRaises(Http404):
                self.view._render_change_history(request, self.packing)
            logs.assert_not_called()

    def test_unrecognized_scope_is_not_a_fallback_to_all_logs(self):
        request = SimpleNamespace(GET={'audit_scope': 'all'})
        with patch('order.views.ChangeLog.objects.filter') as logs:
            with self.assertRaises(Http404):
                self.view._render_change_history(request, self.packing)
            logs.assert_not_called()
