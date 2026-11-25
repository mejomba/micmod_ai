"""Order/Packing bindings and read-only arrival service.

The central arrival target is completion of warehouse receipt, not warehouse
entry. A successful transfer line to central stock with a receipt and sent_at
is evidence of receipt. Other destinations and damaged stock are deliberately
not counted as central stock. No network calls or operational writes occur.
"""
from dataclasses import replace
from datetime import datetime, time
from decimal import Decimal
from django.conf import settings
from django.utils import timezone

from workflow.scheduling.configuration import calculate
from workflow.scheduling.engine import SchedulingError
from workflow.scheduling.registry import Binding, StageState, registry
from workflow.scheduling.scheduler import compile_policy
from workflow.scheduling.policies import select_policy
from .models import Order, Packing, GIOItem, PackingSepidarTransferItem
from .scheduling_rules import (
    FIELDS, ORDER_STAGES, PACKING_STAGES, ORDER_KEYS, PACKING_KEYS, KEYS,
    TARGET, POLICY_CODE, normalize_label, stage_state, transport_method,
    quantity, Shipment, summarize_shipments, residual_gio_allocations,
)


def _events(instance, as_of=None):
    if not instance.pk:
        return []
    qs = instance.get_flow()
    if as_of is not None:
        qs = qs.filter(created_date__lte=as_of)
    return list(qs.order_by('created_date', 'pk'))


def order_state(order, as_of=None):
    return stage_state(_events(order, as_of), ORDER_STAGES, 'order',
        cancelled=bool(order.cancel or order.sales_admin_cancel or order.is_deleted))


def packing_state(packing, as_of=None):
    def normalize(value):
        return normalize_label(packing.normalize_workflow_state_name(value))
    return stage_state(_events(packing, as_of), PACKING_STAGES, 'packing', normalize,
                       cancelled=bool(packing.is_deleted), created_at=packing.created_date)


def order_context(order):
    return {'has_price_inquiry': order.price_inquiry_result_id is not None,
            'production_lead_time': order.production_lead_time,
            'shipment_type': transport_method(order.transportation_method),
            'gio_weight_kg': None}


def packing_weight(packing):
    # There is no direct GIOItem -> PackingItem FK. A single active candidate
    # is usable; multiple candidates are ambiguous, never arbitrarily summed.
    ids = packing.packing_item_rel.filter(is_deleted=False, order__is_deleted=False).values_list('order_id', flat=True)
    rows = GIOItem.objects.filter(order_id__in=ids, is_deleted=False, gio__is_deleted=False).select_related('gio').order_by('gio_id')
    gios = {}
    for row in rows:
        gios[row.gio_id] = row.gio
        if len(gios) > 1:
            return None, True
    if not gios:
        return None, False
    return next(iter(gios.values())).effective_weight_kg, True


def packing_context(packing):
    weight, _ = packing_weight(packing)
    return {'shipment_type': transport_method(packing.shipment_type), 'gio_weight_kg': weight}


def register_bindings(context_registry=registry):
    for binding in (
        Binding('order', Order, order_state, order_context, FIELDS, frozenset(KEYS),
                entry_stages=frozenset((ORDER_KEYS[0],)), targets=frozenset((TARGET,))),
        Binding('packing', Packing, packing_state, packing_context, FIELDS, frozenset(PACKING_KEYS),
                entry_stages=frozenset((PACKING_KEYS[0],)), targets=frozenset((TARGET,))),
    ):
        try:
            existing = context_registry.by_key(binding.workflow_key)
        except SchedulingError:
            context_registry.register(binding)
        else:
            if existing.model is not binding.model:
                raise SchedulingError('Conflicting operational binding')


def _local_date(value):
    return timezone.make_aware(datetime.combine(value, time.min), timezone.get_default_timezone()) if value else None


def _forecast(compiled, binding, state, context, as_of, actual_gio=False):
    if state.cancelled or not state.stage or state.stage == 'packing.done':
        return None
    if actual_gio and context.get('gio_weight_kg') is None:
        # The default is only for virtual GIOs; an existing incomplete weight
        # must be fixed or overridden by the user.
        compiled = replace(compiled, unknown={**compiled.unknown,
            'gio_weight_kg': {'mode': 'MARK_INCOMPLETE'}})
    return calculate(compiled, binding, state, context, TARGET, 'exit', as_of)


def _packing_forecast(packing, compiled, binding, as_of):
    weight, candidate = packing_weight(packing)
    context = dict.fromkeys(binding.fields)
    context.update(shipment_type=transport_method(packing.shipment_type), gio_weight_kg=weight)
    return _forecast(compiled, binding, packing_state(packing, as_of), context, as_of, candidate)


def _received_lines(row, as_of):
    central = settings.SEPIDAR_CONST_DATA.get('central_wh_id')
    if not central:
        return []
    return list(PackingSepidarTransferItem.objects.filter(
        packing_item=row, transfer__packing_id=row.packing_id,
        transfer__status='success', transfer__transfer_type='normal',
        transfer__destination_stock_ref=central, transfer__receipt_id__gt=0,
        transfer__sent_at__lte=as_of,
    ).select_related('transfer').order_by('transfer__sent_at', 'pk'))


def _noncentral_receipt(row, as_of):
    central = settings.SEPIDAR_CONST_DATA.get('central_wh_id')
    return PackingSepidarTransferItem.objects.filter(
        packing_item=row, transfer__status='success', transfer__receipt_id__gt=0,
        transfer__sent_at__lte=as_of,
    ).exclude(transfer__transfer_type='normal', transfer__destination_stock_ref=central).exists()


