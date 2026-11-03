"""Regression tests for language-neutral Quick Packing error responses."""
import json
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from order.packing_error_messages import (
    EXACT_ERROR_CODES, ROW_SUFFIX_CODES, classify_packing_error,
    packing_error_payload,
)


class PackingErrorCodeTests(SimpleTestCase):
    def test_warehouse_receipt_validation_has_stable_code(self):
        code, params = classify_packing_error(
            'Received/damaged quantities are outside the Packing quantity.'
        )
        self.assertEqual(code, 'packing_err_quantities_out_of_range')
        self.assertEqual(params, {})

    def test_warehouse_return_lock_has_stable_code(self):
        self.assertEqual(classify_packing_error(
            'برای این پکینگ اطلاعات انبار ثبت شده و امکان عودت به مرحله قبل وجود ندارد.'
        )[0], 'packing_err_return_locked')

    def test_row_errors_keep_row_identifier_as_separate_parameter(self):
        payload = packing_error_payload(
            ValueError('Packing row 151: destination warehouse is required.')
        )
        self.assertEqual(payload, {
            'error_code': 'packing_err_row_destination_required',
            'error_params': {'row': '151'},
        })

    def test_invalid_quantity_and_field_have_safe_parameter(self):
        self.assertEqual(
            classify_packing_error('Invalid quantity in row 12.'),
            ('packing_err_row_quantity_invalid', {'row': '12'}),
        )
        self.assertEqual(
            classify_packing_error('Invalid ruined_quantity value.'),
            ('packing_err_invalid_field', {'field': 'ruined_quantity'}),
        )

    def test_unexpected_remote_error_is_not_exposed_as_translation_key(self):
        code, params = classify_packing_error(
            '<script>alert("remote")</script> validation exception'
        )
        self.assertEqual(code, 'packing_err_unexpected')
        self.assertEqual(params, {})

    def test_all_known_errors_have_translations_for_each_portal_language(self):
        required = (set(EXACT_ERROR_CODES.values()) | set(ROW_SUFFIX_CODES.values()) |
                    {
                        'packing_err_row_invalid', 'packing_err_row_quantity_invalid',
                        'packing_err_invalid_field', 'packing_err_assignee_missing',
                        'packing_err_unexpected', 'packing_err_network',
                        'packing_err_form_invalid', 'packing_err_form_invalid_value',
                        'packing_err_form_required', 'packing_err_form_invalid_choice',
                        'packing_err_form_invalid_date', 'packing_err_form_max_length',
                        'packing_err_form_min_value', 'packing_err_form_max_value',
                        'packing_err_sepidar_uncertain', 'packing_err_sepidar_rejected',
                        'packing_err_preview_failed', 'packing_err_send_failed',
                        'packing_err_assignee_required', 'packing_err_packing_capacity',
                        'packing_field_general', 'packing_field_wh_destination',
                        'packing_field_warehouse_destination',
                        'packing_field_wh_receipt_quantity',
                        'packing_field_ruined_quantity',
                    })
        for lang in ('fa', 'en', 'gr', 'it', 'ru', 'sp'):
            with self.subTest(lang=lang):
                file = Path(settings.BASE_DIR) / 'assets' / 'lang' / f'{lang}.json'
                data = json.loads(file.read_text(encoding='utf-8'))
                self.assertFalse(sorted(key for key in required if not data.get(key)))

    def test_error_messages_do_not_use_untranslated_input_as_keys(self):
        page = (Path(settings.BASE_DIR) /
                'order/templates/order/packing/quick_packing_create.html').read_text(encoding='utf-8')
        self.assertIn('function localizedPackingError(code, params = {})', page)
        self.assertIn('function localizedSepidarTransferError(transfer)', page)
        self.assertIn('payload.error_code', page)
        self.assertIn('packing_err_quantities_out_of_range', page)
        self.assertIn('packing_err_packing_capacity', page)
        self.assertIn('packing_err_form_invalid_value', page)
        self.assertIn('if (error) console.warn', page)
        self.assertIn('localizedSepidarTransferError(transfer)', page)
        self.assertIn('localizedPackingError(\'packing_err_network\')', page)
