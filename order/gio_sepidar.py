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

from order.models import GIO, GIOSepidarGroup, GIOSepidarManualReview, SepidarOrderDocument
from sepidar.api_call import SepidarApiCall
from sepidar.data import SepidarDataFactory


class GIOSepidarError(ValueError):
    pass


BLOCKING_STATUSES = ('sending', 'success', 'unknown', 'reviewed')


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
        'order', 'order__currency', 'order__item', 'order__item_trade',
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


def gio_preview_groups(gio):
    """Build readable Sepidar preview from *current* portal order data.

    This never calls Sepidar and does not pretend to be an API document readback.
    Each supplier/currency group will create exactly three document types.
    """
    planned = plan_gio_groups(gio)
    saved = {group.group_key: group for group in gio.sepidar_groups.all()}
    result = []
    is_legacy = bool(
        gio.sepidar_buy_factor_response_json
        or gio.sepidar_inventory_receipt_response_json
    )
    for key, rows in planned.items():
        first = rows[0].order
        supplier = first.final_supplier
        dlref = key.split('___', 1)[0]
        supplier_label = (
            str(supplier) if supplier and str(getattr(supplier, 'dlref', '')) == dlref
            else 'تأمین‌کننده پیش‌فرض سپیدار'
        )
        currency = first.currency
        currency_label = str(currency.title_en or currency.title or currency.sepidar_id)
        record = saved.get(key)
        status = record.status if record else ('success' if is_legacy else 'pending')
        review = None
        if record and getattr(record, 'manual_reviews', None) is not None:
            review = record.manual_reviews.select_related('reviewer').first()
        review_display = {
            'reviewer': str(review.reviewer),
            'at': timezone.localtime(review.created_at).strftime('%Y-%m-%d %H:%M'),
            'reason': review.reason,
        } if review else None
        items = []
        total_quantity = Decimal('0')
        for row in rows:
            order = row.order
            final_item = order.final_item
            quantity = _quantity_text(row.quantity)
            total_quantity += Decimal(quantity)
            items.append({
                'order_id': order.pk,
                'order_number': str(order.order_number or order.pk),
                'part_number': str(getattr(final_item, 'part_number', None) or '-'),
                'sku': str(getattr(final_item, 'sku', None) or '-'),
                'quantity': quantity,
                'description': row.description or '',
            })
        result.append({
            'key': key,
            'supplier': supplier_label,
            'supplier_ref': dlref,
            'currency': currency_label,
            'currency_ref': key.split('___', 1)[1],
            'status': status,
            'can_send': not is_legacy and status in ('pending', 'failed', 'reviewed'),
            'manual_review': review_display,
            'error': record.last_error if record else '',
            'attempts': record.attempt_count if record else 0,
            'invoice': {'id': record.invoice_id, 'number': record.invoice_number} if record else {},
            'receipt': {'id': record.receipt_id, 'number': record.receipt_number} if record else {},
            'voucher': {'id': record.voucher_id, 'number': record.voucher_number} if record else {},
            'items': items,
            'row_count': len(items),
            'total_quantity': format(total_quantity.normalize(), 'f'),
        })
    return result


def gio_header_status(gio, statuses):
    """Return a visually distinct GIO status based on persisted group states."""
    if gio is None:
        return {'tone': 'draft', 'label': 'ثبت اولیه'}

    statuses = set(statuses)
    if 'unknown' in statuses:
        return {'tone': 'danger', 'label': 'نیازمند بررسی دستی سپیدار'}
    if 'failed' in statuses:
        return {'tone': 'danger', 'label': 'ارسال ناموفق به سپیدار'}
    if 'sending' in statuses:
        return {'tone': 'warning', 'label': 'در حال ارسال به سپیدار'}
    if 'reviewed' in statuses:
        return {'tone': 'warning', 'label': 'بررسی‌شده؛ آماده ارسال مجدد'}
    if statuses and statuses == {'success'}:
        return {'tone': 'success', 'label': 'ارسال کامل به سپیدار'}
    if 'success' in statuses:
        return {'tone': 'warning', 'label': 'ارسال بخشی از گروه‌ها'}
    if (gio.sepidar_buy_factor_response_json
            or gio.sepidar_inventory_receipt_response_json):
        return {'tone': 'success', 'label': 'ارسال ثبت‌شده در سپیدار'}
    return {'tone': 'info', 'label': 'ثبت‌شده در پرتال'}