def _packing_shipments(row, forecast, as_of):
    planned = quantity(row.quantity)
    declared = _local_date(row.packing.estimated_arrive_to_wh_date)
    remaining = planned
    shipments = []
    for line in _received_lines(row, as_of):
        # Do not silently count over-receipt as part of another shipment.
        amount = min(remaining, quantity(line.quantity))
        if amount:
            shipments.append(Shipment('receipt:%s' % line.pk, amount,
                declared=declared, actual=line.transfer.sent_at, status='actual',
                details={'packing_id': row.packing_id, 'forecast': forecast}))
            remaining -= amount
    if remaining:
        noncentral = _noncentral_receipt(row, as_of)
        calculated = forecast.estimated_at if forecast and not noncentral else None
        # A completed transfer to another warehouse is not a central receipt.
        shipments.append(Shipment('packing:%s' % row.pk, remaining, calculated,
            None if noncentral else declared, status='incomplete' if noncentral else forecast.status if forecast else 'incomplete',
            details={'packing_id': row.packing_id, 'noncentral_receipt': noncentral,
                     'declared_overdue': bool(declared and declared.date() < timezone.localdate(as_of)),
                     'forecast': forecast}))
    return shipments


def forecast_order_arrival(order, *, as_of=None, policy=None):
    """Read-only, quantity-aware ETA. No historical replay of mutable inputs."""
    as_of = as_of if as_of is not None else timezone.now()
    if timezone.is_naive(as_of):
        raise SchedulingError('Timezone-aware as_of required')
    required = quantity(order.final_quantity)
    state = order_state(order, as_of)
    if state.cancelled or order.is_wh or order.is_bazar or not state.stage:
        return {**summarize_shipments(required, []), 'status': 'cancelled' if state.cancelled else 'incomplete',
                'shipments': [], 'assumptions': [], 'in_transit_quantity': Decimal(0)}
    binding = registry.by_key('order')
    row = policy or select_policy('order', POLICY_CODE, as_of=as_of)
    if row is None:
        raise SchedulingError('No eligible order arrival policy')
    compiled = compile_policy(row, binding)
    shipments, assumptions, packed, transit = [], [], Decimal(0), Decimal(0)
    forecasts = {}
    packing_rows = order.packing_item_order.filter(is_deleted=False, packing__is_deleted=False).select_related('packing').order_by('packing_id', 'pk')
    for item in packing_rows:
        packing = item.packing
        if packing.pk not in forecasts:
            forecasts[packing.pk] = _packing_forecast(packing, compiled, binding, as_of)
        portions = _packing_shipments(item, forecasts[packing.pk], as_of)
        shipments.extend(portions)
        packed += quantity(item.quantity)
        stage = packing_state(packing, as_of).stage
        if stage in PACKING_KEYS[2:-1]:
            transit += sum((s.quantity for s in portions if not s.actual
                            and not (s.details or {}).get('noncentral_receipt')), Decimal(0))
    # Group by actual GIO (not per row) and preserve the full effective weight.
    groups = {}
    for item in order.gio_items.filter(is_deleted=False, gio__is_deleted=False).select_related('gio').order_by('gio__gio_date', 'gio_id', 'pk'):
        if item.gio_id not in groups:
            groups[item.gio_id] = [Decimal(0), item.gio]
        groups[item.gio_id][0] += quantity(item.quantity)
    gios = [(key, amount, gio.effective_weight_kg, None) for key, (amount, gio) in groups.items()]
    if packed and len(gios) > 1:
        assumptions.append('GIO/Packing allocation is not explicit; residual quantities use FIFO by GIO date and ID.')
    if packed > sum((g[1] for g in gios), Decimal(0)):
        assumptions.append('Packed quantity exceeds linked GIO quantity; reconcile allocation.')
    if sum((g[1] for g in gios), Decimal(0)) > required:
        assumptions.append('GIO quantity exceeds order quantity; reconcile allocation.')
    for key, amount, weight, entered in residual_gio_allocations(gios, packed, required):
        context = order_context(order)
        context['gio_weight_kg'] = weight
        # A saved GIO represents completed GIO allocation, but there is no
        # recorded entry into a virtual packing. Forecast from now provisionally.
        source = StageState('packing.draft', entered) if key is not None else state
        if key is not None:
            assumptions.append('GIO %s has no packing stage entry; forecast starts from now.' % key)
        forecast = _forecast(compiled, binding, source, context, as_of, key is not None)
        shipments.append(Shipment('gio:%s' % key if key else 'unallocated', amount,
            forecast.estimated_at if forecast else None, status=forecast.status if forecast else 'incomplete', details=forecast))
    result = summarize_shipments(required, shipments)
    result.update(shipments=shipments, assumptions=assumptions, in_transit_quantity=transit,
                  policy_id=row.pk)
    if packed > required or sum((g[1] for g in gios), Decimal(0)) > required:
        result.update(complete_arrival=None, status='incomplete', allocation_discrepancy=True)
    elif assumptions and result['status'] not in ('incomplete', 'actual'):
        result['status'] = 'provisional'
    return result


def forecast_packing_arrival(packing, *, as_of=None, policy=None):
    as_of = as_of if as_of is not None else timezone.now()
    binding = registry.by_key('packing')
    row = policy or select_policy('packing', POLICY_CODE, as_of=as_of)
    if row is None:
        raise SchedulingError('No eligible packing arrival policy')
    compiled = compile_policy(row, binding)
    forecast = _packing_forecast(packing, compiled, binding, as_of)
    shipments = []
    required = Decimal(0)
    for item in packing.packing_item_rel.filter(is_deleted=False).select_related('packing').order_by('pk'):
        required += quantity(item.quantity)
        shipments.extend(_packing_shipments(item, forecast, as_of))
    result = summarize_shipments(required, shipments)
    result.update(shipments=shipments, forecast=forecast, policy_id=row.pk)
    return result
