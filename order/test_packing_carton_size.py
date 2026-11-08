"""Size is shared by the outer carton number, never by row index."""
from types import SimpleNamespace

from django.test import SimpleTestCase

from order.packing_carton_size import reconcile_carton_sizes


def stored(pk, carton, size):
    return SimpleNamespace(pk=pk, carton_number=carton, size=size)


class CartonSizeValidationTests(SimpleTestCase):
    def test_new_rows_share_size_by_carton_number(self):
        one = {'carton_number': 'BOX-1', 'size': '40 x 30 x 20'}
        two = {'carton_number': 'box-1', 'size': ''}
        self.assertEqual(reconcile_carton_sizes([], [], [one, two]), [])
        self.assertEqual(two['size'], '40 x 30 x 20')

    def test_new_size_is_filled_from_saved_carton(self):
        fresh = {'carton_number': 'C1', 'size': None}
        self.assertEqual(reconcile_carton_sizes([stored(1, 'C1', '20×30')], [], [fresh]), [])
        self.assertEqual(fresh['size'], '20×30')

    def test_manual_size_conflict_blocks_save(self):
        rows = [
            {'carton_number': 'A', 'size': '40x30'},
            {'carton_number': 'A', 'size': '30x30'},
        ]
        with self.assertRaisesMessage(ValueError, 'سایزهای متفاوت'):
            reconcile_carton_sizes([], [], rows)

    def test_edited_existing_carton_checks_other_saved_rows(self):
        original = [stored(1, 'A', '40x30'), stored(2, 'A', '40x30')]
        with self.assertRaisesMessage(ValueError, 'سایزهای متفاوت'):
            reconcile_carton_sizes(original, [
                {'id': 1, 'carton_number': 'A', 'size': '20x20'}
            ], [])

    def test_missing_size_is_required_for_new_carton(self):
        with self.assertRaisesMessage(ValueError, 'باید یک سایز ثبت شود'):
            reconcile_carton_sizes([], [], [{'carton_number': 'A', 'size': ''}])

    def test_no_conflict_with_equivalent_separator_spellings(self):
        rows = [
            {'carton_number': 'Box 1', 'size': '40 × 30 x 20'},
            {'carton_number': 'BOX 1', 'size': '40x30x20'},
        ]
        self.assertEqual(reconcile_carton_sizes([], [], rows), [])

    def test_deleting_row_excludes_its_old_conflicting_size(self):
        original = [stored(1, 'A', '30x30'), stored(2, 'A', '50x50')]
        row = {'id': 2, 'delete': True}
        added = {'carton_number': 'A', 'size': '30x30'}
        self.assertEqual(reconcile_carton_sizes(original, [row], [added]), [])

    def test_retroactive_missing_size_can_be_saved_with_audit(self):
        original = [stored(1, 'A', None), stored(2, 'A', '40x30')]
        added = {'carton_number': 'A', 'size': None}
        fixes = reconcile_carton_sizes(original, [], [added])
        self.assertEqual(added['size'], '40x30')
        self.assertEqual(fixes, [(original[0], '40x30')])

    def test_unrelated_edit_does_not_block_old_legacy_size_mismatch(self):
        old = [stored(1, 'A', '40x30'), stored(2, 'A', '20x20')]
        row = {'id': 1, 'carton_number': 'A', 'size': '40x30',
               'category': 'New'}
        self.assertEqual(reconcile_carton_sizes(old, [row], []), [])

    def test_warehouse_editing_does_not_run_carton_size_updates(self):
        from unittest.mock import Mock, patch
        from order.views import QuickPackingView
        view = QuickPackingView()
        request = SimpleNamespace(
            user=SimpleNamespace(is_superuser=False),
            POST={'existing-17-id': '17',
                  'existing-17-wh_receipt_quantity': '1',
                  'existing-17-ruined_quantity': '0'},
        )
        with patch.object(view, '_is_warehouse_stage', return_value=True), \
             patch('order.views.PackingItem.objects.select_for_update') as db:
            result = view._prepare_carton_sizes(request, Mock(), [])
        self.assertNotIn('size', result[0])
        db.assert_not_called()

    def test_prepare_persists_backfilled_size_with_request_actor(self):
        from unittest.mock import Mock, patch
        from order.views import QuickPackingView
        view = QuickPackingView()
        user = Mock(is_superuser=False)
        request = SimpleNamespace(user=user, POST={})
        packing = Mock()
        missing = Mock(pk=1, carton_number='BOX', size=None)
        missing.extra_data = Mock()
        existing = [missing, stored(2, 'BOX', '40x30')]
        # Unsaved new row joins an existing carton but omitted its size.
        new = [{'carton_number': 'BOX', 'size': ''}]
        with patch.object(view, '_is_warehouse_stage', return_value=False), \
             patch.object(view, '_parse_existing_rows', return_value=[]), \
             patch('order.views.PackingItem.objects.select_for_update') as lock:
            lock.return_value.filter.return_value.only.return_value = existing
            result = view._prepare_carton_sizes(request, packing, new)
        self.assertEqual(result, [])
        self.assertEqual(new[0]['size'], '40x30')
        self.assertEqual(existing[0].size, '40x30')
        missing.save.assert_called_once_with()
        self.assertIs(missing.editor_user, user)
        self.assertIs(missing.extra_data.request, request)
