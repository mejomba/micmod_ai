"""Tests for permissions and editing existing Quick Packing rows."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase

from order.views import QuickPackingView


class QuickPackingWorkflowRowEditTests(SimpleTestCase):
    def setUp(self):
        self.view = QuickPackingView()
        self.request = SimpleNamespace(user=Mock(is_superuser=False))
        self.packing = Mock()
        self.packing.workflow_state_index.return_value = 2
        self.packing.user_has_workflow_access.return_value = True

        self.row = {
            'id': 123,
            'delete': False,
            'quantity': 5,
            'carton_number': 'Carton B',
            'gross_weight_kg': 4,
            'size': 'M',
            'description': 'Edited',
        }
        self.item = Mock()
        self.item.order_id = 10
        self.item.quantity = 5
        self.item.price = 20
        self.item.carton_number = 'Carton A'
        self.item.gross_weight_kg = 4
        self.item.size = 'M'
        self.item.description = 'Original'
        # A bare Mock().filter().exists() is truthy. No Sepidar transfer
        # exists by default; individual tests can explicitly simulate one.
        self.item.sepidar_transfer_lines.filter.return_value.exists.return_value = False

        self.order = Mock()
        self.order.final_price = 50
        self.order.final_weight = 2
        self.order.validate_for_packing.return_value = (True, '')

    def edit(self, item_exists=True):
        with (
            patch.object(self.view, '_parse_existing_rows', return_value=[self.row]),
            patch('order.views.PackingItem.objects.select_for_update') as item_query,
            patch('order.views.Order.objects.select_for_update') as order_query,
        ):
            item_query.return_value.filter.return_value.first.return_value = (
                self.item if item_exists else None
            )
            order_query.return_value.get.return_value = self.order
            self.view._update_existing_rows(self.request, self.packing)

    def test_assigned_or_supervisor_access_can_edit_later_stage(self):
        self.edit()
        self.item.save.assert_called_once_with()
        self.assertEqual(self.item.carton_number, 'Carton B')
        self.assertEqual(self.item.description, 'Edited')
        # Later-stage edits must not reprice existing PackingItems.
        self.assertEqual(self.item.price, 20)
        self.order.validate_for_packing.assert_not_called()

    def test_change_quantity_later_stage_is_revalidated(self):
        self.row['quantity'] = 6
        self.edit()
        self.order.validate_for_packing.assert_called_once_with(
            6, self.packing, packing_item_obj=self.item,
        )
        self.assertEqual(self.item.net_weight_kg, 12)
        self.assertEqual(self.item.price, 20)

    def test_cannot_edit_without_current_workflow_access(self):
        self.packing.user_has_workflow_access.return_value = False
        with patch.object(self.view, '_parse_existing_rows', return_value=[self.row]):
            with self.assertRaises(PermissionDenied):
                self.view._update_existing_rows(self.request, self.packing)
        self.item.save.assert_not_called()

    def test_deleting_later_stage_row_is_forbidden(self):
        self.row['delete'] = True
        with patch.object(self.view, '_parse_existing_rows', return_value=[self.row]):
            with self.assertRaises(PermissionDenied):
                self.view._update_existing_rows(self.request, self.packing)
        self.item.save.assert_not_called()

    def test_cannot_update_row_from_different_packing(self):
        with self.assertRaisesMessage(ValueError, 'does not belong'):
            self.edit(item_exists=False)
        self.item.save.assert_not_called()

    def test_first_stage_delete_remains_available(self):
        self.packing.workflow_state_index.return_value = 0
        self.row['delete'] = True
        self.edit()
        self.assertTrue(self.item.is_deleted)
        self.item.save.assert_called_once_with()
        self.order.validate_for_packing.assert_not_called()

    def test_sent_or_unresolved_sepidar_transfer_prevents_quantity_edits(self):
        self.packing.workflow_state_index.return_value = 8
        self.row.update(wh_receipt_quantity=4, ruined_quantity=1)
        self.item.wh_receipt_quantity = 3
        self.item.ruined_quantity = 0
        self.item.sepidar_transfer_lines.filter.return_value.exists.return_value = True
        with self.assertRaisesMessage(ValueError, 'A Sepidar transfer exists'):
            self.edit()
        self.item.sepidar_transfer_lines.filter.assert_called_once_with(
            transfer__status__in=('success', 'sending', 'unknown'),
        )
        self.item.save.assert_not_called()

    def test_definitely_failed_transfer_does_not_lock_row(self):
        # The production query excludes 'failed' transfers, allowing fixes
        # before retrying the affected destination group.
        self.packing.workflow_state_index.return_value = 8
        self.row.update(wh_receipt_quantity=4, ruined_quantity=1)
        self.item.wh_receipt_quantity = None
        self.item.ruined_quantity = None
        self.item.sepidar_transfer_lines.filter.return_value.exists.return_value = False
        self.edit()
        self.assertEqual(self.item.wh_receipt_quantity, 4)
        self.assertEqual(self.item.ruined_quantity, 1)
        self.item.save.assert_called_once_with()

    def test_warehouse_only_updates_received_and_ruined_quantities(self):
        self.packing.workflow_state_index.return_value = 8
        self.row['wh_receipt_quantity'] = 4
        self.row['ruined_quantity'] = 1
        self.item.wh_receipt_quantity = None
        self.item.ruined_quantity = None
        self.edit()
        self.assertEqual(self.item.wh_receipt_quantity, 4)
        self.assertEqual(self.item.ruined_quantity, 1)
        self.assertEqual(self.item.quantity, 5)
        self.assertEqual(self.item.price, 20)
        self.assertEqual(self.item.carton_number, 'Carton A')
        self.order.validate_for_packing.assert_not_called()
        self.item.save.assert_called_once_with()

    def test_warehouse_rejects_damaged_above_received(self):
        self.packing.workflow_state_index.return_value = 8
        self.row.update(wh_receipt_quantity=3, ruined_quantity=4)
        with self.assertRaisesMessage(ValueError, 'Received/damaged'):
            self.edit()
        self.item.save.assert_not_called()

    def test_warehouse_rejects_received_above_packing_quantity(self):
        self.packing.workflow_state_index.return_value = 8
        self.row.update(wh_receipt_quantity=6, ruined_quantity=0)
        with self.assertRaisesMessage(ValueError, 'Received/damaged'):
            self.edit()
        self.item.save.assert_not_called()

    def test_warehouse_rejects_row_deletion(self):
        self.packing.workflow_state_index.return_value = 8
        self.row['delete'] = True
        with self.assertRaises(PermissionDenied):
            self.edit()

    def test_warehouse_payload_does_not_need_other_row_fields(self):
        self.packing.workflow_state_index.return_value = 8
        self.row = {'id': 123, 'delete': False, 'wh_receipt_quantity': 5, 'ruined_quantity': 0}
        self.item.wh_receipt_quantity = None
        self.item.ruined_quantity = None
        self.edit()
        self.item.save.assert_called_once_with()

    def test_warehouse_parser_ignores_tampered_quantity_and_price(self):
        post = {
            'existing-123-id': '123',
            'existing-123-wh_receipt_quantity': '5',
            'existing-123-ruined_quantity': '1',
            'existing-123-quantity': '9999',
            'existing-123-price': '0',
        }
        parsed = self.view._parse_existing_rows(
            SimpleNamespace(POST=post), warehouse_stage=True,
        )
        self.assertEqual(parsed, [{
            'id': 123, 'delete': False, 'wh_receipt_quantity': 5.0, 'ruined_quantity': 1.0,
        }])

    def test_superuser_can_edit_normal_and_warehouse_fields_in_warehouse_stage(self):
        self.request.user.is_superuser = True
        self.packing.workflow_state_index.return_value = 8
        self.row.update(wh_receipt_quantity=4, ruined_quantity=1)
        self.item.wh_receipt_quantity = None
        self.item.ruined_quantity = None
        self.edit()
        self.assertEqual(self.item.wh_receipt_quantity, 4)
        self.assertEqual(self.item.ruined_quantity, 1)
        self.assertEqual(self.item.carton_number, 'Carton B')
        self.assertEqual(self.item.quantity, 5)
        self.assertEqual(self.item.price, 20)
        self.item.save.assert_called_once_with()

    def test_superuser_can_edit_receipt_fields_outside_warehouse(self):
        self.request.user.is_superuser = True
        self.row.update(wh_receipt_quantity=5, ruined_quantity=1)
        self.item.wh_receipt_quantity = None
        self.item.ruined_quantity = None
        self.edit()
        self.assertEqual(self.item.wh_receipt_quantity, 5)
        self.assertEqual(self.item.ruined_quantity, 1)

    def test_superuser_only_receipt_change_is_saved(self):
        self.request.user.is_superuser = True
        self.item.carton_number = self.row['carton_number']
        self.item.size = self.row['size']
        self.item.description = self.row['description']
        self.row.update(wh_receipt_quantity=5, ruined_quantity=0)
        self.item.wh_receipt_quantity = None
        self.item.ruined_quantity = None
        self.edit()
        self.item.save.assert_called_once_with()

    def test_superuser_receipt_parser_accepts_normal_and_warehouse_fields(self):
        post = {
            'existing-123-id': '123',
            'existing-123-quantity': '5',
            'existing-123-wh_receipt_quantity': '4',
            'existing-123-ruined_quantity': '1',
        }
        parsed = self.view._parse_existing_rows(
            SimpleNamespace(POST=post), superuser=True,
        )
        self.assertEqual(parsed[0]['quantity'], 5)
        self.assertEqual(parsed[0]['wh_receipt_quantity'], 4)
        self.assertEqual(parsed[0]['ruined_quantity'], 1)

    def test_superuser_cannot_exceed_packing_quantity_on_receipt(self):
        self.request.user.is_superuser = True
        self.row.update(wh_receipt_quantity=6, ruined_quantity=0)
        with self.assertRaisesMessage(ValueError, 'Received/damaged quantities'):
            self.edit()

    def test_unmodified_row_does_not_create_history(self):
        self.row['carton_number'] = self.item.carton_number
        self.row['description'] = self.item.description
        self.edit()
        self.item.save.assert_not_called()

    def test_warehouse_can_save_destination_without_touching_other_fields(self):
        self.packing.workflow_state_index.return_value = 8
        self.row = {
            'id': 123, 'delete': False,
            'wh_receipt_quantity': 4, 'ruined_quantity': 1,
            'wh_destination': '2',
        }
        self.item.wh_receipt_quantity = 4
        self.item.ruined_quantity = 1
        self.item.wh_destination = None
        self.edit()
        self.assertEqual(self.item.wh_destination, '2')
        self.assertEqual(self.item.quantity, 5)
        self.assertEqual(self.item.price, 20)
        self.item.save.assert_called_once_with()

    def test_unknown_warehouse_destination_is_rejected(self):
        post = {
            'existing-123-id': '123',
            'existing-123-wh_receipt_quantity': '4',
            'existing-123-ruined_quantity': '1',
            'existing-123-wh_destination': '999999',
        }
        with self.assertRaisesMessage(ValueError, 'انبار مقصد'):
            self.view._parse_existing_rows(
                SimpleNamespace(POST=post), warehouse_stage=True,
            )

    def test_warehouse_can_save_destination_before_quantities_are_complete(self):
        post = {
            'existing-123-id': '123',
            'existing-123-wh_receipt_quantity': '',
            'existing-123-ruined_quantity': '',
            'existing-123-wh_destination': '2',
        }
        result = self.view._parse_existing_rows(
            SimpleNamespace(POST=post), warehouse_stage=True,
        )
        self.assertEqual(result[0]['wh_destination'], '2')
        self.assertIsNone(result[0]['wh_receipt_quantity'])
        self.assertIsNone(result[0]['ruined_quantity'])

    def test_received_and_damaged_quantities_must_be_completed_together(self):
        with self.assertRaisesMessage(ValueError, 'Received/damaged'):
            self.view._validate_receipt_quantities(3, None, 5)

    def test_bulk_header_destination_can_be_saved_in_warehouse_stage(self):
        self.packing.workflow_state_index.return_value = 8
        self.packing.wh_destination = None
        self.request.POST = {'warehouse_destination': '2'}
        self.view._save_warehouse_destination(self.request, self.packing)
        self.assertEqual(self.packing.wh_destination, '2')
        self.packing.save.assert_called_once_with()

    def test_bulk_header_forgery_ignored_outside_warehouse_stage(self):
        self.packing.workflow_state_index.return_value = 2
        self.request.POST = {'warehouse_destination': '2'}
        self.view._save_warehouse_destination(self.request, self.packing)
        self.packing.save.assert_not_called()



class QuickPackingWarehouseReturnLockTests(SimpleTestCase):
    """Warehouse metadata cannot be lost by returning the workflow backward."""

    def setUp(self):
        self.view = QuickPackingView()
        self.view.request = SimpleNamespace(user=Mock())
        self.packing = Mock(
            wh_destination=None,
            sepidar_wh_to_wh=None,
        )
        self.packing.workflow_state_index.return_value = 8
        self.packing.user_has_workflow_access.return_value = True
        self.view.flow_config = {
            'flow_state_list': [
                'پیش‌نویس', 'تحویل شرکت حمل', 'حمل',
                'قبض انبار', 'تحویل اسناد', 'اظهار',
                'ضمانتنامه', 'ترخیص', 'انبار', 'اتمام کار',
            ],
        }

    def test_header_destination_alone_disables_return(self):
        self.packing.wh_destination = '2'
        self.assertTrue(self.view._has_saved_warehouse_data(self.packing))
        self.packing.packing_item_rel.filter.assert_not_called()

    def test_row_destination_or_received_quantity_disables_return(self):
        rows = self.packing.packing_item_rel.filter.return_value
        rows.filter.return_value.exists.return_value = True
        self.packing.sepidar_transfers.exists.return_value = False
        self.assertTrue(self.view._has_saved_warehouse_data(self.packing))
        self.assertTrue(rows.filter.called)

    def test_sepidar_transfer_disables_return_even_without_quantities(self):
        self.packing.sepidar_transfers.exists.return_value = True
        self.assertTrue(self.view._has_saved_warehouse_data(self.packing))
        self.packing.packing_item_rel.filter.assert_not_called()

    def test_no_warehouse_data_keeps_return_available(self):
        self.packing.sepidar_transfers.exists.return_value = False
        self.packing.packing_item_rel.filter.return_value.filter.return_value.exists.return_value = False
        self.assertFalse(self.view._has_saved_warehouse_data(self.packing))

    def test_back_action_rejected_server_side_even_for_superuser(self):
        self.packing.wh_destination = '2'
        with self.assertRaisesMessage(ValueError, 'امکان عودت'):
            self.view._submit_workflow_action(self.packing, 'back')