def gio_registered_document_count(documents):
    """Count documented IDs, not planned groups or placeholder documents."""
    if not isinstance(documents, dict):
        return 0
    count = 0
    for name in ('purchase_invoice', 'before_central_wh_receipt', 'voucher'):
        ids = documents.get(name)
        if isinstance(ids, (list, tuple)):
            count += sum(1 for value in ids if value)
    return count


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


def approve_unknown_gio_retry(gio, user, *, group_key, confirmed_group,
                              reason, invoice_checked, receipt_checked, voucher_checked):
    """Superuser attests that all THREE remote documents are absent.

    This is an explicit, audited human override, NOT a Sepidar existence check.
    The operation is serialized with send_gio_groups using the GIO row lock.
    """
    if not (user and user.is_authenticated and user.is_active and user.is_superuser):
        raise PermissionError('Only an active superuser can approve an uncertain GIO retry.')
    if not isinstance(group_key, str) or not group_key:
        raise GIOSepidarError('A valid supplier/currency group is required.')
    if confirmed_group != group_key:
        raise GIOSepidarError('Type the exact group key to confirm the reviewed group.')
    if any(value is not True for value in (
        invoice_checked, receipt_checked, voucher_checked,
    )):
        raise GIOSepidarError('Confirm that all three Sepidar document types were checked.')
    if not isinstance(reason, str) or not (20 <= len(reason.strip()) <= 2000):
        raise GIOSepidarError('Manual review details must be between 20 and 2000 characters.')

    with transaction.atomic():
        locked_gio = GIO.objects.select_for_update().get(pk=gio.pk, is_deleted=False)
        if (locked_gio.sepidar_buy_factor_response_json
                or locked_gio.sepidar_inventory_receipt_response_json):
            raise GIOSepidarError('This GIO already has a completed/legacy Sepidar response.')
        record = GIOSepidarGroup.objects.select_for_update().filter(
            gio=locked_gio, group_key=group_key,
        ).first()
        if not record or record.status != 'unknown':
            raise GIOSepidarError('Only a currently unknown group can be manually reviewed.')
        # If ANY identifiers were recorded, do not allow an uncertain retry.
        if any((record.invoice_id, record.invoice_number, record.receipt_id,
                record.receipt_number, record.voucher_id, record.voucher_number)):
            raise GIOSepidarError(
                'Sepidar identifiers are already recorded; investigate manually instead.'
            )
        planned = plan_gio_groups(locked_gio)
        if group_key not in planned:
            raise GIOSepidarError('The reviewed group is no longer present in GIO.')
        if record.items_snapshot != snapshot_for_group(planned[group_key]):
            raise GIOSepidarError('GIO rows changed since the uncertain Sepidar request.')
        GIOSepidarManualReview.objects.create(
            group=record, reviewer=user, reason=reason.strip(),
            previous_error=record.last_error,
            previous_request_payload=record.request_payload,
            previous_response_payload=record.response_payload,
            previous_attempt_count=record.attempt_count,
            confirmations={
                'purchase_invoice_absent': True,
                'before_central_wh_receipt_absent': True,
                'voucher_absent': True,
            },
        )
        record.status = 'reviewed'
        record.save(update_fields=['status'])
        return record


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
                if old.status == 'reviewed':
                    # A manual override permits ONLY an explicitly selected group.
                    if group_key is None:
                        raise GIOSepidarError('A reviewed group requires an explicit retry group key.')
                else:
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
