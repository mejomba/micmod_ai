"""Authenticated preview/send endpoints for Quick Packing Sepidar transfers."""
import json

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.decorators import login_required

from order.packing_error_messages import packing_error_payload
from order.models import Packing
from order.packing_sepidar import (
    PackingTransferError, send_packing_transfers, transfer_preview,
)


def _get_authorized_packing(request, pk, sending=False):
    packing = get_object_or_404(Packing, pk=pk)
    if sending:
        states = Packing.get_flow_config(
            settings.BASE_DIR /
            '_keenthemes/view_config.json', 'PackingView'
        ).get('flow_state_list') or []
        warehouse_index = states.index('انبار') if 'انبار' in states else -1
        permitted = (
            warehouse_index >= 0
            and packing.workflow_state_index() == warehouse_index
            and packing.user_has_workflow_access(request.user)
        )
    else:
        permitted = packing.user_can_view_workflow(request.user)
    if not permitted:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied('Packing Sepidar transfer access denied.')
    return packing


@login_required
@require_GET
def packing_sepidar_preview(request, pk):
    packing = _get_authorized_packing(request, pk)
    try:
        planned = transfer_preview(packing)
    except PackingTransferError as exc:
        return JsonResponse({'error': str(exc), **packing_error_payload(exc)}, status=400)
    return JsonResponse({
        'transfers': planned,
        'all_success': all(t['status'] == 'success' for t in planned),
    })


@login_required
@require_POST
def packing_sepidar_send(request, pk):
    packing = _get_authorized_packing(request, pk, sending=True)
    try:
        # Empty body retains the old "send all pending groups" behavior.
        payload = json.loads(request.body or b'{}')
        if not isinstance(payload, dict):
            raise PackingTransferError('Invalid transfer request.')
        if 'transfer_type' in payload or 'destination_stock_ref' in payload:
            from order.packing_sepidar import normalize_transfer_selection
            group_key = normalize_transfer_selection(
                payload.get('transfer_type'), payload.get('destination_stock_ref'),
            )
            if group_key is None:
                raise PackingTransferError('Incomplete transfer group.')
        else:
            group_key = None
        send_packing_transfers(packing, request, group_key=group_key)
        # A single response contract for preview and either sending mode:
        # detailed groups first, with the existing summary built from them.
        records = transfer_preview(packing)
    except (PackingTransferError, ValueError, UnicodeDecodeError) as exc:
        return JsonResponse({'error': str(exc), **packing_error_payload(exc)}, status=400)
    return JsonResponse({
        'transfers': records,
        'all_success': all(t['status'] == 'success' for t in records),
    })
