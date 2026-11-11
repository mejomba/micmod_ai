"""Layout, preview, and mock-details regression checks for Quick GIO."""
import json
from collections import OrderedDict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.template.loader import get_template, render_to_string
from django.test import RequestFactory, SimpleTestCase

from order.gio_sepidar import gio_preview_groups, gio_header_status, gio_registered_group_count
from order.views import OrderAndSepidar, QuickGIODataTableListView, QuickGIOView


def fake_order(order_id, supplier_ref, currency_ref, part_number):
    supplier = SimpleNamespace(dlref=supplier_ref)
    currency = SimpleNamespace(title_en='Dollar' if currency_ref == 1 else 'rmb',
                               title='ارز', sepidar_id=currency_ref)
    order = SimpleNamespace(pk=order_id, order_number='ORD-' + str(order_id),
                            final_supplier=supplier, currency=currency,
                            final_item=SimpleNamespace(
                                part_number=part_number, sku='SKU-' + str(order_id)))
    return SimpleNamespace(order=order, order_id=order_id,
                           quantity=3, description='توضیح ردیف')


class GIOHeaderPresentationTests(SimpleTestCase):
    def test_header_tones_cover_draft_saved_complete_partial_and_warnings(self):
        gio = SimpleNamespace(
            sepidar_buy_factor_response_json=None,
            sepidar_inventory_receipt_response_json=None,
        )
        cases = [
            (None, [], 'draft', 'ثبت اولیه'),
            (gio, [], 'info', 'ثبت‌شده در پرتال'),
            (gio, ['pending'], 'info', 'ثبت‌شده در پرتال'),
            (gio, ['success'], 'success', 'ارسال کامل به سپیدار'),
            (gio, ['success', 'pending'], 'warning', 'ارسال بخشی از گروه‌ها'),
            (gio, ['success', 'preview_error'], 'warning', 'بررسی گروه‌های سپیدار لازم است'),
            (gio, ['preview_error'], 'warning', 'بررسی گروه‌های سپیدار لازم است'),
            (gio, ['sending'], 'warning', 'در حال ارسال به سپیدار'),
            (gio, ['reviewed'], 'warning', 'بررسی‌شده؛ آماده ارسال مجدد'),
            (gio, ['failed', 'success'], 'danger', 'ارسال ناموفق به سپیدار'),
            (gio, ['unknown', 'success'], 'danger', 'نیازمند بررسی دستی سپیدار'),
            (gio, ['unknown', 'failed'], 'danger', 'نیازمند بررسی دستی سپیدار'),
        ]
        for obj, statuses, tone, label in cases:
            with self.subTest(statuses=statuses):
                self.assertEqual(gio_header_status(obj, statuses), {
                    'tone': tone, 'label': label,
                })
        legacy_gio = SimpleNamespace(
            sepidar_buy_factor_response_json={'purchase_invoice': [1001]},
            sepidar_inventory_receipt_response_json=None,
        )
        self.assertEqual(gio_header_status(legacy_gio, [])['tone'], 'success')

    def test_registered_group_badge_counts_successful_groups_not_documents(self):
        self.assertEqual(gio_registered_group_count(['success']), 1)
        self.assertEqual(gio_registered_group_count(
            ['success', 'pending', 'unknown', 'failed', 'reviewed']), 1)
        self.assertEqual(gio_registered_group_count(['success', 'success']), 2)
        self.assertEqual(gio_registered_group_count(['failed', 'pending']), 0)
        self.assertEqual(gio_registered_group_count([]), 0)
        self.assertEqual(gio_registered_group_count(None), 0)

    def test_get_uses_planned_groups_for_header_and_persisted_success_for_badge(self):
        # The missing pending group has no database record yet.
        gio = SimpleNamespace(
            pk=42,
            sepidar_buy_factor_response_json=None,
            sepidar_inventory_receipt_response_json=None,
            sepidar_groups=SimpleNamespace(values_list=lambda *args, **kwargs: ['success']),
        )
        request = RequestFactory().get('/order/quick_gio/42/')
        request.user = SimpleNamespace(
            is_authenticated=True, is_superuser=False, is_active=True,
        )
        planned = [
            {'key': '101___1', 'status': 'success'},
            {'key': '202___1', 'status': 'pending'},
        ]
        with patch.object(QuickGIOView, 'get_object', return_value=gio), patch(
            'order.views.gio_preview_groups', return_value=planned,
        ), patch('order.views.gio_document_display', return_value={
            'purchase_invoice': [11], 'before_central_wh_receipt': [12],
            'voucher': [13],
        }), patch('order.views.GIOForm'), patch(
            'order.views.GIOItemFormSet',
        ), patch('order.views.GIOItem.objects.filter'), patch(
            'order.views.gio_is_locked', return_value=True,
        ), patch('order.views.user_can_send_gio', return_value=True), patch(
            'order.views.render',
        ) as render_view:
            QuickGIOView().get(request, pk=gio.pk)
        context = render_view.call_args.args[2]
        self.assertEqual(context['gio_hero_status']['tone'], 'warning')
        self.assertEqual(context['gio_hero_status']['label'], 'ارسال بخشی از گروه‌ها')
        self.assertEqual(context['gio_registered_group_count'], 1)
        self.assertTrue(context['gio_has_group_submissions'])


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
        self.assertEqual(groups[0]['items'][0]['sku'], 'SKU-11')
        self.assertEqual(groups[1]['key'], '202___2')
        self.assertEqual(groups[1]['currency_ref'], '2')
        self.assertTrue(groups[1]['can_send'])
        self.assertEqual(groups[1]['row_count'], 1)

    def test_preview_sku_comes_from_final_trade_item_not_sales_item(self):
        row = fake_order(31, 101, 1, 'TRADE-PN')
        # In trade orders the purchasing item can differ from the sales item.
        row.order.item = SimpleNamespace(sku='SALES-SKU', part_number='SALES-PN')
        row.order.final_item = SimpleNamespace(sku='TRADE-SKU', part_number='TRADE-PN')
        gio = SimpleNamespace(
            sepidar_buy_factor_response_json=None,
            sepidar_inventory_receipt_response_json=None,
            sepidar_groups=SimpleNamespace(all=lambda: []),
        )
        with patch('order.gio_sepidar.plan_gio_groups',
                   return_value=OrderedDict([('101___1', [row])])):
            item = gio_preview_groups(gio)[0]['items'][0]
        self.assertEqual(item['sku'], 'TRADE-SKU')
        self.assertEqual(item['part_number'], 'TRADE-PN')

    def test_preview_missing_sku_is_displayed_as_placeholder(self):
        row = fake_order(32, 101, 1, 'NO-SKU-PN')
        row.order.final_item.sku = None
        gio = SimpleNamespace(
            sepidar_buy_factor_response_json=None,
            sepidar_inventory_receipt_response_json=None,
            sepidar_groups=SimpleNamespace(all=lambda: []),
        )
        with patch('order.gio_sepidar.plan_gio_groups',
                   return_value=OrderedDict([('101___1', [row])])):
            item = gio_preview_groups(gio)[0]['items'][0]
        self.assertEqual(item['sku'], '-')

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
        self.assertIn('<th>SKU</th>', content['res'])


class GIORedesignTemplateTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        root = Path(settings.BASE_DIR) / 'order' / 'templates' / 'order'
        cls.page = (root / 'gio' / 'quick_gio_update.html').read_text(encoding='utf-8')
        cls.preview = (root / 'partial' / 'sepidar' /
                       'trade_buy_factor_preview.html').read_text(encoding='utf-8')

    def test_standalone_preview_loads_humanize_for_intcomma(self):
        """An included template is also rendered directly by the AJAX preview."""
        self.assertEqual(self.preview.splitlines()[0], '{% load humanize %}')
        for name in ('group.row_count', 'group.total_quantity', 'item.quantity'):
            self.assertIn('{{ ' + name + '|intcomma }}', self.preview)
        get_template('order/partial/sepidar/trade_buy_factor_preview.html')

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

    def test_preview_and_mock_document_rows_display_sku_column(self):
        self.assertIn('<th>SKU</th>', self.preview)
        self.assertIn('{{ item.sku }}', self.preview)
        self.assertIn('<th>SKU</th>', self.page)
        self.assertIn("item.sku || '—'", self.page)

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

    def test_save_existing_gio_reloads_saved_rows_and_shows_success(self):
        """A hash-only navigation on the same GIO does not refresh saved items."""
        self.assertIn("if (isSaved) {", self.page)
        self.assertIn("target.searchParams.set('gio_saved', '1')", self.page)
        self.assertIn("target.hash = '#gio-editor'", self.page)
        self.assertIn("target.hash = '#gio-preview'", self.page)
        self.assertIn("window.location.assign(target.toString())", self.page)
        self.assertIn("loadedUrl.searchParams.get('gio_saved') === '1'", self.page)
        self.assertIn("تغییرات GIO با موفقیت ذخیره شد.", self.page)
        self.assertIn("loadedUrl.searchParams.delete('gio_saved')", self.page)
        self.assertIn("window.history.replaceState(null, '', loadedUrl.toString())", self.page)
        self.assertNotIn("response.res.url + '#gio-preview'", self.page)

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

    def test_preview_groups_expose_total_quantity_for_closed_summary(self):
        rows = OrderedDict([('101___1', [
            fake_order(11, 101, 1, 'ABC-1'),
            fake_order(12, 101, 1, 'ABC-2'),
        ])])
        gio = SimpleNamespace(
            sepidar_buy_factor_response_json=None,
            sepidar_inventory_receipt_response_json=None,
            sepidar_groups=SimpleNamespace(all=lambda: []),
        )
        with patch('order.gio_sepidar.plan_gio_groups', return_value=rows):
            group = gio_preview_groups(gio)[0]
        self.assertEqual(group['row_count'], 2)
        self.assertEqual(group['total_quantity'], '6')

    def test_preview_groups_are_collapsed_accessible_accordion_with_summary(self):
        groups = [
            {'key': '101___1', 'supplier': 'تأمین‌کننده اول', 'currency': 'Dollar',
             'supplier_ref': '101', 'currency_ref': '1', 'row_count': 2,
             'total_quantity': '6', 'status': 'success', 'can_send': False,
             'invoice': {'id': 5, 'number': 'INV-77'},
             'receipt': {'id': 6, 'number': 'REC-78'},
             'voucher': {'id': 7, 'number': 'ACC-79'}, 'items': [],
             'error': ''},
            {'key': '202___2', 'supplier': 'تأمین‌کننده دوم', 'currency': 'rmb',
             'supplier_ref': '202', 'currency_ref': '2', 'row_count': 1,
             'total_quantity': '3', 'status': 'pending', 'can_send': True,
             'invoice': {}, 'receipt': {}, 'voucher': {},
             'items': [{'order_number': 'ORD-22', 'part_number': 'XYZ',
                        'quantity': '3'}], 'error': ''},
        ]
        html = render_to_string(
            'order/partial/sepidar/trade_buy_factor_preview.html',
            {'groups': groups, 'gio_sepidar_can_send': True},
        )
        self.assertEqual(html.count('<details class="gio-group-card gio-preview-group'), 2)
        self.assertEqual(html.count('<summary class="gio-group-head gio-accordion-summary">'), 2)
        self.assertEqual(html.count('</details>'), 2)
        self.assertIn('name="gio-sepidar-accordion"', html)
        self.assertNotIn(' name="gio-sepidar-accordion" open', html)
        for value in ('تأمین‌کننده اول', 'Dollar', '2 ردیف سفارش',
                      'مجموع تعداد: 6', 'ارسال موفق',
                      'INV-77', 'REC-78', 'ACC-79', 'آماده ارسال'):
            self.assertIn(value, html)
        self.assertEqual(html.count('class="gio-eyebrow gio-accordion-heading"'), 2)
        self.assertEqual(html.count('class="gio-accordion-group-label"'), 2)
        self.assertIn('گروه 1 ·', html)
        self.assertIn('گروه 2 ·', html)
        self.assertNotIn('تأمین‌کننده / ارز', html)
        self.assertNotIn('۳ سند سپیدار', html)
        self.assertNotIn('class="gio-accordion-title"', html)
        self.assertIn('class="gio-eyebrow gio-accordion-heading"', self.preview)
        self.assertIn('.gio-accordion-heading strong {font-weight:800}', self.page)
        self.assertIn('data-group-key="202___2"', html)
        self.assertIn('gio-send-group', html)
        self.assertIn('ORD-22', html)
        self.assertIn('gio-accordion-toggle', html)

    def test_preview_accordion_has_keyboard_focus_and_exclusive_toggle(self):
        self.assertIn('.gio-accordion-summary:focus-visible', self.page)
        self.assertIn('.gio-accordion-item[open]', self.page)
        self.assertIn("panel.addEventListener('toggle'", self.page)
        self.assertIn('if (other !== panel && other.open) other.open = false', self.page)

    def test_datatable_quantities_have_thousand_separators_but_picker_values_remain_raw(self):
        order = SimpleNamespace(
            pk=98765, order_number='PO-100200', final_quantity=1234567.5,
            quantity_in_gio=567.25,
            final_item=SimpleNamespace(part_number='ABC-12345'),
            currency=SimpleNamespace(title_en='Dollar'),
        )
        row = {}
        QuickGIODataTableListView().customize_row(row, order)
        self.assertEqual(row['quantity'], '1,234,567.5')
        self.assertEqual(row['remaining_quantity'], '1,234,000.25')
        self.assertIn('data-order-id="98765"', row['buy_factor'])
        self.assertIn('data-max-qty="1234000.25"', row['buy_factor'])
        self.assertIn('PO-100200', row['buy_factor'])
        self.assertIn('ABC-12345', row['buy_factor'])

    def test_preview_quantity_separator_without_formatting_document_identifiers(self):
        groups = [{
            'key': '101___1', 'supplier': 'Supplier', 'currency': 'Dollar',
            'supplier_ref': '101', 'currency_ref': '1',
            'row_count': 1250, 'total_quantity': '1234567.125',
            'status': 'success', 'can_send': False, 'error': '',
            'invoice': {'id': 1234567, 'number': 'INV-1234567'},
            'receipt': {'id': 5678, 'number': 'REC-5678'},
            'voucher': {'id': 9012, 'number': 'ACC-9012'},
            'items': [{'order_number': 'PO-1234567', 'part_number': 'PN-1234567',
                       'quantity': '1234567.125'}],
        }]
        html = render_to_string(
            'order/partial/sepidar/trade_buy_factor_preview.html',
            {'groups': groups, 'gio_sepidar_can_send': True},
        )
        self.assertIn('1,250 ردیف سفارش', html)
        self.assertIn('مجموع تعداد: 1,234,567.125', html)
        self.assertIn('<td>1,234,567.125</td>', html)
        self.assertIn('INV-1234567', html)
        self.assertIn('PO-1234567', html)
        self.assertIn('PN-1234567', html)
        self.assertNotIn('INV-1,234,567', html)

    def test_saved_and_mock_quantities_use_display_only_number_format(self):
        self.assertIn("{{ gio.quantity|intcomma }}", self.page)
        self.assertIn("{{ gios.count|intcomma }}", self.page)
        self.assertIn("{{ group.row_count|intcomma }}", self.page)
        self.assertIn("formatGioQuantity(item.quantity)", self.page)
        self.assertIn("toLocaleString('en-US'", self.page)
        self.assertIn("data-quantity=\"{{ gio.quantity }}\"", self.page)
        self.assertIn("field.value = maxQuantity", self.page)

    def test_send_response_reloads_exact_group_and_shows_in_card(self):
        self.assertIn("function refreshGioSendResult(status, groupKey)", self.page)
        self.assertIn("target.searchParams.set('gio_send_notice', status)", self.page)
        self.assertIn("target.searchParams.set('gio_send_group', groupKey)", self.page)
        self.assertIn("window.location.replace(target.toString())", self.page)
        self.assertIn("loadedUrl.searchParams.delete('gio_send_notice')", self.page)
        self.assertIn("loadedUrl.searchParams.delete('gio_send_group')", self.page)
        self.assertIn("showGioGroupMessage(sendGroup, message, !sent)", self.page)
        self.assertIn("function gioGroupResult(response, key)", self.page)
        self.assertIn("group.key === key", self.page)
        self.assertIn("group && group.status === 'success'", self.page)
        self.assertIn("group.status === 'failed' ? 'failed' : 'uncertain'", self.page)
        self.assertIn("timeout:120000", self.page)
        self.assertIn("بررسی وضعیت الزامی است", self.page)
        self.assertNotIn("success:showUpdatedDocuments", self.page)

    def test_success_error_and_processing_feedback_stay_inside_correct_group(self):
        self.assertIn('gio-group-send-feedback', self.preview)
        self.assertIn('aria-live="polite"', self.preview)
        self.assertIn("function showGioGroupMessage(groupKey, message, error)", self.page)
        self.assertIn("item.dataset.groupKey === groupKey", self.page)
        self.assertIn("panel.open = true", self.page)
        self.assertIn("panel.querySelector('.gio-group-send-feedback')", self.page)
        self.assertIn("feedback.textContent = String(message || '')", self.page)
        self.assertIn("showGioGroupMessage(groupKey, 'در حال ارسال", self.page)
        self.assertIn("showGioGroupMessage(groupKey, uncertain", self.page)
        self.assertIn("target.searchParams.set('gio_review_group', currentReviewGroup)", self.page)

    def test_steps_removed_and_registered_documents_have_count_badge(self):
        self.assertNotIn('class="gio-steps"', self.page)
        self.assertNotIn('class="gio-step"', self.page)
        self.assertNotIn('.gio-steps {', self.page)
        self.assertIn('gio_registered_group_count', self.page)
        self.assertIn('aria-label="{{ gio_registered_group_count }} گروه دارای اسناد ثبت‌شده"', self.page)
        self.assertIn('{{ gio_registered_group_count|intcomma }}', self.page)
        self.assertNotIn('gio_registered_document_count', self.page)
        self.assertIn('gio-tab-count--empty', self.page)

    def test_hero_status_uses_server_derived_severity_and_color(self):
        self.assertIn('gio-hero-status--{{ gio_hero_status.tone }}', self.page)
        self.assertIn('{{ gio_hero_status.label }}', self.page)
        for tone in ('draft', 'info', 'warning', 'danger', 'success'):
            self.assertIn('.gio-hero-status--' + tone, self.page)

    def test_previous_sepidar_app_visibility_disclaimer_is_removed(self):
        self.assertNotIn("قابل‌مشاهده بودن سند حسابداری", self.page)
        self.assertNotIn("وجود شناسه یا رکورد در دیتابیس", self.page)
        self.assertNotIn("اگر سند را در برنامه نمی‌بینید", self.page)
        self.assertIn("پیش از هر ارسال مجدد، اسناد سپیدار را بررسی کنید", self.page)

    def test_failed_and_unknown_groups_can_expand_untruncated_escaped_error(self):
        from django.utils.html import escape
        full_error = 'Gateway failed: ' + ('ERR0123456789' * 130) + (
            '\nSQL: <script>alert("x")</script> | SELECT /api/response'
        )
        for status in ('failed', 'unknown'):
            with self.subTest(status=status):
                html = render_to_string(
                    'order/partial/sepidar/gio_group_error.html',
                    {'group': {'status': status, 'error': full_error}},
                )
                self.assertIn('gio-error-details', html)
                self.assertIn('مشاهده متن کامل خطا', html)
                self.assertIn('class="gio-error-text"', html)
                self.assertIn(escape(full_error.split('\n')[0]), html)
                self.assertIn('\nSQL:', html)
                self.assertIn('&lt;script&gt;', html)
                self.assertNotIn('<script>alert("x")</script>', html)
                self.assertIn('gio-error-copy', html)
        for status in ('pending', 'success', 'reviewed', 'sending'):
            self.assertNotIn(
                'gio-error-details',
                render_to_string(
                    'order/partial/sepidar/gio_group_error.html',
                    {'group': {'status': status, 'error': full_error}},
                ),
            )

    def test_all_gio_group_error_surfaces_use_shared_readable_component(self):
        include = "{% include 'order/partial/sepidar/gio_group_error.html' with group=group %}"
        self.assertIn(include, self.preview)
        self.assertIn(include, self.page)
        self.assertNotIn('<div class="mt-2">{{ group.error }}</div>', self.page)
        self.assertNotIn('<div class="gio-alert gio-alert--error">{{ group.error }}</div>', self.preview)
        self.assertIn('{{ group.error|truncatechars:100 }}', self.preview)
        self.assertIn('.gio-error-full {', self.page)
        self.assertIn('max-height:320px;overflow:auto', self.page)
        self.assertIn('white-space:pre-wrap;overflow-wrap:anywhere', self.page)
        self.assertIn('gio-error-details > summary:focus-visible', self.page)
        self.assertIn("event.target.closest('.gio-error-copy')", self.page)
        self.assertIn('navigator.clipboard.writeText(pre.textContent)', self.page)

    def test_each_group_has_three_docs_and_independent_retry(self):
        for label in ('فاکتور خرید', 'رسید انبار قبل از مرکزی', 'سند حسابداری'):
            self.assertIn(label, self.preview)
        self.assertIn('data-group-key="{{ group.key }}"', self.preview)
        self.assertIn('gio-send-group', self.preview)
        self.assertIn("group.can_send", self.preview)
        self.assertIn("group.status == 'unknown'", self.preview)
        self.assertIn("gio_is_locked", self.page)
