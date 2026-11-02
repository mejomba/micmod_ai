"""Inquiry timing for quotation list (no schema migration required).

Time span: first workflow ENTRY into 'استعلام قیمت' through latest workflow EXIT
or now, if the quotation is currently in that state. Re-entries do not reset it.
"""
from django.contrib.contenttypes.models import ContentType
from django.db.models import F, OuterRef, Subquery
from django.utils import timezone
from django.utils.html import format_html

from .models import Quotation, QuotationItem
from inquiry.models import InquiryResult
from workflow.models import WorkFlow


INQUIRY_STATE = 'استعلام قیمت'


def annotate_quotation_inquiry_timing(queryset):
    """Fetch timing events with correlated subqueries, not per-row DB calls."""
    quotation_ct = ContentType.objects.get_for_model(Quotation)
    events = WorkFlow.objects.filter(
        content_type_id=quotation_ct.pk,
        object_id=OuterRef('pk'),
        is_deleted=False,
    )
    # `current_state_name` is the destination; `state` is the source state.
    first_entry = (
        events.filter(current_state_name=INQUIRY_STATE)
        .order_by('created_date', 'pk').values('created_date')[:1]
    )
    latest_exit = (
        events.filter(state=INQUIRY_STATE)
        .exclude(current_state_name=INQUIRY_STATE)
        .order_by('-created_date', '-pk').values('created_date')[:1]
    )
    inquiry_items = QuotationItem.objects.filter(quotation_id=OuterRef('pk'))
    latest_local_reply = (
        inquiry_items.filter(local_price_inquiry_done_date__isnull=False)
        .order_by('-local_price_inquiry_done_date', '-pk')
        .values('local_price_inquiry_done_date')[:1]
    )
    latest_foreign_reply = (
        inquiry_items.filter(foreign_price_inquiry_done_date__isnull=False)
        .order_by('-foreign_price_inquiry_done_date', '-pk')
        .values('foreign_price_inquiry_done_date')[:1]
    )
    inquiry_result = (
        InquiryResult.objects.filter(quotation_item__quotation_id=OuterRef('pk'))
        .order_by('-last_update_date', '-pk')
        .values('last_update_date')[:1]
    )
    return queryset.annotate(
        _inq_first_entry=Subquery(first_entry),
        _inq_latest_exit=Subquery(latest_exit),
        _inq_latest_local_reply=Subquery(latest_local_reply),
        _inq_latest_foreign_reply=Subquery(latest_foreign_reply),
        _inq_latest_result_reply=Subquery(inquiry_result),
        _inq_current_state=F('last_work_flow__current_state_name'),
    )


def format_timedelta_fa(start, end):
    """Compact, elapsed whole hours (under 1 day) or whole days (1+ days)."""
    if not start or not end or end < start:
        return None
    total_hours = int((end - start).total_seconds() // 3600)
    days = total_hours // 24
    return f'{days} روز' if days >= 1 else f'{total_hours} ساعت'


def compute_quotation_inquiry_timing(first_entry, latest_exit, current_state,
                                     last_local_reply=None, last_foreign_reply=None, now=None,
                                     last_result_reply=None):
    """Pure calculation to make returned quotations and historical records testable."""
    if first_entry is None:
        return None
    active = current_state == INQUIRY_STATE
    endpoint = (now or timezone.now()) if active else latest_exit
    # A transition may not have been recorded yet; do not fake a finished duration.
    if endpoint is None or endpoint < first_entry:
        return None
    duration = format_timedelta_fa(first_entry, endpoint)
    replies = [dt for dt in (last_local_reply, last_foreign_reply, last_result_reply)
               if dt is not None and first_entry <= dt <= endpoint]
    latest_reply = max(replies) if replies else None
    since_reply = format_timedelta_fa(latest_reply, endpoint) if latest_reply else None
    return {'duration': duration, 'since_reply': since_reply, 'active': active,
            'first_entry': first_entry, 'end': endpoint, 'latest_reply': latest_reply}


def render_quotation_inquiry_timing(quotation):
    metrics = compute_quotation_inquiry_timing(
        first_entry=getattr(quotation, '_inq_first_entry', None),
        latest_exit=getattr(quotation, '_inq_latest_exit', None),
        current_state=getattr(quotation, '_inq_current_state', None),
        last_local_reply=getattr(quotation, '_inq_latest_local_reply', None),
        last_foreign_reply=getattr(quotation, '_inq_latest_foreign_reply', None),
        last_result_reply=getattr(quotation, '_inq_latest_result_reply', None),
    )
    if metrics is None:
        return '—'
    return format_html(
        '<span class="text-nowrap" style="display:inline-block;font-size:12px;line-height:1;">{}</span>',
        metrics['duration'],
    )
