"""Stable error identifiers for Quick Packing.

The API keeps the original error for diagnostics, but the browser translates
error_code using the language selected in the Portal UI. Never derive a
translation key directly from untrusted remote error strings.
"""
import re


EXACT_ERROR_CODES = {
    'انبار مقصد انتخاب‌شده معتبر نیست.': 'packing_err_destination_invalid',
    'Received/damaged quantities are outside the Packing quantity.': 'packing_err_quantities_out_of_range',
    'A Sepidar transfer exists; quantities and destination are locked.': 'packing_err_sepidar_locked',
    'برای این پکینگ اطلاعات انبار ثبت شده و امکان عودت به مرحله قبل وجود ندارد.': 'packing_err_return_locked',
    'All Sepidar warehouse transfers must succeed before completion.': 'packing_err_transfers_incomplete',
    'Packing workflow access denied.': 'packing_err_forbidden',
    'Packing document view access denied.': 'packing_err_forbidden',
    'Packing Sepidar transfer access denied.': 'packing_err_forbidden',
    'Packing items can only be added in the first workflow state.': 'packing_err_add_items_limited',
    'Packing items can only be deleted in the first workflow state.': 'packing_err_delete_items_limited',
    'Packing item does not belong to this Packing.': 'packing_err_item_not_found',
    'File upload is not allowed in this workflow stage.': 'packing_err_file_forbidden',
    'Packing is already in the last workflow state.': 'packing_err_last_stage',
    'Packing is already in the first workflow state.': 'packing_err_first_stage',
    'Invalid workflow action.': 'packing_err_workflow_action',
    'Select at least one order for Packing.': 'packing_err_no_order',
    'An order cannot be added twice in one request.': 'packing_err_duplicate_order',
    'No received quantity to send to Sepidar.': 'packing_err_no_received',
    'Sepidar source warehouse is not configured.': 'packing_err_sepidar_config',
    'Legacy Sepidar transfer exists. Reconcile its documents before sending again.': 'packing_err_legacy_transfer',
    'Legacy Sepidar transfer must be reconciled before resending.': 'packing_err_legacy_transfer',
    'Previous transfer documents conflict with current Packing rows.': 'packing_err_transfer_conflict',
    'Existing transfer records conflict with Packing rows.': 'packing_err_transfer_conflict',
    'Sent/in-flight transfer differs from current Packing rows.': 'packing_err_sepidar_locked',
    'Previously sent transfer differs from current Packing.': 'packing_err_sepidar_locked',
    'This transfer is already registered or needs reconciliation.': 'packing_err_sepidar_locked',
    'This transfer group does not exist in the saved Packing.': 'packing_err_transfer_group_missing',
    'Invalid transfer group type.': 'packing_err_transfer_group_invalid',
    'Invalid destination warehouse.': 'packing_err_destination_invalid',
    'Invalid transfer request.': 'packing_err_transfer_group_invalid',
    'Incomplete transfer group.': 'packing_err_transfer_group_invalid',
    'Selected user is not a valid member of the current workflow group.': 'packing_err_assignee_invalid',
    'Only workflow admins can change the assigned user.': 'packing_err_forbidden',
}
ROW_SUFFIX_CODES = {
    'destination warehouse is required.': 'packing_err_row_destination_required',
    'invalid destination warehouse.': 'packing_err_row_destination_invalid',
    'received/damaged quantity is required.': 'packing_err_row_quantities_required',
    'received/damaged exceeds Packing quantity.': 'packing_err_row_quantities_excess',
    'item has no Sepidar code.': 'packing_err_row_item_code_missing',
    'invalid quantity': 'packing_err_row_quantity_invalid',
    'invalid quantity or precision': 'packing_err_row_quantity_invalid',
}
ROW_PATTERN = re.compile(r'^Packing row (?P<row>\d+): (?P<detail>.+)$')
ITEM_QUANTITY_PATTERN = re.compile(r'^Invalid quantity for PackingItem (?P<row>\d+)\.$')
FORM_QUANTITY_PATTERN = re.compile(r'^Invalid quantity in row (?P<row>\d+)\.$')
FIELD_PATTERN = re.compile(r'^Invalid (?P<field>[a-z_]+) value\.$')


def classify_packing_error(error):
    """Return a stable key and safe formatting parameters, never raw HTML."""
    message = str(error).strip()
    if message in EXACT_ERROR_CODES:
        return EXACT_ERROR_CODES[message], {}
    match = ROW_PATTERN.match(message)
    if match:
        return ROW_SUFFIX_CODES.get(match.group('detail'), 'packing_err_row_invalid'), {
            'row': match.group('row'),
        }
    for pattern, key in (
        (ITEM_QUANTITY_PATTERN, 'packing_err_row_quantity_invalid'),
        (FORM_QUANTITY_PATTERN, 'packing_err_row_quantity_invalid'),
        (FIELD_PATTERN, 'packing_err_invalid_field'),
    ):
        match = pattern.match(message)
        if match:
            return key, match.groupdict()
    if message.startswith('No user is available in workflow group '):
        return 'packing_err_assignee_missing', {}
    if message.startswith('Missing Sepidar delivery/receipt identifiers'):
        return 'packing_err_sepidar_uncertain', {}
    if message.startswith('Invalid Sepidar response'):
        return 'packing_err_sepidar_uncertain', {}
    return 'packing_err_unexpected', {}


def packing_error_payload(error):
    code, params = classify_packing_error(error)
    return {'error_code': code, 'error_params': params}
