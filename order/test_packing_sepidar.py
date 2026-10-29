"""Pure plan/response tests (no external Sepidar calls)."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from order.packing_sepidar import PackingTransferError, _parse_result, plan_packing_transfers, transfer_snapshot


class _Rows:
    def __init__(self, values):
        self.values = values

    def filter(self, **kwargs):
        return self

    def select_related(self, *args):
        return self

    def order_by(self, *args):
        return self

    def __iter__(self):
        return iter(self.values)


@override_settings(SEPIDAR_CONST_DATA={'before_central_wh_id': 91})
class PackingSepidarPlanTests(SimpleTestCase):
    def row(self, pk, destination, received, damaged):
        return SimpleNamespace(
            pk=pk, wh_destination=destination,
            wh_receipt_quantity=received, ruined_quantity=damaged, quantity=received,
            order=SimpleNamespace(item=SimpleNamespace(sepidar_id_0=100 + pk)),
        )

    def packing(self, *rows):
        return SimpleNamespace(packing_item_rel=_Rows(rows))

    def test_groups_healthy_and_damaged_in_separate_destinations(self):
        with patch('order.packing_sepidar.Order.sepidar_wh_map', {2: 'central', 42: 'damaged', 73: 'resalat'}):
            groups = plan_packing_transfers(self.packing(
                self.row(1, '2', 100, 5),
                self.row(2, '73', 40, 10),
            ))
        self.assertEqual(
            {(g['transfer_type'], g['destination_stock_ref']): sum(x['quantity'] for x in g['lines'])
             for g in groups},
            {('normal', 2): 95, ('normal', 73): 30, ('damaged', 42): 15},
        )

    def test_missing_destination_blocks_entire_plan(self):
        with self.assertRaises(PackingTransferError):
            plan_packing_transfers(self.packing(self.row(1, '', 10, 0)))

    def test_received_cannot_exceed_packing_quantity(self):
        row = self.row(1, '2', 10, 0)
        row.quantity = 8
        with self.assertRaises(PackingTransferError):
            plan_packing_transfers(self.packing(row))

    def test_error_result_is_definitively_failed(self):
        self.assertEqual(_parse_result({'errors': 'validation exception'})[0], 'failed')

    def test_valid_response_stores_both_documents(self):
        status, data, error = _parse_result({'packing': {'sepidar': [{
            'wh_delivery': {'id': 12, 'number': 34},
            'wh_receipt': {'id': 56, 'number': 78},
        }]}})
        self.assertEqual(status, 'success')
        self.assertEqual(data['receipt_id'], 56)
        self.assertEqual(error, '')

    def test_float_quantities_have_stable_document_snapshot(self):
        self.assertEqual(
            transfer_snapshot([{'packing_item_id': 1, 'itemref': 105, 'quantity': Decimal('95.0')}]),
            [(1, 105, '95')],
        )

    def test_uncertain_remote_failure_is_not_retry_safe(self):
        self.assertEqual(_parse_result({'errors': 'HTTP 500', 'uncertain': True})[0], 'unknown')

    def test_incomplete_response_is_uncertain(self):
        self.assertEqual(_parse_result({'packing': {'sepidar': []}})[0], 'unknown')
