"""Portal-side Sepidar Packing warehouse transfers.

Each destination is an independent request and has an immutable successful
transfer record.  Network uncertainty is NOT considered a safe retry.
"""
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from order.packing_error_messages import packing_error_payload

from order.models import Order, Packing, PackingSepidarTransfer, PackingSepidarTransferItem
from sepidar.api_call import SepidarApiCall


class PackingTransferError(ValueError):
    pass


def decimal_quantity(value, label):
    try:
        result = Decimal(str(value))
    except (TypeError, InvalidOperation, ValueError):
        raise PackingTransferError(f'{label}: invalid quantity')
    if not result.is_finite() or result < 0 or result.as_tuple().exponent < -4:
        raise PackingTransferError(f'{label}: invalid quantity or precision')
    return result


def plan_packing_transfers(packing):
    """Split by (normal/damaged, Sepidar warehouse ID), never by header fallback."""
    groups = defaultdict(list)
    stock_ids = {int(x) for x in Order.sepidar_wh_map}
    source = settings.SEPIDAR_CONST_DATA.get('before_central_wh_id')
    if not source:
        raise PackingTransferError('Sepidar source warehouse is not configured.')
    items = (packing.packing_item_rel.filter(is_deleted=False)
             .select_related('order__item').order_by('pk'))
    seen = 0
    for item in items:
        seen += 1
        label = f'Packing row {item.pk}'
        if item.wh_destination in (None, ''):
            raise PackingTransferError(f'{label}: destination warehouse is required.')
        try:
            destination = int(item.wh_destination)
        except (ValueError, TypeError):
            raise PackingTransferError(f'{label}: invalid destination warehouse.')
        if destination not in stock_ids or destination == int(source):
            raise PackingTransferError(f'{label}: invalid destination warehouse.')
        if item.wh_receipt_quantity is None or item.ruined_quantity is None:
            raise PackingTransferError(f'{label}: received/damaged quantity is required.')
        arrived = decimal_quantity(item.wh_receipt_quantity, label)
        ruined = decimal_quantity(item.ruined_quantity, label)
        planned = decimal_quantity(item.quantity, label)
        if arrived > planned or ruined > arrived:
            raise PackingTransferError(f'{label}: received/damaged exceeds Packing quantity.')
        goods = getattr(getattr(item, 'order', None), 'item', None)
        code = getattr(goods, 'sepidar_id_0', None)
        if not code:
            raise PackingTransferError(f'{label}: item has no Sepidar code.')
        line = {
            'packing_item_id': item.pk,
            'itemref': int(code),
            'sku': str(getattr(goods, 'sku', None) or code),
            'part_number': str(item.part_number or getattr(goods, 'part_number', None) or ''),
            # The denominator is this row's total physically received quantity,
            # including any damaged pieces. It is not the original order quantity.
            'received_quantity': arrived,
        }
        healthy = arrived - ruined
        if healthy > 0:
            groups[('normal', destination)].append({**line, 'quantity': healthy})
        if ruined > 0:
            groups[('damaged', 42)].append({**line, 'quantity': ruined})
    if not seen or not groups:
        raise PackingTransferError('No received quantity to send to Sepidar.')
    return [
        {'transfer_type': kind, 'destination_stock_ref': dest,
         'source_stock_ref': int(source), 'lines': lines}
        for (kind, dest), lines in sorted(groups.items())
    ]


def transfer_snapshot(lines):
    return sorted((int(x['packing_item_id']), int(x['itemref']), str(x['quantity'].normalize()))
                  for x in lines)


def _quantity_text(quantity):
    return format(quantity.normalize(), 'f')


def _display_lines(group):
    """One transfer quantity and its received total for each Packing row.

    Groups already distinguish healthy and damaged documents, so showing both
    quantities in every group's table would be misleading.
    """
    return [
        {
            'packing_item_id': line['packing_item_id'],
            'item_ref': line['itemref'],
            'sku': line['sku'],
            'part_number': line['part_number'],
            'transfer_quantity': _quantity_text(line['quantity']),
            'received_quantity': _quantity_text(line['received_quantity']),
        }
        for line in group['lines']
    ]


