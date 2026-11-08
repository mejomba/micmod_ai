"""Read-only Packing shipping overview built from actual workflow transitions.

Estimates belong to Packing; confirmed milestones are derived exclusively from
WorkFlow records, never from editable Packing date fields.
"""
from collections import defaultdict
from datetime import date

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.shortcuts import render
from django.utils import timezone
from django.views import View

from order.models import Order, Packing, PackingItem
from order.packing_carton_report import build_carton_report, carton_key
from workflow.models import WorkFlow


STAGES = (
    'پیش‌نویس', 'تحویل شرکت حمل', 'حمل', 'قبض انبار', 'تحویل اسناد',
    'اظهار', 'ضمانتنامه', 'ترخیص', 'انبار', 'اتمام کار',
)
MILESTONES = {
    'حمل': 'actual_start',
    'انبار': 'actual_arrival',
}
GLOBAL_VIEW_GROUPS = ('packing_viewer', 'packing_finance_viewer')
SHIPMENT_LABELS = {'sea': 'دریایی', 'air': 'هوایی', 'express': 'اکسپرس'}


def workflow_destination(event):
    """Get the effective destination, including legacy events without a target."""
    target = Packing.normalize_workflow_state_name(event.current_state_name)
    if target in STAGES:
        return target
    source = Packing.normalize_workflow_state_name(event.state)
    if source not in STAGES:
        return None
    index = STAGES.index(source)
    if event.wf_status == 3:
        # Historical declarations could skip the later-added guarantee stage.
        if event.state == 'اظهار گمرکی':
            return 'ترخیص'
        return STAGES[min(index + 1, len(STAGES) - 1)]
    if event.wf_status == 2:
        if event.state == 'ترخیص گمرک':
            return 'اظهار'
        return STAGES[max(index - 1, 0)]
    return source


def confirmed_milestones(events):
    """Latest *forward entry* into shipping/warehouse, ignoring reassignment.

    Using wf_status=3 and actual destination also avoids misinterpreting
    the source step (event.state) as the step newly entered.
    """
    actual = {'actual_start': None, 'actual_arrival': None}
    for event in events:
        if event.wf_status != 3 or not event.created_date:
            continue
        destination = workflow_destination(event)
        key = MILESTONES.get(destination)
        if key:
            actual[key] = timezone.localtime(event.created_date).date()
    return actual


def current_workflow_stage(events):
    if not events:
        return STAGES[0]
    return workflow_destination(events[-1]) or STAGES[0]


def delay_information(planned_start, planned_arrival, actual_start,
                      actual_arrival, today):
    """Positive delays only; zero means on time, None means no comparable plan."""
    def delta(planned, actual):
        if not planned:
            return None
        comparable_date = actual or today
        return max(0, (comparable_date - planned).days)

    start = delta(planned_start, actual_start)
    arrival = delta(planned_arrival, actual_arrival)
    # Past due dates without a recorded milestone are actionable delays.
    return {
        'start_delay': start,
        'arrival_delay': arrival,
        'is_delayed': bool(start or arrival),
    }


def build_schedule_row(packing, events, today):
    actual = confirmed_milestones(events)
    planned_start = packing.estimated_shipping_start_date
    planned_arrival = packing.estimated_arrive_to_wh_date
    actual_start = actual['actual_start']
    actual_arrival = actual['actual_arrival']
    delay = delay_information(
        planned_start, planned_arrival, actual_start, actual_arrival, today,
    )

    stage = current_workflow_stage(events)
    # The actual milestones are historical facts even if a workflow is
    # subsequently returned to an earlier step.
    if actual_arrival:
        status = 'arrived'
        status_label = 'رسیده به انبار'
    elif actual_start:
        status = 'in_transit'
        status_label = 'در مسیر'
    else:
        status = 'planned'
        status_label = 'در انتظار حمل'

    orders = {}
    quantity = 0
    for item in packing.active_schedule_items:
        order = item.order
        amount = item.quantity or 0
        quantity += amount
        key = order.pk if order else 'unlinked-' + str(item.pk)
        if key not in orders:
            original_item = (order.item_trade or order.item) if order else None
            orders[key] = {
                'number': (order.order_number or str(order.pk)) if order else '—',
                'part_number': (
                    item.part_number
                    or (original_item.part_number if original_item else None)
                    or '—'
                ),
                'quantity': 0,
            }
        orders[key]['quantity'] += amount

    return {
        'id': packing.pk,
        'number': packing.packing_number or str(packing.pk),
        'bl_number': packing.bl_number or '—',
        'shipment_type': SHIPMENT_LABELS.get(
            packing.shipment_type, packing.shipment_type or '—',
        ),
        'transportation_company': packing.transportation_company or '—',
        'origin': packing.origin or '—',
        'destination': packing.destination or '—',
        'stage': stage,
        'status': status,
        'status_label': status_label,
        'planned_start': planned_start,
        'planned_arrival': planned_arrival,
        'actual_start': actual_start,
        'actual_arrival': actual_arrival,
        'start_delay': delay['start_delay'],
        'arrival_delay': delay['arrival_delay'],
        'is_delayed': delay['is_delayed'],
        'unscheduled': not (planned_start and planned_arrival),
        'orders': list(orders.values()),
        'order_count': len(orders),
        'total_quantity': quantity,
        'unique_carton_count': len({
            carton_key(item.carton_number)
            for item in packing.active_schedule_items
            if carton_key(getattr(item, 'carton_number', None))
        }),
    }


