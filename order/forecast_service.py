"""Operational forecast calculation and persistence entry point."""
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from workflow.scheduling.engine import SchedulingError
from workflow.scheduling.history import record_forecast
from workflow.scheduling.models import WorkflowForecast
from workflow.scheduling.policies import select_policy
from .models import Order, Packing
from .scheduling_adapters import (forecast_order_arrival, forecast_packing_arrival,
    order_state, packing_state, order_context, packing_context)
from .scheduling_rules import POLICY_CODE, TARGET, ORDER_KEYS, quantity, summarize_shipments

MODELS = {'order': Order, 'packing': Packing}


@transaction.atomic
def recalculate(workflow_key, object_id, *, reason='manual', latest_policy=False, dry_run=False):
    model = MODELS[workflow_key]
    instance = model._base_manager.select_for_update().filter(pk=object_id).first()
    if instance is None:
        # Hard deletes are not normal portal operations. Keep historical rows.
        return None, False
    as_of = timezone.now()  # after obtaining the lock; no stale queued snapshots
    ct = ContentType.objects.get_for_model(model)
    previous = WorkflowForecast.objects.filter(content_type=ct, object_id=object_id,
        target_stage=TARGET, target_event='exit', is_current=True).select_related('policy').first()
    state = order_state(instance, as_of) if workflow_key == 'order' else packing_state(instance, as_of)
    excluded = bool(workflow_key == 'order' and (instance.is_wh or instance.is_bazar))
    if not previous and (state.cancelled or excluded or not state.stage):
        return None, False
    policy = (previous.policy if previous and not latest_policy else
              select_policy(workflow_key, POLICY_CODE, as_of=as_of))
    if policy is None:
        raise SchedulingError('No eligible published arrival policy: ' + workflow_key)
    if state.cancelled or excluded or not state.stage:
        result = summarize_shipments(quantity(instance.final_quantity) if workflow_key == 'order' else 0, [])
        result.update(shipments=[], assumptions=[], status='cancelled' if state.cancelled or excluded else 'incomplete')
        context = {}
    elif workflow_key == 'order':
        result = forecast_order_arrival(instance, as_of=as_of, policy=policy)
        context = order_context(instance)
    else:
        result = forecast_packing_arrival(instance, as_of=as_of, policy=policy)
        context = packing_context(instance)
    if dry_run:
        return result, False
    # Only the genuine first trade-entry event qualifies as a contemporaneous
    # initial forecast. Existing records, delayed events and later stages are
    # never represented as forecasts actually recorded in the past.
    initial_backfill = not (workflow_key == 'order' and reason == 'trade_entry'
        and state.stage == ORDER_KEYS[0] and state.entered_at
        and timezone.localdate(state.entered_at) == timezone.localdate(as_of))
    if not initial_backfill:
        from .scheduling_adapters import _events
        from .scheduling_rules import ORDER_STAGES, stage_state
        first_entry = None
        events = _events(instance, as_of)
        # The first valid entry can be identified from the earliest prefix of
        # the real history. Skip reassignment without resetting the anchor.
        for index, event in enumerate(events):
            if event.wf_status not in (1, 2, 3, 5):
                continue
            candidate = stage_state([event], ORDER_STAGES, 'order')
            if candidate.stage == ORDER_KEYS[0]:
                first_entry = candidate.entered_at
                break
        initial_backfill = first_entry != state.entered_at
    return record_forecast(instance, policy=policy, target=TARGET, source=state.stage,
        entered_at=state.entered_at, result=result, context=context, as_of=as_of,
        reason=reason, initial_backfill=initial_backfill)
