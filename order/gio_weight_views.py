"""Dedicated weight metadata endpoint; never invokes Sepidar."""
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .gio_sepidar import gio_is_locked
from .gio_weight import parse_manual_weight
from .models import GIO


def can_change_gio_weight(user, gio):
    if gio is None or not user.is_authenticated or not user.is_active:
        return False
    return bool(user.has_perm('order.change_gio') and
                GIO.objects.get_access_object(user).filter(pk=gio.pk).exists())


def _number(value):
    return format(value, 'f') if value is not None else None


@login_required
@require_POST
@transaction.atomic
def update_gio_weight(request, pk):
    if not request.user.is_active or not request.user.has_perm('order.change_gio'):
        return JsonResponse({'error': 'forbidden'}, status=403)
    gio = GIO.objects.select_for_update().filter(pk=pk).first()
    if gio is None or not can_change_gio_weight(request.user, gio):
        return JsonResponse({'error': 'not_found'}, status=404)
    if gio_is_locked(gio):
        return JsonResponse({'error': 'locked'}, status=409)
    action = request.POST.get('action')
    try:
        if action == 'manual':
            manual = parse_manual_weight(request.POST.get('weight'))
        elif action == 'automatic':
            manual = None
        else:
            raise ValueError('invalid_weight')
    except ValueError:
        return JsonResponse({'error': 'invalid_weight'}, status=400)
    # Update only the scheduling metadata; preserve every Sepidar payload.
    if gio.manual_weight_kg != manual:
        GIO.objects.filter(pk=gio.pk).update(manual_weight_kg=manual)
        gio.manual_weight_kg = manual
    summary = gio.get_weight_summary()
    return JsonResponse({
        'calculated': _number(summary.calculated_weight_kg),
        'effective': _number(summary.effective_weight_kg),
        'known': _number(summary.known_weight_kg),
        'manual': _number(summary.manual_weight_kg),
        'overridden': summary.is_overridden,
        'missing_count': len(summary.missing_row_ids),
        'row_count': summary.row_count,
    })
