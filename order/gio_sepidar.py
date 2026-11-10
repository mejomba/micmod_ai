"""Reliable, per-vendor/currency Sepidar document registration for Quick GIO.

The remote GIO function creates three documents in one database transaction.
A 5xx, disconnection, or malformed successful response cannot establish whether
that transaction committed; such a group must never be automatically retried.
"""
from collections import OrderedDict
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from order.models import GIO, GIOSepidarGroup, SepidarOrderDocument
from sepidar.api_call import SepidarApiCall
from sepidar.data import SepidarDataFactory


class GIOSepidarError(ValueError):
    pass


BLOCKING_STATUSES = ('sending', 'success', 'unknown')


def user_can_send_gio(user):
    """Match the existing template's has_group('mac') semantics exactly."""
    return bool(
        user and user.is_authenticated and not user.is_superuser
        and not user.groups.filter(name='mac').exists()
    )


def gio_is_locked(gio):
    if gio is None or gio.pk is None:
        return False
    return bool(
        gio.sepidar_buy_factor_response_json
        or gio.sepidar_inventory_receipt_response_json
        or gio.sepidar_groups.filter(status__in=BLOCKING_STATUSES).exists()
    )


def _fallback_currency_name(currency):
    name = ('%s %s' % (currency.title_en or '', currency.title or '')).lower()
    for token, code in (
        ('rmb', 'rmb'), ('یوآن', 'rmb'), ('yuan', 'rmb'),
        ('ero', 'ero'), ('euro', 'ero'), ('یورو', 'ero'),
        ('usd', 'usd'), ('dollar', 'usd'), ('دلار', 'usd'),
        ('dirham', 'aed'), ('درهم', 'aed'),
    ):
        if token in name:
            return code
    return None


def _quantity_text(value):
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise GIOSepidarError('Invalid GIO item quantity.')
    if not quantity.is_finite() or quantity <= 0:
        raise GIOSepidarError('GIO quantities must be positive and finite.')
    return format(quantity.normalize(), 'f')


def plan_gio_groups(gio):
    """Keep the current supplier/currency rule, but reject incomplete input."""
    groups = OrderedDict()
    items = gio.gioitems.filter(is_deleted=False).select_related(
        'order', 'order__currency', 'order__item',
    ).order_by('pk')
    for row in items:
        order = row.order
        if not order or not order.currency or not order.item:
            raise GIOSepidarError('Every GIO row needs an order, currency and item.')
        _quantity_text(row.quantity)
        itemref = getattr(order.item, 'sepidar_id_0', None)
        if not itemref:
            raise GIOSepidarError('An order item has no Sepidar item code.')
        currency = str(order.currency.sepidar_id or '')
        if not currency:
            raise GIOSepidarError('An order currency has no Sepidar currency ID.')
        supplier = order.final_supplier
        vendor = getattr(supplier, 'dlref', None)
        if not vendor:
            code = _fallback_currency_name(order.currency)
            vendor = settings.SEPIDAR_CONST_DATA.get('no_name_vendor_%s' % code) if code else None
        if not vendor:
            raise GIOSepidarError('Supplier is missing a Sepidar DL and no currency fallback is configured.')
        group_key = '%s___%s' % (vendor, currency)
        groups.setdefault(group_key, []).append(row)
    if not groups:
        raise GIOSepidarError('GIO has no active rows to send.')
    return OrderedDict(sorted(groups.items()))


def snapshot_for_group(rows):
    """Stable mapping of exactly the items and values used for this group."""
    return [
        {
            'gio_item_id': row.pk,
            'order_id': row.order_id,
            'quantity': _quantity_text(row.quantity),
            'itemref': str(row.order.item.sepidar_id_0),
            'price': str(row.order.final_price or 0),
            'discount': str(row.order.final_discount or 0),
            'addition': str(row.order.final_addition or 0),
        }
        for row in rows
    ]


def parse_gio_response(response, group_key):
    """Return (status, document identifiers or None, error)."""
    if not isinstance(response, dict):
        return 'unknown', None, 'Invalid Sepidar response; manual reconciliation required.'
    if response.get('errors'):
        return (
            'unknown' if response.get('uncertain') else 'failed',
            None, str(response['errors']),
        )
    try:
        if set(response) != {group_key}:
            raise ValueError('Unexpected supplier/currency group in Sepidar response.')
        documents = response[group_key]['gio']['sepidar']
        if not isinstance(documents, list) or len(documents) != 1:
            raise ValueError('Expected exactly one group of three Sepidar documents.')
        document = documents[0]
        fields = {}
        for name, prefix in (
            ('purchase_invoice', 'invoice'),
            ('before_central_wh_receipt', 'receipt'),
            ('voucher', 'voucher'),
        ):
            value = document[name]
            identifier = int(value['id'])
            number = str(value['number']).strip()
            if identifier <= 0 or not number:
                raise ValueError('Empty or invalid document identifiers.')
            fields[prefix + '_id'] = identifier
            fields[prefix + '_number'] = number
        return 'success', fields, ''
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        return 'unknown', None, 'Incomplete Sepidar response (%s); reconcile manually.' % exc


def _document_value(group):
    return {
        'purchase_invoice': {'id': group.invoice_id, 'number': group.invoice_number},
        'before_central_wh_receipt': {'id': group.receipt_id, 'number': group.receipt_number},
        'voucher': {'id': group.voucher_id, 'number': group.voucher_number},
    }


