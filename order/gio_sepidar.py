"""Reliable, per-vendor/currency Sepidar document registration for Quick GIO.

The remote GIO function creates three documents in one database transaction.
A 5xx, disconnection, or malformed successful response cannot establish whether
that transaction committed; such a group must never be automatically retried.
"""
from collections import OrderedDict
from decimal import Decimal, InvalidOperation
import re

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from order.models import (GIO, GIOSepidarGroup, GIOSepidarManualReview,
                          GIOSepidarManualDocumentEntry, SepidarOrderDocument)
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


def _record_order_documents(group, rows, *, previous_invoice_id=None):
    """Sync the per-order ledger after 3 IDs are verified.

    Manual corrections replace the previous group's entry rather than leaving
    an incorrect old voucher triple alongside the newly verified one.
    """
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
        # Prefer replacing the record originally attributed to this group.
        # Do not disturb Sepidar records of other GIO groups/orders.
        index = next((
            i for i, item in enumerate(invoices)
            if isinstance(item, dict) and (
                (previous_invoice_id is not None and
                 str((item.get('purchase_invoice') or {}).get('id')) == str(previous_invoice_id))
                or str((item.get('purchase_invoice') or {}).get('id')) == str(group.invoice_id)
            )
        ), None)
        if index is None:
            invoices.append(document)
        else:
            invoices[index] = document
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
        entry = (record.manual_document_entries.select_related('actor').first()
                 if record and hasattr(record, 'manual_document_entries') else None)
        entry_display = {
            'actor': str(entry.actor),
            'at': timezone.localtime(entry.created_at).strftime('%Y-%m-%d %H:%M'),
            'reason': entry.reason,
        } if entry else None
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
            'manual_document_entry': entry_display,
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
    if 'preview_error' in statuses:
        # Never claim full registration when the current group plan is unavailable.
        return {'tone': 'warning', 'label': 'بررسی گروه‌های سپیدار لازم است'}
    if statuses and statuses == {'success'}:
        return {'tone': 'success', 'label': 'ارسال کامل به سپیدار'}
    if 'success' in statuses:
        return {'tone': 'warning', 'label': 'ارسال بخشی از گروه‌ها'}
    if (gio.sepidar_buy_factor_response_json
            or gio.sepidar_inventory_receipt_response_json):
        return {'tone': 'success', 'label': 'ارسال ثبت‌شده در سپیدار'}
    return {'tone': 'info', 'label': 'ثبت‌شده در پرتال'}


def gio_registered_group_count(recorded_statuses):
    """Count confirmed successful GIO groups, not their three Sepidar documents.

    Only durable group records count: older ungrouped document IDs cannot be
    accurately assigned to supplier/currency groups.
    """
    return sum(1 for status in (recorded_statuses or []) if status == 'success')


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


def _manual_document_identifiers(documents):
    """Validate three complete ID/number pairs (IDs stored as BIGINT)."""
    if not isinstance(documents, dict):
        raise GIOSepidarError('اطلاعات سه سند سپیدار معتبر نیست.')
    fields = {}
    for prefix, title in (
        ('invoice', 'فاکتور خرید'),
        ('receipt', 'رسید انبار'),
        ('voucher', 'سند حسابداری'),
    ):
        data = documents.get(prefix)
        if not isinstance(data, dict):
            raise GIOSepidarError('شناسه و شماره %s الزامی است.' % title)
        raw_id = data.get('id')
        if isinstance(raw_id, bool) or not isinstance(raw_id, (str, int)):
            raise GIOSepidarError('شناسه %s باید عدد صحیح مثبت باشد.' % title)
        identifier_text = str(raw_id).strip()
        if not re.fullmatch(r'[0-9]{1,19}', identifier_text):
            raise GIOSepidarError('شناسه %s باید عدد صحیح مثبت باشد.' % title)
        identifier = int(identifier_text)
        if not 0 < identifier <= 9223372036854775807:
            raise GIOSepidarError('شناسه %s خارج از محدوده مجاز است.' % title)
        number = data.get('number')
        if not isinstance(number, str):
            raise GIOSepidarError('شماره %s الزامی است.' % title)
        number = number.strip()
        if not number or len(number) > 64 or any(c in number for c in '\r\n'):
            raise GIOSepidarError('شماره %s باید بین ۱ تا ۶۴ کاراکتر باشد.' % title)
        fields[prefix + '_id'] = identifier
        fields[prefix + '_number'] = number
    return fields


