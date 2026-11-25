"""Persistent refresh queue, independent of the broker and request transaction."""
from datetime import timedelta
import logging

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from workflow.scheduling.models import WorkflowForecast, WorkflowForecastRefresh
from .forecast_service import MODELS, recalculate
from .scheduling_rules import TARGET

logger = logging.getLogger(__name__)


def enabled():
    return getattr(settings, 'WORKFLOW_SCHEDULING_AUTO_ENABLED', False)


@transaction.atomic
def enqueue(workflow_key, object_id, reason, *, latest_policy=False):
    if not object_id or workflow_key not in MODELS:
        return
    now = timezone.now()
    job, created = WorkflowForecastRefresh.objects.select_for_update().get_or_create(
        workflow_key=workflow_key, object_id=object_id,
        defaults=dict(reason=reason, latest_policy=latest_policy))
    if not created:
        job.reason = 'trade_entry' if job.reason == 'trade_entry' else reason
        job.requested_at = now
        job.available_at = now
        job.attempts = 0
        job.last_error = ''
        job.latest_policy = job.latest_policy or latest_policy
        job.save(update_fields=['reason', 'requested_at', 'available_at', 'attempts',
                                'last_error', 'latest_policy'])


def sweep_candidates(workflow_key):
    model = MODELS[workflow_key]
    ct = ContentType.objects.get_for_model(model)
    forecasts = WorkflowForecast.objects.filter(content_type=ct, target_stage=TARGET,
        target_event='exit', is_current=True)
    unfinished = forecasts.exclude(forecast_status__in=('actual', 'cancelled')).values('object_id')
    completed = forecasts.filter(forecast_status='actual').values('object_id')
    qs = model._base_manager.all()
    if workflow_key == 'order':
        qs = qs.filter(Q(is_deleted=False, is_wh=False, is_bazar=False, cancel=False,
                        sales_admin_cancel=False, is_over=False) | Q(pk__in=unfinished))
    else:
        qs = qs.filter(Q(is_deleted=False) | Q(pk__in=unfinished))
    return qs.exclude(pk__in=completed).order_by('pk').values_list('pk', flat=True)


def enqueue_sweep(reason='daily', *, latest_policy=False):
    count = 0
    for key in MODELS:
        batch = []
        for pk in sweep_candidates(key).iterator(chunk_size=500):
            batch.append(WorkflowForecastRefresh(workflow_key=key, object_id=pk,
                                                reason=reason, latest_policy=latest_policy))
            if len(batch) == 500:
                _sweep_batch(batch, latest_policy)
                count += len(batch)
                batch = []
        if batch:
            _sweep_batch(batch, latest_policy)
            count += len(batch)
    return count


@transaction.atomic
def _sweep_batch(batch, latest_policy):
    # Do not reset retry backoff or overwrite a more specific event reason.
    WorkflowForecastRefresh.objects.bulk_create(batch, ignore_conflicts=True, batch_size=500)
    if latest_policy:
        WorkflowForecastRefresh.objects.filter(workflow_key=batch[0].workflow_key,
            object_id__in=[job.object_id for job in batch]).update(latest_policy=True)


@transaction.atomic
def process_one():
    job = WorkflowForecastRefresh.objects.select_for_update(skip_locked=True).filter(
        available_at__lte=timezone.now()).order_by('available_at', 'pk').first()
    if job is None:
        return None
    try:
        # Nested atomic gives rollback of a failed calculation while retaining
        # the claimed job, including when a database constraint fails.
        _, changed = recalculate(job.workflow_key, job.object_id, reason=job.reason,
                                 latest_policy=job.latest_policy)
    except Exception as exc:
        logger.exception('Forecast refresh failed: %s/%s', job.workflow_key, job.object_id)
        job.attempts += 1
        job.last_error = (type(exc).__name__ + ': ' + str(exc))[:2000]
        job.available_at = timezone.now() + timedelta(minutes=min(1440, 2 ** min(job.attempts, 10)))
        job.save(update_fields=['attempts', 'last_error', 'available_at'])
        return 'failed'
    job.delete()
    return 'changed' if changed else 'unchanged'


def drain(limit=200):
    result = {'changed': 0, 'unchanged': 0, 'failed': 0}
    for _ in range(limit):
        outcome = process_one()
        if outcome is None:
            break
        result[outcome] += 1
    return result
