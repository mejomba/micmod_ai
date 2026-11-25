"""Read-only presentation helpers for scheduling. No calculation or write on GET."""
from datetime import date, datetime
from django.contrib.contenttypes.models import ContentType
from django.db.models import OuterRef, Subquery, DurationField, ExpressionWrapper
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.html import format_html
from django.utils.translation import get_language
import jdatetime

from workflow.scheduling.models import WorkflowForecast, WorkflowForecastRefresh
from .scheduling_rules import TARGET, ORDER_STAGES, PACKING_STAGES, stage_state, normalize_label

SOURCES = {'actual':('رسید واقعی','Actual receipt'), 'declared':('اعلامی کاربر','Declared'),
           'calculated':('محاسباتی سیستم','Calculated'), 'none':('نامشخص','Unknown')}
STATUSES = {'estimated':('پیش‌بینی‌شده','Estimated'), 'provisional':('مشروط به فرضیات','Provisional'),
    'incomplete':('اطلاعات ناقص','Incomplete'), 'declared':('اعلامی','Declared'),
    'actual':('رسیده','Arrived'), 'cancelled':('لغوشده','Cancelled'), 'missing':('بدون پیش‌بینی','No forecast')}
STAGES = {prefix + '.' + key: label for prefix, rows in [('order',ORDER_STAGES),('packing',PACKING_STAGES)] for key,label,_ in rows}
STAGES['order.done'] = 'مرحله نهایی'
METHODS = {'air':('هوایی','Air'), 'express':('اکسپرس','Express'), 'sea':('دریایی','Sea'), 'road':('زمینی','Road'), 'rail':('ریلی','Rail')}


def is_farsi(request=None):
    cookie = getattr(request,'COOKIES',{}).get('portal_scheduling_language') if request is not None else None
    language = cookie if cookie in ('fa','en') else getattr(request,'LANGUAGE_CODE',None) or get_language() or 'en'
    return language.startswith('fa')


def label(mapping, key, fa):
    if key is None:
        return '—'
    return mapping.get(key,(key,key))[0 if fa else 1]


def display_date(value, fa):
    if isinstance(value,str):
        try:
            value = parse_datetime(value) or parse_date(value)
        except ValueError:
            value = None
    if isinstance(value,datetime):
        value = timezone.localdate(value) if timezone.is_aware(value) else value.date()
    if not isinstance(value,date):
        return '—'
    return jdatetime.date.fromgregorian(date=value).strftime('%Y/%m/%d') if fa else value.isoformat()


def display_datetime(value,fa):
    if value is None:
        return '—'
    local = timezone.localtime(value) if timezone.is_aware(value) else value
    return display_date(local,fa) + ' ' + local.strftime('%H:%M:%S')


def current_queryset(model):
    return WorkflowForecast.objects.filter(content_type=ContentType.objects.get_for_model(model),
        target_stage=TARGET,target_event='exit',is_current=True)


def annotate_order_forecasts(qs):
    latest = current_queryset(qs.model).filter(object_id=OuterRef('pk')).order_by('-revision')
    qs = qs.annotate(
        estimated_arrive_date=Subquery(latest.values('effective_estimated_at')[:1]),
        forecast_initial_at=Subquery(latest.values('initial_estimated_at')[:1]),
        forecast_source_code=Subquery(latest.values('forecast_source')[:1]),
        forecast_status_code=Subquery(latest.values('forecast_status')[:1]))
    return qs.annotate(forecast_delay=ExpressionWrapper(
        TruncDate('estimated_arrive_date') - TruncDate('forecast_initial_at'), output_field=DurationField()))


def filter_order_forecasts(qs, data):
    status = data.get('forecast_status')
    if status == 'missing':
        qs = qs.filter(forecast_status_code__isnull=True)
    elif status in STATUSES:
        qs = qs.filter(forecast_status_code=status)
    for key, lookup in [('forecast_from','estimated_arrive_date__date__gte'),('forecast_to','estimated_arrive_date__date__lte')]:
        raw = data.get(key)
        if raw:
            try:
                value = parse_date(raw)
            except (TypeError,ValueError):
                value = None
            if value:
                qs = qs.filter(**{lookup:value})
    return qs


def order_forecast_cells(obj, fa):
    # Deliberately no fallback DB query: mocks and unrelated list views remain safe.
    date_ = getattr(obj,'estimated_arrive_date',None)
    status = getattr(obj,'forecast_status_code',None) or 'missing'
    source = getattr(obj,'forecast_source_code',None) or 'none'
    delay = getattr(obj,'forecast_delay',None)
    return {
        'estimated_arrive_date': display_date(date_,fa),
        'forecast_status_code': label(STATUSES,status,fa),
        'forecast_source_code': label(SOURCES,source,fa),
        'forecast_delay': format_html('<span class="{}" dir="ltr">{}</span>',
            'text-danger fw-bold' if delay and delay.days > 0 else 'text-muted',
            '%+d' % delay.days) if delay is not None else '—',
    }


def _stage_name(value, fa):
    return STAGES.get(value,value) if fa else value


def _date_delta(later, earlier):
    if not later or not earlier:
        return None
    return (timezone.localdate(later)-timezone.localdate(earlier)).days


