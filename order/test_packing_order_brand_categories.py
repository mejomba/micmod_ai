"""Independent Packing category autocomplete + trade-selected Order brand."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from extra_data.models import Brand
from order.form_perm import ORDER_FIELDS_BY_PERMISSION
from order.forms import OrderSafeForm
from order.models import Order, Packing, PackingItem
from order.packing_inline_labels import (
    normalize_packing_label, packing_label_suggestions,
)
from order.views import SafeOrderView, QuickPackingView


class OrderBrandFormTests(SimpleTestCase):
    def test_order_brand_has_no_default_and_is_nullable_foreign_key(self):
        field = Order._meta.get_field('brand')
        self.assertTrue(field.null)
        self.assertTrue(field.blank)
        self.assertIsNone(Order().brand_id)
        self.assertEqual(field.related_model, Brand)

    def test_only_trade_permission_after_sales_manager_can_edit_brand(self):
        trade = ORDER_FIELDS_BY_PERMISSION['order.cp_order_trade']
        self.assertNotIn('brand', trade[1]['edit'])
        for stage in range(2, 9):
            self.assertIn('brand', trade[stage]['edit'])
        for name in ('order.cp_order_sales', 'order.cp_order_sales_admin',
                     'order.cp_order_mac'):
            for constraint in ORDER_FIELDS_BY_PERMISSION[name].values():
                self.assertNotIn('brand', constraint['edit'])

    def test_combined_permissions_do_not_allow_early_or_nontrade_brand_changes(self):
        view = SafeOrderView()
        perm = SimpleNamespace(
            content_type=SimpleNamespace(app_label='order'),
            codename='cp_order_trade',
        )
        user = Mock(base_group='trade')
        user.user_permissions.all.return_value = [perm]
        view.request = SimpleNamespace(user=user)
        view.state_index = 1
        edit, _, _ = view._get_order_allowed_fields()
        self.assertNotIn('brand', edit)
        view.state_index = 2
        edit, _, _ = view._get_order_allowed_fields()
        self.assertIn('brand', edit)
        user.base_group = 'sales'
        edit, _, _ = view._get_order_allowed_fields()
        self.assertNotIn('brand', edit)

    def test_safe_order_form_exposes_brand_only_when_whitelisted(self):
        form = OrderSafeForm(instance=Order(), allowed_fields=['brand'])
        self.assertIn('brand', form.fields)
        self.assertFalse(form.fields['brand'].required)
        hidden = OrderSafeForm(instance=Order(), allowed_fields=['item'])
        self.assertNotIn('brand', hidden.fields)


class InlinePackingLabelTests(TestCase):
    def setUp(self):
        self.packing = Packing.objects.create(packing_number='PK-INDEP-TEST')

    def test_category_and_main_category_are_independent(self):
        PackingItem.objects.create(
            packing=self.packing, quantity=1, category='Electronics',
            main_category='SMD',
        )
        PackingItem.objects.create(
            packing=self.packing, quantity=2, category='Tools',
            main_category='SMD',
        )
        PackingItem.objects.create(
            packing=self.packing, quantity=3, category=None,
            main_category='Assembly',
        )
        self.assertEqual(
            packing_label_suggestions('main_category', 'SMD'), ['SMD']
        )
        self.assertEqual(
            packing_label_suggestions('main_category', 'Assembly'),
            ['Assembly'],
        )
        self.assertEqual(
            packing_label_suggestions('category', 'Tools'), ['Tools']
        )
        self.assertEqual(packing_label_suggestions('category', 'missing'), [])

    def test_brand_suggestions_from_brand_catalog(self):
        Brand.objects.create(title='Test Brand A')
        self.assertIn('Test Brand A', packing_label_suggestions('brand', 'Brand A'))

    def test_values_are_normalized_independently(self):
        self.assertEqual(normalize_packing_label('category', '  Test   Category  '), 'Test Category')
        self.assertEqual(normalize_packing_label('main_category', '  Component  '), 'Component')
        self.assertIsNone(normalize_packing_label('category', ''))
        with self.assertRaises(ValueError):
            normalize_packing_label('category', 'x' * 151)


class PackingLabelPageContractTests(SimpleTestCase):
    def test_same_quick_packing_page_has_three_row_fields(self):
        template = (Path(settings.BASE_DIR)
                    / 'order/templates/order/packing/quick_packing_create.html').read_text(encoding='utf-8')
        for name in ('category', 'main_category', 'brand'):
            self.assertIn('name="form-${index}-' + name + '"', template)
            self.assertIn('name="existing-{{ packing_item.pk }}-' + name + '"', template)
        self.assertIn('data-packing-autocomplete="category"', template)
        self.assertIn('data-packing-autocomplete="main_category"', template)
        self.assertIn('packing_autocomplete: field', template)
        self.assertNotIn("main_category: category", template)
        self.assertIn("newBrandInput.value = data.brand || ''", template)

    def test_new_and_existing_rows_parse_independent_values(self):
        view = QuickPackingView()
        post = {
            'form-TOTAL_FORMS': '2', 'form-1-order': '17',
            'form-1-quantity': '1',
            'form-1-category': 'Capacitor',
            'form-1-main_category': 'SMD',
            'form-1-brand': 'User Brand',
        }
        row = view._parse_rows(
            SimpleNamespace(user=Mock(is_superuser=False), POST=post),
        )[0]
        self.assertEqual(row['category'], 'Capacitor')
        self.assertEqual(row['main_category'], 'SMD')
        self.assertEqual(row['brand'], 'User Brand')
        existing = view._parse_existing_rows(SimpleNamespace(POST={
            'existing-12-id': '12', 'existing-12-quantity': '1',
            'existing-12-category': 'Tooling',
            'existing-12-main_category': 'SMD',
            'existing-12-brand': 'Packing Override',
        }))[0]
        self.assertEqual(existing['category'], 'Tooling')
        self.assertEqual(existing['main_category'], 'SMD')
        self.assertEqual(existing['brand'], 'Packing Override')

    def test_suggestion_endpoint_uses_no_extra_page_and_checks_access(self):
        view = QuickPackingView()
        view.request = SimpleNamespace(user=Mock())
        query = SimpleNamespace(GET={'packing_autocomplete': 'main_category', 'q': 'SMD'},
                                user=view.request.user)
        with patch.object(view, '_assert_create_access'), patch(
            'order.views.packing_label_suggestions', return_value=['SMD']
        ) as lookup:
            response = view.get(query)
        self.assertEqual(response.status_code, 200)
        self.assertIn('SMD', response.content.decode())
        lookup.assert_called_once_with('main_category', 'SMD')
