from datetime import date
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from order.models import GIO, GIOItem, Order
from order.forms import GIOForm


class GioWeightDatabaseTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(username='gio_weight_admin', password=None)
        self.viewer = get_user_model().objects.create_user(username='gio_weight_viewer', password=None)
        self.gio = GIO.objects.create(gio_date=date(2026, 11, 25))
        self.url = reverse('order:gio.weight', args=[self.gio.pk])

    def test_model_manual_weight_persists_and_zero_is_valid(self):
        GIO.objects.filter(pk=self.gio.pk).update(manual_weight_kg=Decimal('0'))
        self.gio.refresh_from_db()
        self.assertTrue(self.gio.weight_is_overridden)
        self.assertEqual(self.gio.total_weight_kg, Decimal('0'))
        self.assertIsNone(self.gio.calculated_weight_kg)

    def test_missing_order_and_deleted_rows(self):
        row = GIOItem.objects.create(gio=self.gio, quantity=2)
        self.assertEqual(self.gio.get_weight_summary().missing_row_ids, (row.pk,))
        GIOItem.objects.filter(pk=row.pk).update(is_deleted=True)
        self.assertEqual(self.gio.get_weight_summary().row_count, 0)

    def test_manual_override_endpoint_and_reset(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url, {'action': 'manual', 'weight': '15000.001'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Decimal(response.json()['effective']), Decimal('15000.001'))
        GIOItem.objects.create(gio=self.gio, quantity=2)
        self.gio.refresh_from_db()
        self.assertEqual(self.gio.total_weight_kg, Decimal('15000.001'))
        response = self.client.post(self.url, {'action': 'automatic'})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['effective'])
        self.gio.refresh_from_db()
        self.assertIsNone(self.gio.manual_weight_kg)

    def test_invalid_and_forbidden_and_locked(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.post(self.url, {'action': 'manual', 'weight': '1'}).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(self.client.post(self.url, {'action': 'manual', 'weight': '-1'}).status_code, 400)
        GIO.objects.filter(pk=self.gio.pk).update(sepidar_buy_factor_response_json={'registered': True})
        self.assertEqual(self.client.post(self.url, {'action': 'manual', 'weight': '1'}).status_code, 409)
        self.gio.refresh_from_db()
        self.assertIsNone(self.gio.manual_weight_kg)
        self.assertEqual(self.gio.sepidar_buy_factor_response_json, {'registered': True})

    def test_negative_database_constraint_and_legacy_form(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            GIO.objects.filter(pk=self.gio.pk).update(manual_weight_kg=Decimal('-1'))
        self.assertNotIn('manual_weight_kg', GIOForm(instance=self.gio).fields)
