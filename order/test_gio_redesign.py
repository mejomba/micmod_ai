"""Layout, preview, and mock-details regression checks for Quick GIO."""
import json
from collections import OrderedDict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.template.loader import get_template, render_to_string
from django.test import RequestFactory, SimpleTestCase

from order.gio_sepidar import gio_preview_groups
from order.views import OrderAndSepidar, QuickGIODataTableListView


def fake_order(order_id, supplier_ref, currency_ref, part_number):
    supplier = SimpleNamespace(dlref=supplier_ref)
    currency = SimpleNamespace(title_en='Dollar' if currency_ref == 1 else 'rmb',
                               title='ارز', sepidar_id=currency_ref)
    order = SimpleNamespace(pk=order_id, order_number='ORD-' + str(order_id),
                            final_supplier=supplier, currency=currency,
                            final_item=SimpleNamespace(part_number=part_number))
    return SimpleNamespace(order=order, order_id=order_id,
                           quantity=3, description='توضیح ردیف')


class GIORedesignPreviewTests(SimpleTestCase):
    def test_preview_groups_supplier_and_currency_without_sepidar_calls(self):
        rows = OrderedDict([
            ('101___1', [fake_order(11, 101, 1, 'ABC-1')]),
            ('202___2', [fake_order(22, 202, 2, 'XYZ-2')]),
        ])
        successful = SimpleNamespace(
            group_key='101___1', status='success', invoice_id=111, invoice_number='901',
            receipt_id=112, receipt_number='902',
            voucher_id=113, voucher_number='903',
            last_error='', attempt_count=1,
        )
        gio = SimpleNamespace(
            sepidar_buy_factor_response_json=None,
            sepidar_inventory_receipt_response_json=None,
            sepidar_groups=SimpleNamespace(all=lambda: [successful]),
        )
        with patch('order.gio_sepidar.plan_gio_groups', return_value=rows), patch(
            'order.gio_sepidar.SepidarApiCall.gio_to_sepidar',
        ) as send:
            groups = gio_preview_groups(gio)
        send.assert_not_called()
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0]['key'], '101___1')
        self.assertEqual(groups[0]['supplier_ref'], '101')
        self.assertEqual(groups[0]['status'], 'success')
        self.assertFalse(groups[0]['can_send'])
        self.assertEqual(groups[0]['invoice']['number'], '901')
        self.assertEqual(groups[0]['items'][0]['order_number'], 'ORD-11')
        self.assertEqual(groups[1]['key'], '202___2')
        self.assertEqual(groups[1]['currency_ref'], '2')
        self.assertTrue(groups[1]['can_send'])
        self.assertEqual(groups[1]['row_count'], 1)

    def test_unknown_groups_are_not_retryable(self):
        row = fake_order(12, 101, 1, 'ABC-2')
        unknown = SimpleNamespace(
            group_key='101___1', status='unknown', invoice_id=None, invoice_number=None,
            receipt_id=None, receipt_number=None, voucher_id=None, voucher_number=None,
            last_error='Connection timed out', attempt_count=1,
        )
        gio = SimpleNamespace(
            sepidar_buy_factor_response_json=None,
            sepidar_inventory_receipt_response_json=None,
            sepidar_groups=SimpleNamespace(all=lambda: [unknown]),
        )
        with patch('order.gio_sepidar.plan_gio_groups',
                   return_value=OrderedDict([('101___1', [row])])):
            group = gio_preview_groups(gio)[0]
        self.assertEqual(group['status'], 'unknown')
        self.assertFalse(group['can_send'])
        self.assertIn('timed out', group['error'])

    def test_preview_endpoint_returns_grouped_rendered_three_documents(self):
        row = fake_order(12, 101, 1, 'ABC-2')
        gio = SimpleNamespace(pk=19)
        groups = [{
            'key':'101___1', 'supplier':'تأمین‌کننده تست', 'supplier_ref':'101',
            'currency':'Dollar', 'currency_ref':'1', 'row_count':1,
            'status':'pending', 'can_send':True, 'error':'',
            'invoice':{}, 'receipt':{}, 'voucher':{},
            'items':[{'order_number':'ORD-12','part_number':'ABC-2','quantity':'3'}],
        }]
        request = RequestFactory().get('/order/ajax/order_and_sepidar/', {
            'view_name':'trade_buy_factor_preview', 'gio_id':'19',
        })
        request.user = SimpleNamespace(is_authenticated=True)
        with patch('order.views.GIO.objects.filter') as filtered, patch(
            'order.views.gio_preview_groups', return_value=groups,
        ), patch('order.views.user_can_send_gio', return_value=True), patch(
            'order.views.render_to_string',
            side_effect=lambda template_name, context, request: render_to_string(
                template_name, context,
            ),
        ):
            filtered.return_value.first.return_value = gio
            response = OrderAndSepidar().trade_buy_factor_preview(request)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertEqual(content['groups'][0]['key'], '101___1')
        self.assertIn('فاکتور خرید', content['res'])
        self.assertIn('رسید انبار قبل از مرکزی', content['res'])
        self.assertIn('سند حسابداری', content['res'])
        self.assertIn('ارسال این گروه', content['res'])
        self.assertIn('ORD-12', content['res'])


class GIORedesignTemplateTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        root = Path(settings.BASE_DIR) / 'order' / 'templates' / 'order'
        cls.page = (root / 'gio' / 'quick_gio_update.html').read_text(encoding='utf-8')
        cls.preview = (root / 'partial' / 'sepidar' /
                       'trade_buy_factor_preview.html').read_text(encoding='utf-8')

    def test_django_templates_compile(self):
        get_template('order/gio/quick_gio_update.html')
        get_template('order/partial/sepidar/trade_buy_factor_preview.html')

    def test_right_order_table_left_gio_form_in_responsive_layout(self):
        self.assertIn('class="gio-layout"', self.page)
        self.assertLess(self.page.index('gio-table-panel'), self.page.index('gio-form-panel"'))
        self.assertIn('grid-template-columns:minmax(0,1.42fr) minmax(350px,1fr)', self.page)
        self.assertIn('@media(max-width:1170px)', self.page)
        self.assertIn('{% render_field_by_order form form.gio_date form.description', self.page)
        self.assertIn('form_s.order form_s.quantity form_s.description', self.page)

    def test_saved_document_preview_and_mock_are_separate_tabs(self):
        for name in ('editor', 'preview', 'documents'):
            self.assertIn('data-gio-tab="' + name + '"', self.page)
        self.assertIn('gio-document-mock-modal', self.page)
        self.assertIn('MOCK', self.page)
        self.assertIn('gio-sepidar-group-data', self.page)
        self.assertIn('td.textContent = value', self.page)
        self.assertNotIn('/sepidar/get/', self.page)

    def test_table_does_not_use_hidden_metadata_columns(self):
        columns = QuickGIODataTableListView.column_defs
        names = {column['name'] for column in columns}
        self.assertNotIn('id', names)
        self.assertNotIn('show_order_str', names)
        self.assertNotIn('item__sepidar_id_0', names)
        self.assertFalse(any('d-none' in column.get('className', '') for column in columns))
        self.assertTrue(any('data-order-id=' in str(c) for c in QuickGIODataTableListView.customize_row.__code__.co_consts))
        self.assertIn("button.dataset.orderId", self.page)
        self.assertIn('button.dataset.maxQty', self.page)

    def test_column_search_is_debounced_for_200ms(self):
        """Avoid a request on each keystroke in django-ajax-datatable column filters."""
        self.assertIn("installGioColumnSearchDebounce", self.page)
        self.assertIn("initComplete.gioColumnDebounce", self.page)
        self.assertIn(".datatable-column-filter-row input[data-index]", self.page)
        self.assertIn("$filters.off('keyup change')", self.page)
        self.assertIn("$filters.on('input.gioColumnDebounce'", self.page)
        self.assertIn("clearTimeout(searchTimer)", self.page)
        self.assertIn("setTimeout(function () {", self.page)
        self.assertIn("}, 200);", self.page)
        self.assertIn("if (changed) api.draw()", self.page)
        self.assertIn("searchDelay:200", self.page)

    def test_initial_sort_keys_are_existing_orderable_columns(self):
        """ajax_datatable rejects initial_order when a column has been removed."""
        columns = {column['name']: column for column in QuickGIODataTableListView.column_defs}
        for key, direction in QuickGIODataTableListView.initial_order:
            with self.subTest(column=key):
                self.assertIn(key, columns)
                self.assertTrue(columns[key].get('orderable', True))
                self.assertIn(direction, ('asc', 'desc'))
        self.assertEqual(QuickGIODataTableListView.initial_order, [['order_number', 'desc']])

    def test_ajax_datatable_queryset_does_not_force_deferred_foreign_keys(self):
        """ajax_datatable may defer FK fields; select_related would raise FieldError."""
        view = QuickGIODataTableListView()
        with patch.object(QuickGIODataTableListView, 'model') as model:
            qs = model.objects.annotate.return_value.filter.return_value
            self.assertIs(view.get_initial_queryset(), qs)
            model.objects.annotate.assert_called_once()
            qs.select_related.assert_not_called()

    def test_each_group_has_three_docs_and_independent_retry(self):
        for label in ('فاکتور خرید', 'رسید انبار قبل از مرکزی', 'سند حسابداری'):
            self.assertIn(label, self.preview)
        self.assertIn('data-group-key="{{ group.key }}"', self.preview)
        self.assertIn('gio-send-group', self.preview)
        self.assertIn("group.can_send", self.preview)
        self.assertIn("group.status == 'unknown'", self.preview)
        self.assertIn("gio_is_locked", self.page)
