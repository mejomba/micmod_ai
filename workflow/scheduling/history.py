"""Append-only forecast history. Callers lock the document before calculation.

The only mutation to an existing revision is clearing is_current. Results are
day-based; the fingerprint excludes intraday jitter in calculated timestamps.
"""
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from .history_values import arrival_dates, fingerprint, json_value
from .models import WorkflowForecast, WorkflowForecastStep, WorkflowForecastAnchor


def policy_snapshot(policy):
    calendars = []
    for calendar in policy.calendars.prefetch_related('exceptions').order_by('code'):
        calendars.append(dict(code=calendar.code, timezone=calendar.timezone,
            weekdays=calendar.working_weekdays, active=calendar.is_active,
            exceptions=[dict(date=e.date, working=e.is_working_day, description=e.description)
                        for e in sorted(calendar.exceptions.all(), key=lambda e: e.date)]))
    stages = []
    for timing in policy.stage_timings.select_related('calendar').prefetch_related('rules').order_by('workflow_key', 'stage_key'):
        stages.append(dict(workflow=timing.workflow_key, stage=timing.stage_key,
            duration=timing.default_duration, unit=timing.duration_unit,
            calendar=timing.calendar.code, strategy=timing.remaining_time_strategy,
            overdue=timing.overdue_duration, active=timing.is_active,
            rules=[dict(id=r.pk, name=r.name, condition=r.condition_json, effect=r.effect_json,
                        priority=r.priority, active=r.is_active)
                   for r in sorted(timing.rules.all(), key=lambda r: r.pk)]))
    transitions = list(policy.transitions.order_by('pk').values(
        'source_workflow', 'source_stage', 'target_workflow', 'target_stage',
        'condition_json', 'priority', 'is_active'))
    return dict(id=policy.pk, workflow=policy.workflow_key, code=policy.code, version=policy.version,
                unknown=policy.unknown_policies, route_mode=policy.route_mode,
                calendars=calendars, stages=stages, transitions=transitions)


def _details(result):
    for shipment in result['shipments']:
        details = shipment.details
        forecast = details.get('forecast') if isinstance(details, dict) else details
        if forecast is None:
            continue
        for scenario_index, scenario in enumerate(forecast.scenarios):
            for route_index, (_, steps) in enumerate(scenario.routes):
                for step in steps:
                    yield shipment, scenario_index, scenario, route_index, step


def _write_details(revision, result, entered_at):
    calendar_ids = dict(revision.policy.calendars.values_list('code', 'pk'))
    rows = []
    for sequence, (shipment, scenario_index, scenario, route_index, step) in enumerate(_details(result), 1):
        workflow, stage = step.stage.split('.', 1)
        standard = sum(c.duration for c in step.components)
        remaining = sum(c.duration for c in step.remaining)
        standard_remaining = sum(c.duration for c in step.remaining[:len(step.components)])
        codes = {c.calendar for c in step.components}
        direct_entry = entered_at if (step.stage == revision.source_stage and
            shipment.key == 'unallocated' and route_index >= 0) else None
        rows.append(WorkflowForecastStep(
            forecast=revision, sequence=sequence, workflow_key=workflow, stage_key=stage,
            estimated_start_at=step.start, estimated_end_at=step.end,
            actual_start_at=direct_entry,
            standard_duration=standard, elapsed_duration=max(0, standard - standard_remaining),
            remaining_duration=remaining,
            calendar_id=calendar_ids.get(next(iter(codes))) if len(codes) == 1 else None,
            duration_components=json_value([{'standard': step.components, 'remaining': step.remaining}]),
            applied_rules=list(scenario.applied_rules.get(step.stage, ())),
            assumptions=json_value(scenario.assumptions), status='overdue' if step.overdue else 'estimated',
            calculation_details={'shipment': shipment.key, 'scenario': scenario_index, 'route': route_index},
        ))
    WorkflowForecastStep.objects.bulk_create(rows, batch_size=500)
    anchors = []
    if entered_at:
        anchors.append(WorkflowForecastAnchor(forecast=revision, stage_key=revision.source_stage,
            target_event='entry', anchor_type='actual', anchor_datetime=entered_at,
            source_content_type_id=revision.content_type_id, source_object_id=revision.object_id,
            description='Current stage entry'))
    for shipment in result['shipments']:
        for kind, value in (('calculated', shipment.calculated), ('declared', shipment.declared), ('actual', shipment.actual)):
            if value:
                anchors.append(WorkflowForecastAnchor(forecast=revision, stage_key=revision.target_stage,
                    target_event=revision.target_event, anchor_type=kind, anchor_datetime=value,
                    description=shipment.key))
    WorkflowForecastAnchor.objects.bulk_create(anchors, batch_size=500)