def _actual_stages(instance, kind, fa):
    rows = ORDER_STAGES + (('done','مرحله نهایی',0),) if kind=='order' else PACKING_STAGES
    normalize = normalize_label if kind=='order' else lambda v: normalize_label(instance.normalize_workflow_state_name(v))
    visits = []
    for event in instance.get_flow().order_by('created_date','pk'):
        if event.wf_status not in (1,2,3,5):
            continue
        state = stage_state([event],rows,kind,normalize)
        if not state.stage or not state.entered_at:
            continue
        if visits and visits[-1]['key']==state.stage:
            continue
        if visits:
            visits[-1]['exit']=state.entered_at
        visits.append({'key':state.stage,'stage':_stage_name(state.stage,fa),'entry':state.entered_at,'exit':None})
    for v in visits:
        v['days']=0 if v['key'] in ('order.done','packing.done') else _date_delta(v['exit'] or timezone.now(),v['entry'])
        v['entry']=display_date(v['entry'],fa)
        v['exit']=display_date(v['exit'],fa)
    return visits


def revision_summary(row, fa):
    result = row.context_snapshot.get('result',{}) or {}
    return {'revision':row.revision,'version':row.policy_version,
        'recorded':display_datetime(row.calculated_at,fa),
        'effective':display_date(row.effective_estimated_at,fa),
        'status':label(STATUSES,row.forecast_status,fa),
        'source':label(SOURCES,row.forecast_source,fa),'reason':row.calculation_reason,
        'delta':_date_delta(row.effective_estimated_at,row.initial_estimated_at),
        'first':display_date(result.get('first_arrival'),fa)}


def panel_context(instance, kind, user, fa, *, revision=None):
    result = {'show':False,'fa':fa,'kind':kind}
    if not instance or not getattr(instance,'pk',None):
        return result
    from .models import Order,Packing
    model = Order if kind=='order' else Packing
    if not isinstance(instance,model):
        return result
    if kind=='order' and (instance.is_wh or instance.is_bazar):
        return result
    result['show']=True
    if revision is not None:
        if not user.has_perm('workflow.view_workflowforecast') or revision.object_id != instance.pk or revision.content_type_id != ContentType.objects.get_for_model(model).pk or revision.target_stage != TARGET or revision.target_event != 'exit':
            return {'show':False,'fa':fa,'kind':kind}
        current,job = revision,None
    else:
        current = current_queryset(model).filter(object_id=instance.pk).select_related('policy').first()
        job = WorkflowForecastRefresh.objects.filter(workflow_key=kind,object_id=instance.pk).only('attempts','requested_at').first()
    result.update(current=current,pending=bool(job),retrying=bool(job and job.attempts),
                  can_history=user.has_perm('workflow.view_workflowforecast'),object_id=instance.pk,historical=revision is not None)
    if not current:
        return result
    snapshot = current.context_snapshot.get('result',{}) or {}
    document = current.context_snapshot.get('document',{}) or {}
    method = document.get('shipment_type')
    result.update(summary=revision_summary(current,fa), initial=display_date(current.initial_estimated_at,fa),
        calculated=display_date(current.calculated_estimated_at,fa), declared=display_date(current.declared_at,fa),
        actual=display_date(current.actual_at,fa), backfill=current.initial_is_backfill,
        first=display_date(snapshot.get('first_arrival'),fa), method=label(METHODS,method,fa),
        delta=_date_delta(current.effective_estimated_at,current.initial_estimated_at),
        declared_delta=_date_delta(current.declared_at,current.calculated_estimated_at),
        assumption_count=len(current.assumptions),received=snapshot.get('received_quantity'),
        remaining=snapshot.get('remaining_quantity'),transit=snapshot.get('in_transit_quantity'),
        overdue=(current.actual_at is None and current.forecast_status not in ('cancelled','incomplete')
            and current.effective_estimated_at is not None and timezone.localdate(current.effective_estimated_at)<timezone.localdate()))
    if result['can_history']:
        shipments=[]
        for row in snapshot.get('shipments',[]):
            effective = row.get('actual') or row.get('declared') or row.get('calculated')
            source = 'actual' if row.get('actual') else 'declared' if row.get('declared') else 'calculated' if row.get('calculated') else 'none'
            shipments.append({'key':row.get('key'),'quantity':row.get('quantity'),
                'calculated':display_date(row.get('calculated'),fa),'declared':display_date(row.get('declared'),fa),
                'actual':display_date(row.get('actual'),fa),'effective':display_date(effective,fa),
                'source':label(SOURCES,source,fa),'status':label(STATUSES,row.get('status'),fa)})
        rules={}
        for timing in current.policy_snapshot.get('stages',[]):
            rules.update({str(r['id']):r['name'] for r in timing.get('rules',[])})
        steps=[]
        for step in current.steps.all():
            steps.append({'stage':_stage_name(step.workflow_key+'.'+step.stage_key,fa),
                'start':display_date(step.estimated_start_at,fa),'end':display_date(step.estimated_end_at,fa),
                'duration':step.standard_duration,'elapsed':step.elapsed_duration,'remaining':step.remaining_duration,
                'shipment':step.calculation_details.get('shipment'),'scenario':step.calculation_details.get('scenario',0)+1,
                'route':step.calculation_details.get('route',0)+1,
                'rules':', '.join(rules.get(str(r),str(r)) for r in step.applied_rules),
                'components':step.duration_components,'overdue':step.status=='overdue'})
        result.update(shipments=shipments,steps=steps,assumptions=current.assumptions,
                      calendars=current.policy_snapshot.get('calendars',[]),
                      actual_stages=[] if revision is not None else _actual_stages(instance,kind,fa))
    return result