def normalize_transfer_selection(transfer_type=None, destination_stock_ref=None):
    """None selects all; a group selection must provide both valid dimensions."""
    if transfer_type is None and destination_stock_ref is None:
        return None
    if transfer_type not in ('normal', 'damaged'):
        raise PackingTransferError('Invalid transfer group type.')
    try:
        destination = int(destination_stock_ref)
    except (ValueError, TypeError, OverflowError):
        raise PackingTransferError('Invalid destination warehouse.')
    if destination <= 0 or (transfer_type == 'damaged' and destination != 42):
        raise PackingTransferError('Invalid destination warehouse.')
    return (transfer_type, destination)


def saved_snapshot(transfer):
    return sorted((x.packing_item_id, x.item_ref, str(x.quantity.normalize()))
                  for x in transfer.lines.all())


def transfer_state(transfer):
    return {
        'id': transfer.pk,
        'type': transfer.transfer_type,
        'destination_stock_ref': transfer.destination_stock_ref,
        'status': transfer.status,
        'quantity': str(sum((line.quantity for line in transfer.lines.all()), Decimal('0'))),
        'delivery_id': transfer.delivery_id,
        'delivery_number': transfer.delivery_number,
        'receipt_id': transfer.receipt_id,
        'receipt_number': transfer.receipt_number,
        'error': transfer.last_error,
        'error_code': (packing_error_payload(transfer.last_error)['error_code']
                       if transfer.last_error else ''),
    }


def transfer_preview(packing):
    planned = plan_packing_transfers(packing)
    existing = list(packing.sepidar_transfers.prefetch_related('lines'))
    if packing.sepidar_wh_to_wh and not existing:
        raise PackingTransferError(
            'Legacy Sepidar transfer exists. Reconcile its documents before sending again.'
        )
    keys = {(x['transfer_type'], x['destination_stock_ref']) for x in planned}
    for old in existing:
        if ((old.transfer_type, old.destination_stock_ref) not in keys
                and old.status in ('success', 'sending', 'unknown')):
            raise PackingTransferError('Previous transfer documents conflict with current Packing rows.')
    lookup = {(x.transfer_type, x.destination_stock_ref): x for x in existing}
    result = []
    for group in planned:
        transfer = lookup.get((group['transfer_type'], group['destination_stock_ref']))
        if transfer and transfer.status in ('success', 'sending', 'unknown'):
            if saved_snapshot(transfer) != transfer_snapshot(group['lines']):
                raise PackingTransferError('Sent/in-flight transfer differs from current Packing rows.')
        result.append({
            'type': group['transfer_type'],
            'destination_stock_ref': group['destination_stock_ref'],
            'quantity': _quantity_text(sum(
                (line['quantity'] for line in group['lines']), Decimal('0'),
            )),
            'received_quantity': _quantity_text(sum(
                (line['received_quantity'] for line in group['lines']), Decimal('0'),
            )),
            'rows': len(group['lines']),
            'items': _display_lines(group),
            'status': transfer.status if transfer else 'pending',
            'delivery_number': transfer.delivery_number if transfer else None,
            'receipt_number': transfer.receipt_number if transfer else None,
            'error': transfer.last_error if transfer else '',
            'error_code': (packing_error_payload(transfer.last_error)['error_code']
                           if transfer and transfer.last_error else ''),
        })
    return result


def _parse_result(response):
    if not isinstance(response, dict):
        return 'unknown', None, 'Invalid Sepidar response'
    if response.get('errors'):
        return ('unknown' if response.get('uncertain') else 'failed'), None, str(response['errors'])
    try:
        documents = response['packing']['sepidar']
        if len(documents) != 1:
            raise ValueError('Expected exactly one transfer pair.')
        delivery = documents[0]['wh_delivery']
        receipt = documents[0]['wh_receipt']
        data = {
            'delivery_id': int(delivery['id']),
            'delivery_number': str(delivery['number']),
            'receipt_id': int(receipt['id']),
            'receipt_number': str(receipt['number']),
        }
        if min(data['delivery_id'], data['receipt_id']) <= 0 or not all(
            (data['delivery_number'], data['receipt_number'])
        ):
            raise ValueError('Incomplete Sepidar document identifiers.')
        return 'success', data, ''
    except (KeyError, TypeError, ValueError, IndexError):
        return 'unknown', None, 'Missing Sepidar delivery/receipt identifiers; reconcile manually.'