@transaction.atomic
def record_forecast(instance, *, policy, target, source, entered_at, result,
                    context, as_of, reason, initial_backfill=True):
    # Also acquire the parent lock here for callers using this generic API.
    # Operational callers must acquire it BEFORE reading inputs as well.
    type(instance)._base_manager.select_for_update().get(pk=instance.pk)
    ct = ContentType.objects.get_for_model(instance)
    history = WorkflowForecast.objects.filter(content_type=ct, object_id=instance.pk,
                                             target_stage=target, target_event='exit')
    previous = history.select_for_update().filter(is_current=True).first()
    if previous and previous.as_of > as_of:
        return previous, False
    dates = arrival_dates(result)
    status = dates['forecast_status']
    if status == 'actual' and previous:
        dates['calculated_estimated_at'] = previous.calculated_estimated_at
        dates['declared_at'] = previous.declared_at
    if status == 'actual':
        # Retain a real declaration even when the first calculation is made
        # after receipt. Per-shipment dates remain independently in snapshot.
        declarations = [s.declared for s in result['shipments'] if s.quantity > 0]
        if declarations and all(declarations):
            dates['declared_at'] = max(declarations)
    effective = dates['actual_at'] or dates['declared_at'] or dates['calculated_estimated_at']
    forecast_source = ('actual' if dates['actual_at'] else 'declared' if dates['declared_at']
                       else 'calculated' if dates['calculated_estimated_at'] else 'none')
    assumptions = list(result.get('assumptions', []))
    for shipment in result['shipments']:
        details = shipment.details
        f = details.get('forecast') if isinstance(details, dict) else details
        if f:
            for scenario in f.scenarios:
                for assumption in scenario.assumptions:
                    assumptions.append({'shipment': shipment.key, **assumption})
    snapshot = {'document': context, 'entered_at': entered_at, 'result': result}
    configuration = policy_snapshot(policy)
    signature = fingerprint(dict(source=source, dates=dates, context=snapshot,
                                 assumptions=assumptions, policy=configuration, engine='2'),
                            timezone.get_default_timezone())
    if previous and previous.fingerprint == signature:
        return previous, False
    initial = previous.initial_estimated_at if previous else None
    backfill = previous.initial_is_backfill if previous else False
    if initial is None and effective is not None and status != 'actual':
        initial, backfill = effective, initial_backfill
    latest = history.order_by('-revision').values_list('revision', flat=True).first() or 0
    revision = WorkflowForecast(
        content_type=ct, object_id=instance.pk, policy=policy, policy_version=policy.version,
        revision=latest + 1, source_stage=source or 'unknown', target_stage=target, target_event='exit',
        as_of=as_of, initial_estimated_at=initial, initial_is_backfill=backfill,
        effective_estimated_at=effective, forecast_source=forecast_source,
        context_snapshot=json_value(snapshot), assumptions=json_value(assumptions),
        policy_snapshot=json_value(configuration), calculation_reason=reason[:100],
        calculation_version='2', fingerprint=signature, **dates)
    # The conditional uniqueness check is performed by the database after
    # clearing the old current marker, all in this atomic transaction.
    revision.clean()
    if previous:
        history.filter(pk=previous.pk).update(is_current=False)
    revision.save(force_insert=True)
    from .write_scope import scheduling_write_scope
    with scheduling_write_scope('detail_revision', revision.pk):
        _write_details(revision, result, entered_at)
    return revision, True
