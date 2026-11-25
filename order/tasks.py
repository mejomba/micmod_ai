"""Celery entry points; queue processing can also run without Celery via CLI."""
from celery import shared_task
from .scheduling_queue import enabled, enqueue_sweep, drain


@shared_task(name='order.scheduling.drain')
def drain_workflow_forecasts(limit=200):
    return drain(limit) if enabled() else {'disabled': True}


@shared_task(name='order.scheduling.daily')
def daily_workflow_forecasts():
    if not enabled():
        return {'disabled': True}
    return {'candidates': enqueue_sweep('daily')}