def manual_save_gio_sepidar_documents(
    gio, user, *, group_key, confirmed_group, reason, documents,
    verified, overwrite_confirmed=False,
):
    """Register/correct all three Sepidar documents for one selected GIO group.

    This is a *local-only* reconciliation: no API write is made to Sepidar.
    All changes and ledger synchronization are atomic and audited.
    """
    if not (user and getattr(user, 'is_authenticated', False)
            and getattr(user, 'is_active', False)
            and getattr(user, 'is_superuser', False)):
        raise PermissionError('Only an active superuser can register documents manually.')
    if not isinstance(group_key, str) or not group_key:
        raise GIOSepidarError('گروه سپیدار مشخص نشده است.')
    if confirmed_group != group_key or verified is not True:
        raise GIOSepidarError('تأیید بررسی واقعی اسناد و کد دقیق گروه الزامی است.')
    if not isinstance(reason, str) or not 20 <= len(reason.strip()) <= 2000:
        raise GIOSepidarError('شرح بررسی باید بین ۲۰ تا ۲۰۰۰ کاراکتر باشد.')
    fields = _manual_document_identifiers(documents)

    with transaction.atomic():
        locked_gio = GIO.objects.select_for_update().get(pk=gio.pk, is_deleted=False)
        planned = plan_gio_groups(locked_gio)
        if group_key not in planned:
            raise GIOSepidarError('گروه انتخاب‌شده در GIO وجود ندارد.')

        record = GIOSepidarGroup.objects.select_for_update().filter(
            gio=locked_gio, group_key=group_key,
        ).first()
        # Do not mix the old ungrouped legacy response with new group records.
        if locked_gio.sepidar_inventory_receipt_response_json or (
            locked_gio.sepidar_buy_factor_response_json
            and not GIOSepidarGroup.objects.filter(gio=locked_gio).exists()
        ):
            raise GIOSepidarError('اسناد قدیمی فاقد گروه‌بندی قابل ثبت دستی نیستند.')

        if record and record.status == 'sending':
            raise GIOSepidarError('در حین ارسال فعال، ویرایش دستی اسناد ممنوع است.')
        if record and record.status == 'success' and overwrite_confirmed is not True:
            raise GIOSepidarError('برای اصلاح یک گروه موفق، تأیید جایگزینی اطلاعات الزامی است.')

        rows = planned[group_key]
        snapshot = snapshot_for_group(rows)
        if record and record.items_snapshot and record.items_snapshot != snapshot:
            raise GIOSepidarError('اقلام گروه نسبت به اطلاعات زمان ارسال تغییر کرده‌اند.')

        # Sepidar document IDs are global: reject reusing the same remote ID
        # in any GIO, not only a different group within this GIO.
        conflicts = GIOSepidarGroup.objects.select_for_update().filter(
            Q(invoice_id=fields['invoice_id']) |
            Q(receipt_id=fields['receipt_id']) |
            Q(voucher_id=fields['voucher_id'])
        )
        if record:
            conflicts = conflicts.exclude(pk=record.pk)
        if conflicts.exists():
            raise GIOSepidarError('حداقل یکی از شناسه‌های واردشده در GIO دیگری یا گروه دیگری ثبت شده است.')

        previous_documents = ({
            prefix: {'id': getattr(record, prefix + '_id'),
                     'number': getattr(record, prefix + '_number')}
            for prefix in ('invoice', 'receipt', 'voucher')
        } if record else {})
        previous_status = record.status if record else ''
        old_invoice_id = record.invoice_id if record else None
        if record and record.status == 'success' and all(
            getattr(record, name) == value for name, value in fields.items()
        ):
            raise GIOSepidarError('اطلاعات واردشده با مقادیر موجود یکسان است.')

        if record is None:
            record = GIOSepidarGroup(gio=locked_gio, group_key=group_key)
        record.items_snapshot = snapshot
        for name, value in fields.items():
            setattr(record, name, value)
        record.status = 'success'
        record.last_error = ''
        # sent_at is not set for manual records: remote send time is unknown.
        record.save()

        GIOSepidarManualDocumentEntry.objects.create(
            group=record, actor=user, reason=reason.strip(),
            previous_status=previous_status,
            previous_documents=previous_documents,
            new_documents={
                prefix: {'id': fields[prefix + '_id'],
                         'number': fields[prefix + '_number']}
                for prefix in ('invoice', 'receipt', 'voucher')
            },
        )
        _record_order_documents(record, rows, previous_invoice_id=old_invoice_id)

        # Keep the existing summary response in sync, including corrections
        # made to an already completed, grouped GIO.
        saved = {
            x.group_key: x for x in GIOSepidarGroup.objects.select_for_update().filter(
                gio=locked_gio,
            )
        }
        if all(key in saved and saved[key].status == 'success' for key in planned):
            GIO.objects.filter(pk=locked_gio.pk).update(sepidar_buy_factor_response_json={
                'purchase_invoice': [saved[key].invoice_id for key in planned],
                'before_central_wh_receipt': [saved[key].receipt_id for key in planned],
                'voucher': [saved[key].voucher_id for key in planned],
            })
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