def dates_overlap(row, date_from=None, date_to=None):
    """Show a shipment when its known planning/actual span crosses the filter."""
    dates = [
        row[key] for key in (
            'planned_start', 'planned_arrival', 'actual_start', 'actual_arrival',
        ) if row[key] is not None
    ]
    if not date_from and not date_to:
        return True
    if not dates:
        return False
    return (not date_from or max(dates) >= date_from) and (
        not date_to or min(dates) <= date_to
    )


def matches_status(row, status):
    if status == 'delayed':
        return row['is_delayed']
    if status == 'unscheduled':
        return row['unscheduled']
    return not status or status == 'all' or row['status'] == status


def has_global_schedule_access(user):
    return bool(
        user.is_superuser
        or user.groups.filter(name__in=GLOBAL_VIEW_GROUPS).exists()
    )


def visible_schedule_packings(user, queryset):
    """Enforce the document's existing view authorization, not list permissions."""
    global_view = has_global_schedule_access(user)
    for packing in queryset:
        if global_view or packing.user_can_view_workflow(user):
            yield packing


def _filter_date(value):
    try:
        return date.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


class PackingTransportScheduleView(LoginRequiredMixin, View):
    template_name = 'order/packing/transport_schedule.html'

    def get(self, request):
        query = (request.GET.get('q') or '').strip()[:100]
        method = (request.GET.get('method') or '').strip()
        status = (request.GET.get('status') or 'all').strip()
        date_from = _filter_date(request.GET.get('date_from'))
        date_to = _filter_date(request.GET.get('date_to'))
        today = timezone.localdate()

        queryset = Packing.objects.filter(is_deleted=False)
        if query:
            search = (
                Q(packing_number__icontains=query)
                | Q(bl_number__icontains=query)
                | Q(packing_item_rel__order__order_number__icontains=query)
                | Q(packing_item_rel__part_number__icontains=query)
            )
            if query.isdigit():
                search |= Q(pk=int(query))
            queryset = queryset.filter(search).distinct()
        if method in SHIPMENT_LABELS:
            queryset = queryset.filter(shipment_type=method)

        queryset = queryset.prefetch_related(
            Prefetch(
                'packing_item_rel',
                queryset=PackingItem.objects.filter(is_deleted=False)
                    .select_related('order__item', 'order__item_trade'),
                to_attr='active_schedule_items',
            ),
        ).order_by('-created_date', '-pk')

        visible = list(visible_schedule_packings(request.user, queryset))
        events = defaultdict(list)
        if visible:
            packing_type = ContentType.objects.get_for_model(Packing)
            history = WorkFlow.objects.filter(
                content_type=packing_type,
                object_id__in=[packing.pk for packing in visible],
            ).order_by('object_id', 'id')
            for entry in history:
                events[entry.object_id].append(entry)

        rows = []
        for packing in visible:
            row = build_schedule_row(packing, events[packing.pk], today)
            if dates_overlap(row, date_from, date_to) and matches_status(row, status):
                rows.append(row)

        metrics = {
            'planned': sum(row['status'] == 'planned' for row in rows),
            'in_transit': sum(row['status'] == 'in_transit' for row in rows),
            'arrived': sum(row['status'] == 'arrived' for row in rows),
            'delayed': sum(row['is_delayed'] for row in rows),
        }
        paginator = Paginator(rows, 50)
        page = paginator.get_page(request.GET.get('page'))
        packings_by_id = {packing.pk: packing for packing in visible}
        for row in page.object_list:
            row.update(build_carton_report(
                packings_by_id[row['id']].active_schedule_items
            ))
        plot_rows = [
            {
                'id': row['id'],
                'number': row['number'],
                'stage': row['stage'],
                'status': row['status'],
                'is_delayed': row['is_delayed'],
                'order_count': row['order_count'],
                'unique_carton_count': row['unique_carton_count'],
                'planned_start': row['planned_start'].isoformat() if row['planned_start'] else None,
                'planned_arrival': row['planned_arrival'].isoformat() if row['planned_arrival'] else None,
                'actual_start': row['actual_start'].isoformat() if row['actual_start'] else None,
                'actual_arrival': row['actual_arrival'].isoformat() if row['actual_arrival'] else None,
            }
            for row in page.object_list
        ]
        params = request.GET.copy()
        params.pop('page', None)
        base_query = params.urlencode()
        return render(request, self.template_name, {
            'rows': page.object_list,
            'page_obj': page,
            'plot_rows': plot_rows,
            'today_iso': today.isoformat(),
            'metrics': metrics,
            'filtered_total': len(rows),
            'q': query,
            'method': method,
            'status': status,
            'date_from': date_from.isoformat() if date_from else '',
            'date_to': date_to.isoformat() if date_to else '',
            'page_query': base_query + '&' if base_query else '',
        })