def _record_order_documents(group, rows):
    """Update the legacy per-order ledger only after all 3 IDs are verified."""
    document = _document_value(group)
    for order_id in sorted({row.order_id for row in rows}):
        existing, _ = SepidarOrderDocument.objects.select_for_update().get_or_create(
            order_id=order_id, defaults={'data': {}},
        )
        data = dict(existing.data or {})
        gio_data = data.get('gio') or {}
        if not isinstance(gio_data, dict):
            raise GIOSepidarError('Unexpected legacy order document format.')
        invoices = list(gio_data.get('sepidar') or [])
        if not any(
            str((item.get('purchase_invoice') or {}).get('id')) == str(group.invoice_id)
            for item in invoices if isinstance(item, dict)
        ):
            invoices.append(document)
        gio_data['sepidar'] = invoices
        data['gio'] = gio_data
        existing.data = data
        existing.save(update_fields=['data'])


def group_states(gio):
    return [
        {
            'key': group.group_key,
            'status': group.status,
            'purchase_invoice': group.invoice_id,
            'before_central_wh_receipt': group.receipt_id,
            'voucher': group.voucher_id,
            'error': group.last_error,
        }
        for group in gio.sepidar_groups.order_by('group_key')
    ]


def gio_document_display(gio):
    """Feed the existing three-column Quick GIO display without changing CSS."""
    legacy = gio.sepidar_buy_factor_response_json
    if legacy:
        return legacy
    groups = gio.sepidar_groups.filter(status='success').order_by('group_key')
    return {
        'purchase_invoice': [g.invoice_id for g in groups],
        'before_central_wh_receipt': [g.receipt_id for g in groups],
        'voucher': [g.voucher_id for g in groups],
    }


def _finalize_group(gio_id, group_id, response, status, identifiers, error, rows):
    try:
        with transaction.atomic():
            group = GIOSepidarGroup.objects.select_for_update().get(pk=group_id)
            if group.status != 'sending':
                return
            group.response_payload = response if isinstance(response, dict) else {'raw': str(response)}
            group.status = status
            group.last_error = error
            if identifiers:
                for field, value in identifiers.items():
                    setattr(group, field, value)
                group.sent_at = timezone.now()
            group.save()
            if status == 'success':
                _record_order_documents(group, rows)
    except Exception as exc:
        # Sepidar may already have committed: never retry on a local DB failure.
        GIOSepidarGroup.objects.filter(pk=group_id, status='sending').update(
            status='unknown', last_error='Local recording failed: %s' % exc,
            response_payload=response if isinstance(response, dict) else {'raw': str(response)},
        )


def send_gio_groups(gio, request, *, group_key=None):
    """Reserve before I/O, send one vendor/currency at a time, persist each result."""
    work = []
    with transaction.atomic():
        gio = GIO.objects.select_for_update().get(pk=gio.pk)
        if gio.sepidar_buy_factor_response_json or gio.sepidar_inventory_receipt_response_json:
            raise GIOSepidarError('Legacy/finished GIO is already registered in Sepidar.')
        planned = plan_gio_groups(gio)
        if group_key is not None and group_key not in planned:
            raise GIOSepidarError('Requested vendor/currency group does not exist.')
        records = {
            x.group_key: x for x in GIOSepidarGroup.objects.select_for_update().filter(gio=gio)
        }
        for old_key, old in records.items():
            if old_key not in planned and old.status in BLOCKING_STATUSES:
                raise GIOSepidarError('An already sent GIO group is no longer in the current rows.')
        prepared = []
        for key, rows in planned.items():
            snapshot = snapshot_for_group(rows)
            old = records.get(key)
            if old and old.status in BLOCKING_STATUSES:
                if old.items_snapshot != snapshot:
                    raise GIOSepidarError('An already sent or uncertain group differs from current rows.')
                if group_key == key:
                    raise GIOSepidarError('This group has been sent or requires manual reconciliation.')
                continue
            if group_key is not None and group_key != key:
                continue
            # Prepare every eligible request before marking any group as sending.
            payload = SepidarDataFactory.get_trade_inventory_purchase_invoice_data(
                key, rows, request=request,
            )
            if not isinstance(payload, dict) or not payload.get('inventorypurchaseinvoice_item'):
                raise GIOSepidarError('Cannot prepare a valid purchase invoice for Sepidar.')
            prepared.append((key, rows, snapshot, payload, old))
        for key, rows, snapshot, payload, old in prepared:
            group = old or GIOSepidarGroup(gio=gio, group_key=key)
            group.request_payload = payload
            group.items_snapshot = snapshot
            group.response_payload = {}
            group.status = 'sending'
            group.last_error = ''
            group.attempt_count += 1
            group.save()
            work.append((group.pk, key, rows, payload))

    for group_id, key, rows, payload in work:
        try:
            # The existing Sepidar function accepts a one-element buy_factor_list.
            response = SepidarApiCall.gio_to_sepidar(
                request=request, buy_factor_list=[payload],
            )
            status, identifiers, error = parse_gio_response(response, key)
        except Exception as exc:
            response = {'errors': str(exc), 'uncertain': True}
            status, identifiers, error = 'unknown', None, str(exc)
        _finalize_group(gio.pk, group_id, response, status, identifiers, error, rows)

    with transaction.atomic():
        gio = GIO.objects.select_for_update().get(pk=gio.pk)
        planned = plan_gio_groups(gio)
        records = {
            x.group_key: x for x in GIOSepidarGroup.objects.select_for_update().filter(gio=gio)
        }
        if planned and all(
            key in records and records[key].status == 'success'
            for key in planned
        ):
            # Preserve the response contract expected by the existing UI.
            GIO.objects.filter(pk=gio.pk).update(sepidar_buy_factor_response_json={
                'purchase_invoice': [records[k].invoice_id for k in planned],
                'before_central_wh_receipt': [records[k].receipt_id for k in planned],
                'voucher': [records[k].voucher_id for k in planned],
            })
    return group_states(gio)
