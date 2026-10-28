"""Permission matrix for Quick Packing, audit AJAX, and the viewer group."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase

from order.models import Packing
from order.views import QuickPackingView, PackingView


class QuickPackingDocumentAccessTests(SimpleTestCase):
    def setUp(self):
        self.view = QuickPackingView()
        self.packing = Mock()
        self.packing.user_can_view_workflow.return_value = False
        self.view.get_object = Mock(return_value=self.packing)
        self.user = Mock(is_authenticated=True, is_superuser=False)
        self.request = SimpleNamespace(
            user=self.user, GET={},
        )

    def test_unauthorized_user_cannot_open_document(self):
        with self.assertRaises(PermissionDenied):
            self.view.get(self.request, pk=42)
        self.packing.user_can_view_workflow.assert_called_once_with(self.user)

    def test_unauthorized_user_cannot_fetch_audit_history(self):
        self.request.GET = {'audit_scope': 'header'}
        with patch.object(self.view, '_render_change_history') as audit:
            with self.assertRaises(PermissionDenied):
                self.view.get(self.request, pk=42)
            audit.assert_not_called()

    def test_unauthorized_user_cannot_fetch_row_audit_history(self):
        self.request.GET = {'audit_scope': 'item', 'audit_item_id': '7'}
        with patch.object(self.view, '_render_change_history') as audit:
            with self.assertRaises(PermissionDenied):
                self.view.get(self.request, pk=42)
            audit.assert_not_called()

    def test_viewer_group_has_only_read_access(self):
        packing = Packing()
        user = Mock(is_authenticated=True, is_superuser=False)
        user.groups.filter.return_value.exists.return_value = True
        with patch.object(packing, 'user_has_workflow_access', return_value=False) as edit:
            self.assertTrue(packing.user_can_view_workflow(user))
            self.assertFalse(packing.user_has_workflow_access(user))
            edit.assert_called()
        user.groups.filter.assert_called_with(name='packing_viewer')

    def test_random_logged_in_user_has_no_document_read_access(self):
        packing = Packing()
        user = Mock(is_authenticated=True, is_superuser=False)
        user.groups.filter.return_value.exists.return_value = False
        with patch.object(packing, 'user_has_workflow_access', return_value=False):
            self.assertFalse(packing.user_can_view_workflow(user))

    def test_anonymous_user_cannot_use_viewer_membership(self):
        packing = Packing()
        user = Mock(is_authenticated=False, is_superuser=False)
        self.assertFalse(packing.user_has_view_only_access(user))

    def test_viewer_form_cannot_post_any_header_or_file_field(self):
        self.view.request = self.request
        self.view._workflow_constraint = Mock(return_value={
            'form_state': 2,
            'wf_access': False,
            'form_constraint': [{'read': []} for _ in range(10)],
        })
        self.view._is_warehouse_stage = Mock(return_value=False)
        with patch.object(self.view, 'form_class') as form_class:
            self.view._build_form(
                packing_obj=Mock(),
                data={
                    'bl_number': 'ATTACK',
                    'file_1': 'ATTACK',
                },
            )
        kwargs = form_class.call_args.kwargs
        self.assertEqual(kwargs['allowed_fields'], [])
        self.assertEqual(
            kwargs['only_show'],
            ['file_' + str(idx) for idx in range(1, 12)],
        )

    def test_legacy_packing_route_denies_unauthorized_document(self):
        view = PackingView()
        request = Mock(user=self.user, method='GET')
        packing = Mock()
        packing.user_can_view_workflow.return_value = False
        with patch('order.views.get_object_or_404', return_value=packing):
            with self.assertRaises(PermissionDenied):
                view.dispatch(request, pk=42)

    def test_legacy_route_redirects_read_only_viewer_to_safe_page(self):
        view = PackingView()
        request = Mock(user=self.user, method='GET')
        packing = Mock(pk=42)
        packing.user_can_view_workflow.return_value = True
        packing.user_has_workflow_access.return_value = False
        with patch('order.views.get_object_or_404', return_value=packing):
            response = view.dispatch(request, pk=42)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/quick_packing/42/', response['Location'])

    def test_assigned_user_outside_current_group_cannot_edit(self):
        from workflow.models import WorkFlow, FlowAdminGroup
        from django.contrib.contenttypes.models import ContentType

        packing = Packing()
        user = Mock(id=25, is_authenticated=True, is_superuser=False)
        user.groups.filter.return_value.exists.return_value = False
        flow = Mock(to_user_id=25)
        with (
            patch.object(packing, 'workflow_state_index', return_value=2),
            patch.object(Packing, 'get_flow_config', return_value={
                'flow_users_groups': ['packing_user_p', 'packing_user_dep', 'packing_user_ship'],
            }),
            patch.object(FlowAdminGroup, 'is_admin_of_group', return_value=False),
            patch.object(ContentType.objects, 'get_for_model', return_value=Mock()),
            patch.object(WorkFlow.objects, 'filter') as query,
        ):
            query.return_value.order_by.return_value.last.return_value = flow
            self.assertFalse(packing.user_has_workflow_access(user))
            user.groups.filter.return_value.exists.return_value = True
            self.assertTrue(packing.user_has_workflow_access(user))

    def test_viewer_post_is_denied_even_with_forged_form_data(self):
        self.request.POST = {'bl_number': 'FORGED', 'workflow_action': 'next'}
        self.packing.user_has_workflow_access.return_value = False
        with self.assertRaises(PermissionDenied):
            self.view.post(self.request, pk=42)

    def test_readonly_template_uses_model_values_not_missing_form_fields(self):
        html = (
            Path(settings.BASE_DIR)
            / 'order/templates/order/packing/quick_packing_create.html'
        ).read_text(encoding='utf-8')
        self.assertIn(
            '{% if is_read_only_view or is_warehouse_stage and not is_superuser %}',
            html,
        )
        self.assertIn('packing_object.packing_number|default:', html)
        self.assertIn('packing_object.bl_number|default:', html)
        self.assertIn('packing_object.estimated_shipping_start_date|date:', html)
        self.assertIn('packing_object.description|default:', html)
        self.assertIn('if is_read_only_view and not is_warehouse_stage', html)

    def test_viewer_group_created_by_data_migration(self):
        migration = (
            Path(settings.BASE_DIR)
            / 'order/migrations/0130_packing_viewer_group.py'
        ).read_text(encoding='utf-8')
        self.assertIn("VIEW_ONLY_GROUP = 'packing_viewer'", migration)
        self.assertIn("get_or_create(", migration)
        self.assertIn("'0129_packing_workflow_nine_stages'", migration)