def send_packing_transfers(packing, request, group_key=None):
    """Atomically reserve only requested work; never resend uncertain/successful documents."""
    from sepidar.data import SepidarDataFactory

    if group_key is not None:
        group_key = normalize_transfer_selection(*group_key)
    to_send = []
    with transaction.atomic():
        packing = Packing.objects.select_for_update().get(pk=packing.pk)
        # Validation always runs for the whole Packing, not only failed groups.
        groups = plan_packing_transfers(packing)
        existing = list(PackingSepidarTransfer.objects.select_for_update()
                        .filter(packing=packing).prefetch_related('lines'))
        if packing.sepidar_wh_to_wh and not existing:
            raise PackingTransferError('Legacy Sepidar transfer must be reconciled before resending.')
        group_keys = {(g['transfer_type'], g['destination_stock_ref']) for g in groups}
        if group_key is not None and group_key not in group_keys:
            raise PackingTransferError('This transfer group does not exist in the saved Packing.')
        for old in existing:
            if (old.transfer_type, old.destination_stock_ref) in group_keys:
                continue
            if old.status in ('success', 'sending', 'unknown'):
                raise PackingTransferError('Existing transfer records conflict with Packing rows.')
            # In single-group mode, do not mutate unrelated failed records.
            # Global mode may prune definitively failed, obsolete groups.
            if group_key is None:
                old.delete()
        prior = {(x.transfer_type, x.destination_stock_ref): x for x in existing
                 if (x.transfer_type, x.destination_stock_ref) in group_keys}
        for group in groups:
            key = (group['transfer_type'], group['destination_stock_ref'])
            record = prior.get(key)
            if record is None and group_key is not None and group_key != key:
                continue
            if record is None:
                record = PackingSepidarTransfer.objects.create(
                    packing=packing, transfer_type=key[0],
                    source_stock_ref=group['source_stock_ref'],
                    destination_stock_ref=key[1],
                )
            if record.status in ('success', 'sending', 'unknown'):
                if saved_snapshot(record) != transfer_snapshot(group['lines']):
                    raise PackingTransferError('Previously sent transfer differs from current Packing.')
                if group_key == key:
                    raise PackingTransferError('This transfer is already registered or needs reconciliation.')
                continue  # Never automatically resend success/in-flight/unknown.
            if group_key is not None and group_key != key:
                continue  # Leave every other group untouched.
            record.lines.all().delete()
            PackingSepidarTransferItem.objects.bulk_create([
                PackingSepidarTransferItem(
                    transfer=record, packing_item_id=line['packing_item_id'],
                    item_ref=line['itemref'], quantity=line['quantity'],
                ) for line in group['lines']
            ])
            record.request_payload = SepidarDataFactory.get_wh_to_wh_data(
                packing, destination_stock_ref=key[1], lines=group['lines'],
                creator_code=getattr(request.user, 'sepidar_code', None),
            )
            record.response_payload = {}
            record.source_stock_ref = group['source_stock_ref']
            record.status = 'sending'
            record.last_error = ''
            record.attempt_count += 1
            record.save()
            to_send.append((record.pk, record.request_payload))

    for record_id, payload in to_send:
        try:
            response = SepidarApiCall.packing(packing, request, data=payload)
            status, identifiers, error = _parse_result(response)
        except Exception as exc:
            # A timeout/disconnection cannot prove Sepidar did not commit.
            status, identifiers, error = 'unknown', None, str(exc)
            response = {'uncertain': True, 'errors': error}
        with transaction.atomic():
            record = PackingSepidarTransfer.objects.select_for_update().get(pk=record_id)
            if record.status != 'sending':
                continue
            record.response_payload = response
            record.status = status
            record.last_error = error
            if identifiers:
                for name, value in identifiers.items():
                    setattr(record, name, value)
                record.sent_at = timezone.now()
            record.save()

    return [transfer_state(x) for x in PackingSepidarTransfer.objects
            .filter(packing=packing).prefetch_related('lines').order_by('destination_stock_ref', 'transfer_type')]
