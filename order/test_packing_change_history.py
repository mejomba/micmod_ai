"""Regression tests for the existing ChangeLog integration in Quick Packing."""
from datetime import datetime, timezone
from types import SimpleNamespace

from django.test import SimpleTestCase

from order.packing_change_history import build_packing_change_history
from order.models import Packing, PackingItem


def audit_log(action, fields, item=False, pk=5, actor='editor'):
    return SimpleNamespace(
        pk=99,
        created_date=datetime(2026, 10, 27, 9, 0, tzinfo=timezone.utc),
        action=action,
        object_id=pk,
        content_type=SimpleNamespace(model='packingitem' if item else 'packing'),
        diff_json={'fields': fields},
        editor_user=actor,
        creator_user='creator',
    )


class PackingChangeHistoryTests(SimpleTestCase):
    def present(self, *logs):
        return build_packing_change_history(
            logs, Packing, PackingItem,
            [{'id': 5, 'order_id': 42, 'order__order_number': 'ORD-42',
              'part_number': 'ITEM-X'}],
        )

    def test_update_uses_legacy_new_then_old_diff_order(self):
        history = self.present(audit_log(2, {
            'bl_number': ['NEW', 'OLD'],
            'editor_user_id': [11, 7],
        }))
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['action'], 'update')
        self.assertEqual(history[0]['target'], 'سربرگ پکینگ')
        self.assertIsNone(history[0]['item_id'])
        self.assertEqual(history[0]['actor'], 'editor')
        self.assertEqual(history[0]['changes'][0]['new'], 'NEW')
        self.assertEqual(history[0]['changes'][0]['old'], 'OLD')
        self.assertEqual(len(history[0]['changes']), 1)

    def test_created_item_shows_order_identifier_and_new_values(self):
        history = self.present(audit_log(1, {
            'quantity': [12, 12],
            'carton_number': ['C-8', 'C-8'],
        }, item=True))
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['action'], 'create')
        self.assertEqual(history[0]['scope'], 'item')
        self.assertEqual(history[0]['item_id'], 5)
        self.assertIn('ORD-42', history[0]['target'])
        self.assertIn('ITEM-X', history[0]['target'])
        self.assertEqual(history[0]['changes'][0]['new'], '12')

    def test_soft_deleted_item_is_shown_as_delete(self):
        history = self.present(audit_log(2, {
            'is_deleted': [True, False],
        }, item=True))
        self.assertEqual(history[0]['action'], 'delete')
        self.assertEqual(history[0]['changes'][0]['new'], 'بله')
        self.assertEqual(history[0]['changes'][0]['old'], 'خیر')

    def test_empty_audit_field_updates_are_not_shown(self):
        self.assertEqual(self.present(audit_log(2, {
            'editor_user_id': [9, 8],
            'bl_number': ['same', 'same'],
        })), [])

    def test_missing_values_are_friendly(self):
        history = self.present(audit_log(2, {'description': [None, 'Some note']}))
        self.assertEqual(history[0]['changes'][0]['new'], '—')
        self.assertEqual(history[0]['changes'][0]['old'], 'Some note')

    def test_unknown_deleted_item_keeps_record_identity(self):
        history = build_packing_change_history(
            [audit_log(2, {'size': ['new', 'old']}, item=True, pk=999)],
            Packing, PackingItem, [],
        )
        self.assertEqual(history[0]['target'], 'ردیف 999')

    def test_model_base_includes_automatic_change_log(self):
        self.assertTrue(hasattr(Packing, 'change_logs'))
        self.assertTrue(hasattr(PackingItem, 'change_logs'))
    def test_non_finance_history_strips_price_and_total_amount(self):
        history = build_packing_change_history(
            [audit_log(2, {
                'price': [120.5, 100.5],
                'total_amount': [602.5, 502.5],
                'quantity': [5, 4],
            }, item=True)],
            Packing, PackingItem, [],
            include_financial=False,
        )
        self.assertEqual([x['key'] for x in history[0]['changes']], ['quantity'])
        self.assertNotIn('120.5', str(history))
        self.assertNotIn('602.5', str(history))

    def test_finance_history_preserves_prices(self):
        history = build_packing_change_history(
            [audit_log(2, {'price': [120.5, 100.5]}, item=True)],
            Packing, PackingItem, [],
            include_financial=True,
        )
        self.assertEqual(history[0]['changes'][0]['new'], '120.5')

    def test_price_only_update_invisible_to_ordinary_user(self):
        history = build_packing_change_history(
            [audit_log(2, {'price': [8, 7]}, item=True)],
            Packing, PackingItem, [], include_financial=False,
        )
        self.assertEqual(history, [])
