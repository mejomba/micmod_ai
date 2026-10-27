"""Tests for permissions and editing existing Quick Packing rows."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase

from order.views import QuickPackingView


class QuickPackingWorkflowRowEditTests(SimpleTestCase):
    def setUp(self):
        self.view = QuickPackingView()
        self.request = SimpleNamespace(user=Mock())
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

    def test_warehouse_only_updates_received_and_ruined_quantities(self):
        self.packing.workflow_state_index.return_value = 8
        self.row['arrived_quantity'] = 4
        self.row['ruined_quantity'] = 1
        self.item.arrived_quantity = None
        self.item.ruined_quantity = None
        self.edit()
        self.assertEqual(self.item.arrived_quantity, 4)
        self.assertEqual(self.item.ruined_quantity, 1)
        self.assertEqual(self.item.quantity, 5)
        self.assertEqual(self.item.price, 20)
        self.assertEqual(self.item.carton_number, 'Carton A')
        self.order.validate_for_packing.assert_not_called()
        self.item.save.assert_called_once_with()

    def test_warehouse_rejects_damaged_above_received(self):
        self.packing.workflow_state_index.return_value = 8
        self.row.update(arrived_quantity=3, ruined_quantity=4)
        with self.assertRaisesMessage(ValueError, 'Received/damaged'):
            self.edit()
        self.item.save.assert_not_called()

    def test_warehouse_rejects_received_above_packing_quantity(self):
        self.packing.workflow_state_index.return_value = 8
        self.row.update(arrived_quantity=6, ruined_quantity=0)
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
        self.row = {'id': 123, 'delete': False, 'arrived_quantity': 5, 'ruined_quantity': 0}
        self.item.arrived_quantity = None
        self.item.ruined_quantity = None
        self.edit()
        self.item.save.assert_called_once_with()

    def test_warehouse_parser_ignores_tampered_quantity_and_price(self):
        post = {
            'existing-123-id': '123',
            'existing-123-arrived_quantity': '5',
            'existing-123-ruined_quantity': '1',
            'existing-123-quantity': '9999',
            'existing-123-price': '0',
        }
        parsed = self.view._parse_existing_rows(
            SimpleNamespace(POST=post), warehouse_stage=True,
        )
        self.assertEqual(parsed, [{
            'id': 123, 'delete': False, 'arrived_quantity': 5.0, 'ruined_quantity': 1.0,
        }])

    def test_unmodified_row_does_not_create_history(self):
        self.row['carton_number'] = self.item.carton_number
        self.row['description'] = self.item.description
        self.edit()
        self.item.save.assert_not_called()
