"""Regression checks for removal of stale Packing merge artifacts."""
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import resolve, reverse

from order.forms import PackingSafeForm
from order.models import Packing
from order.views import PackingView, QuickPackingView


class PackingMergeCleanupTests(SimpleTestCase):
    def test_legacy_fields_are_not_in_the_model(self):
        names = {field.name for field in Packing._meta.get_fields()}
        self.assertFalse({'source', 'transporter_company'} & names)
        self.assertTrue({'origin', 'destination', 'transportation_company'} <= names)
        self.assertEqual(
            sum(field.name == 'destination' for field in Packing._meta.fields), 1,
        )

    def test_old_workflow_method_is_not_reintroduced(self):
        self.assertNotIn('submit_flow', Packing.__dict__)
        self.assertTrue(callable(Packing.workflow_state_index))

    def test_packing_form_whitelist_uses_canonical_fields(self):
        fields = set(PackingSafeForm.field_layout)
        self.assertTrue({'origin', 'destination', 'transportation_company'} <= fields)
        self.assertFalse({'source', 'transporter_company'} & fields)

    def test_both_registered_packing_routes_are_retained(self):
        self.assertIs(resolve(reverse('order:packing.view')).func.view_class, PackingView)
        self.assertIs(resolve(reverse('order:quick_packing')).func.view_class, QuickPackingView)

    def test_inactive_template_does_not_reference_old_fields(self):
        path = (Path(settings.BASE_DIR) / 'order' / 'templates' / 'order'
                / 'packing' / 'quick_packing_update.html')
        template = path.read_text(encoding='utf-8')
        self.assertNotIn('form.source', template)
        self.assertNotIn('form.transporter_company', template)
        self.assertIn('form.origin', template)
        self.assertIn('form.transportation_company', template)
