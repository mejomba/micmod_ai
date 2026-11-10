"""Regression tests for Packing assignee continuity and scoped changer access."""
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import QueryDict
from django.test import SimpleTestCase

from order.models import Packing
from order.views import QuickPackingView


class PackingWorkflowAssigneeSelectionTests(SimpleTestCase):
    def setUp(self):
        self.view = QuickPackingView()
        self.view.flow_config = {
            'flow_state_list': ['Current stage', 'Next stage'],
            'flow_users_groups': ['packing_current', 'packing_next'],
        }

    def test_current_assignee_is_reused_when_member_of_destination_group(self):
        current_assignee = Mock(is_active=True)
        current_assignee.groups.filter.return_value.exists.return_value = True
        historical_destination_assignee = Mock()
        packing = Mock()
        packing.workflow_state_index.return_value = 0
        packing.workflow_assigned_user.side_effect = (
            lambda group, fallback_first=True:
                current_assignee if group == 'packing_current'
                else historical_destination_assignee
        )

        selected = self.view._pick_flow_user(packing, 'packing_next')

        self.assertIs(selected, current_assignee)
        self.assertEqual(
            packing.workflow_assigned_user.call_args_list,
            [
                (('packing_current',), {'fallback_first': False}),
            ],
        )

    def test_historical_destination_assignee_is_fallback_when_current_owner_is_not_eligible(self):
        current_assignee = Mock(is_active=True)
        current_assignee.groups.filter.return_value.exists.return_value = False
        historical_destination_assignee = Mock()
        packing = Mock()
        packing.workflow_state_index.return_value = 0
        packing.workflow_assigned_user.side_effect = (
            lambda group, fallback_first=True:
                current_assignee if group == 'packing_current'
                else historical_destination_assignee
        )

        selected = self.view._pick_flow_user(packing, 'packing_next')

        self.assertIs(selected, historical_destination_assignee)
        self.assertEqual(
            packing.workflow_assigned_user.call_args_list,
            [
                (('packing_current',), {'fallback_first': False}),
                (('packing_next',), {'fallback_first': True}),
            ],
        )

    def test_inactive_current_assignee_is_not_reused(self):
        current_assignee = Mock(is_active=False)
        historical_destination_assignee = Mock()
        packing = Mock()
        packing.workflow_state_index.return_value = 0
        packing.workflow_assigned_user.side_effect = (
            lambda group, fallback_first=True:
                current_assignee if group == 'packing_current'
                else historical_destination_assignee
        )

        selected = self.view._pick_flow_user(packing, 'packing_next')

        self.assertIs(selected, historical_destination_assignee)


class PackingWorkflowAssigneeChangerTests(SimpleTestCase):
    @staticmethod
    def user_with_groups(*group_names):
        user = Mock(is_authenticated=True, is_superuser=False)
        user.groups.filter.side_effect = lambda **kwargs: SimpleNamespace(
            exists=lambda: kwargs.get('name') in group_names,
        )
        return user

    def test_changer_group_name_is_model_scoped(self):
        self.assertEqual(Packing.workflow_user_changer_group(), 'packing_user_changer')

    def test_changer_group_grants_only_assignee_change_permission(self):
        user = self.user_with_groups('packing_user_changer')
        self.assertTrue(Packing.user_can_change_workflow_user(user))

        packing = Packing()
        with patch.object(packing, 'user_has_workflow_access', return_value=False):
            self.assertFalse(packing.user_can_view_workflow(user))

        self.assertFalse(Packing.user_can_change_workflow_user(
            self.user_with_groups('order_user_changer'),
        ))

    def test_changer_only_user_can_open_minimal_assignee_page(self):
        view = QuickPackingView()
        view.flow_config = {
            'flow_state_list': ['Draft', 'Shipping'],
            'flow_users_groups': ['packing_user_p', 'packing_user_dep'],
        }
        user = self.user_with_groups('packing_user_changer')
        packing = Mock(pk=42)
        packing.user_can_view_workflow.return_value = False
        packing.workflow_state_index.return_value = 1
        packing.workflow_assigned_user.return_value = Mock(username='assignee')
        view.get_object = Mock(return_value=packing)

        users = Mock()
        users.objects.filter.return_value.distinct.return_value.order_by.return_value = ['allowed-user']
        request = SimpleNamespace(user=user, GET={})
        with (
            patch('order.views.get_user_model', return_value=users),
            patch('order.views.render', return_value='minimal-page') as render,
        ):
            response = view.get(request, pk=42)

        self.assertEqual(response, 'minimal-page')
        self.assertEqual(
            render.call_args.args[1],
            'order/packing/quick_packing_change_user.html',
        )
        context = render.call_args.args[2]
        self.assertEqual(context['current_state'], 'Shipping')
        self.assertNotIn('packings', context)
        self.assertNotIn('form', context)
        self.assertNotIn('workflow_history', context)

    def test_changer_only_user_can_change_assignee_without_document_form_save(self):
        view = QuickPackingView()
        user = self.user_with_groups('packing_user_changer')
        packing = Mock(pk=42)
        packing.user_has_workflow_access.return_value = False
        view.get_object = Mock(return_value=packing)
        view._build_form = Mock()
        view._change_workflow_user = Mock()
        request = SimpleNamespace(
            user=user,
            POST=QueryDict('workflow_action=change_user&workflow_user_id=17'),
            FILES={},
        )
        locked = Mock()
        with (
            patch('order.views.Packing.objects.select_for_update') as select_for_update,
            patch('order.views.transaction.atomic', return_value=nullcontext()),
        ):
            select_for_update.return_value.get.return_value = locked
            response = view.post(request, pk=42)

        self.assertEqual(response.status_code, 200)
        view._change_workflow_user.assert_called_once_with(
            locked, '17', request=request,
        )
        view._build_form.assert_not_called()

    def test_changer_only_user_cannot_advance_workflow(self):
        view = QuickPackingView()
        user = self.user_with_groups('packing_user_changer')
        packing = Mock(pk=42)
        packing.user_has_workflow_access.return_value = False
        view.get_object = Mock(return_value=packing)
        request = SimpleNamespace(
            user=user,
            POST=QueryDict('workflow_action=next'),
            FILES={},
        )
        with self.assertRaises(PermissionDenied):
            view.post(request, pk=42)

    def test_migration_creates_model_scoped_group(self):
        migration = (
            Path(settings.BASE_DIR)
            / 'order/migrations/0139_packing_user_changer_group.py'
        ).read_text(encoding='utf-8')
        self.assertIn("USER_CHANGER_GROUP = 'packing_user_changer'", migration)
        self.assertIn("'0138_packingitem_volume_is_confirmed'", migration)
        self.assertIn("get_or_create(", migration)
