"""Post-draft Packing registration and per-item carton count regression tests."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from order.forms import PackingSafeForm
from order.models import Packing
from order.views import QuickPackingView


class PackingRegistrationAndCartonsTests(SimpleTestCase):
    def test_registration_number_is_exactly_eight_ascii_digits(self):
        field = Packing._meta.get_field('order_registration_number')
        self.assertEqual(field.max_length, 8)
        field.run_validators('00001234')
        for invalid in ('1234567', '123456789', '12A45678', '۱۲۳۴۵۶۷۸'):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                field.run_validators(invalid)

    def test_exactly_six_commercial_cards_are_available(self):
        self.assertEqual(
            [label for _, label in Packing.COMMERCIAL_CARD_CHOICES],
            [
                'رهاورد تجارت آینده', 'رسول رفیع', 'مدرن الکترونیک',
                'فراز فن آوران فاران', 'هایکار', 'هایبار',
            ],
        )
        self.assertEqual(len({value for value, _ in Packing.COMMERCIAL_CARD_CHOICES}), 6)

    def test_draft_and_unsaved_form_never_accept_registration_fields(self):
        for packing in (Packing(), Packing(pk=11)):
            with patch.object(Packing, 'workflow_state_index', return_value=0):
                form = PackingSafeForm(
                    instance=packing, allowed_fields=list(Packing.POST_DRAFT_FIELDS),
                )
            for name in Packing.POST_DRAFT_FIELDS:
                self.assertNotIn(name, form.fields)

    def test_saved_postdraft_form_has_registration_fields(self):
        with patch.object(Packing, 'workflow_state_index', return_value=2):
            form = PackingSafeForm(
                instance=Packing(pk=11),
                allowed_fields=list(Packing.POST_DRAFT_FIELDS),
            )
        self.assertTrue(set(Packing.POST_DRAFT_FIELDS).issubset(form.fields))
        self.assertEqual(
            form.fields['order_registration_number'].widget.attrs['pattern'],
            '[0-9]{8}',
        )

    def test_quick_view_shows_registration_inputs_to_warehouse_editor(self):
        view = QuickPackingView()
        view.request = SimpleNamespace(user=Mock(is_superuser=False))
        view._workflow_constraint = Mock(return_value={
            'form_state': 8, 'wf_access': True,
            'form_constraint': [{'read': []} for _ in range(10)],
        })
        view._is_warehouse_stage = Mock(return_value=True)
        with patch.object(view, 'form_class') as form_class:
            view._build_form(packing_obj=Mock(), data=None)
        kwargs = form_class.call_args.kwargs
        for name in Packing.POST_DRAFT_FIELDS:
            self.assertIn(name, kwargs['allowed_fields'])
        self.assertNotIn('packing_number', kwargs['allowed_fields'])

    def test_quick_view_hides_registration_from_draft_or_viewer(self):
        view = QuickPackingView()
        view.request = SimpleNamespace(user=Mock(is_superuser=False))
        view._is_warehouse_stage = Mock(return_value=False)
        view._workflow_constraint = Mock(return_value={
            'form_state': 0, 'wf_access': True,
            'form_constraint': [{'read': []} for _ in range(10)],
        })
        with patch.object(view, 'form_class') as form_class:
            view._build_form(packing_obj=Mock(), data={})
        self.assertTrue(
            set(Packing.POST_DRAFT_FIELDS).isdisjoint(
                form_class.call_args.kwargs['allowed_fields'],
            ),
        )

        view._workflow_constraint.return_value['form_state'] = 2
        view._workflow_constraint.return_value['wf_access'] = False
        with patch.object(view, 'form_class') as form_class:
            view._build_form(packing_obj=Mock(), data={})
        self.assertTrue(
            set(Packing.POST_DRAFT_FIELDS).isdisjoint(
                form_class.call_args.kwargs['allowed_fields'],
            ),
        )

    def test_partial_posts_preserve_optional_registration_data(self):
        view = QuickPackingView()
        view.request = SimpleNamespace(user=Mock(is_superuser=False))
        view._is_warehouse_stage = Mock(return_value=False)
        view._workflow_constraint = Mock(return_value={
            'form_state': 3, 'wf_access': True,
            'form_constraint': [{'read': []} for _ in range(10)],
        })
        with patch.object(view, 'form_class') as form_class:
            view._build_form(
                packing_obj=Mock(), data={'proforma_pi_number': 'PI-123'},
            )
        fields = set(form_class.call_args.kwargs['allowed_fields'])
        self.assertIn('proforma_pi_number', fields)
        self.assertNotIn('order_registration_number', fields)
        self.assertNotIn('commercial_card', fields)

    def test_new_item_carton_count_is_parsed_as_optional_integer(self):
        view = QuickPackingView()
        request = SimpleNamespace(user=Mock(is_superuser=False), POST={
            'form-TOTAL_FORMS': '2',
            'form-1-order': '17',
            'form-1-quantity': '5',
            'form-1-carton_number': 'C-01',
            'form-1-carton_quantity': '4',
        })
        rows = view._parse_rows(request)
        self.assertEqual(rows[0]['carton_quantity'], 4)
        self.assertEqual(rows[0]['carton_number'], 'C-01')
        request.POST['form-1-carton_quantity'] = ''
        self.assertIsNone(view._parse_rows(request)[0]['carton_quantity'])

    def test_existing_row_count_can_change_without_requiring_other_changes(self):
        view = QuickPackingView()
        request = SimpleNamespace(POST={
            'existing-123-id': '123',
            'existing-123-quantity': '5',
            'existing-123-carton_quantity': '2',
        })
        rows = view._parse_existing_rows(request)
        self.assertEqual(rows[0]['carton_quantity'], 2)
        del request.POST['existing-123-carton_quantity']
        rows = view._parse_existing_rows(request)
        self.assertNotIn('carton_quantity', rows[0])

    def test_invalid_carton_quantities_are_rejected(self):
        view = QuickPackingView()
        for value in ('-1', '1.5', 'abc', '۲', '2147483648'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                view._parse_carton_quantity(value)
        self.assertEqual(view._parse_carton_quantity('0'), 0)
        self.assertIsNone(view._parse_carton_quantity(None))

    def test_total_uses_saved_counts_not_row_count_and_ignores_deleted(self):
        packing = Mock()
        packing.packing_item_rel.filter.return_value.aggregate.return_value = {
            'total': 18,
        }
        self.assertEqual(Packing.computed_carton_qty.fget(packing), 18)
        packing.packing_item_rel.filter.assert_called_once_with(is_deleted=False)
        kwargs = packing.packing_item_rel.filter.return_value.aggregate.call_args.kwargs
        self.assertIn('carton_quantity', str(kwargs['total']))
        packing.packing_item_rel.filter.return_value.aggregate.return_value = {
            'total': None,
        }
        self.assertIsNone(Packing.computed_carton_qty.fget(packing))

    def test_template_has_editable_count_fields_and_live_summary(self):
        html = (
            Path(settings.BASE_DIR)
            / 'order/templates/order/packing/quick_packing_create.html'
        ).read_text(encoding='utf-8')
        self.assertIn('pk-post-draft-registration', html)
        self.assertIn('packing_object and state_index > 0', html)
        self.assertIn('form.order_registration_number', html)
        self.assertIn('form.proforma_pi_number', html)
        self.assertIn('form.commercial_card', html)
        self.assertIn('name="existing-{{ packing_item.pk }}-carton_quantity"', html)
        self.assertIn('name="form-${index}-carton_quantity"', html)
        self.assertIn('id="packing-total-cartons"', html)
        self.assertIn("event.target.matches('input[name$=\"-carton_quantity\"]')", html)

    def test_migration_creates_only_four_nullable_fields(self):
        migration = (
            Path(settings.BASE_DIR)
            / 'order/migrations/0134_packing_registration_and_carton_quantity.py'
        ).read_text(encoding='utf-8')
        self.assertIn("('order', '0133_packing_sepidar_transfers')", migration)
        for field in (*Packing.POST_DRAFT_FIELDS, 'carton_quantity'):
            self.assertIn(f"name='{field}'", migration)
        self.assertEqual(migration.count('migrations.AddField('), 4)
