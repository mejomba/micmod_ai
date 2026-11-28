"""Manual refresh, initial backfill, preview, and retry queue processing."""
from django.core.management.base import BaseCommand, CommandError
from order.forecast_service import recalculate
from order.scheduling_queue import enqueue_sweep, sweep_candidates, drain
from workflow.scheduling.models import WorkflowForecastRefresh
from django.utils import timezone


class Command(BaseCommand):
    help = 'Recalculate arrival forecasts without modifying operational dates or Sepidar documents.'

    def add_arguments(self, parser):
        parser.add_argument('--order-id', type=int, action='append', default=[])
        parser.add_argument('--packing-id', type=int, action='append', default=[])
        parser.add_argument('--sweep', action='store_true')
        parser.add_argument('--backfill', action='store_true')
        parser.add_argument('--drain', action='store_true')
        parser.add_argument('--latest-policy', action='store_true')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--limit', type=int, default=200)

    def handle(self, *args, **options):
        limit = options['limit']
        if not 1 <= limit <= 10000:
            raise CommandError('Limit must be from 1 to 10000')
        targets = [('order', pk) for pk in options['order_id']] + [('packing', pk) for pk in options['packing_id']]
        sweep = options['sweep'] or options['backfill']
        if not targets and not sweep and not options['drain']:
            raise CommandError('Specify --order-id, --packing-id, --sweep, --backfill or --drain.')
        reason = 'backfill' if options['backfill'] else 'manual'
        if options['dry_run'] and options['drain']:
            raise CommandError('--dry-run cannot process queued writes; use --sweep --dry-run or explicit IDs.')
        if options['dry_run'] and sweep:
            for key in ('order', 'packing'):
                if len(targets) < limit:
                    targets.extend((key, pk) for pk in sweep_candidates(key,include_closed_legacy=options['backfill'])[:limit-len(targets)])
        failed = 0
        for key, pk in dict.fromkeys(targets):
            try:
                result, changed = recalculate(key, pk, reason=reason,
                    latest_policy=options['latest_policy'], dry_run=options['dry_run'])
                if options['dry_run'] and result:
                    self.stdout.write('%s/%s preview: %s / %s' % (key, pk, result['status'], result.get('complete_arrival')))
                else:
                    self.stdout.write('%s/%s: %s' % (key, pk, 'changed' if changed else 'unchanged/skipped'))
            except Exception as exc:
                failed += 1
                self.stderr.write('%s/%s: %s' % (key, pk, exc))
        if not options['dry_run']:
            if sweep:
                count = enqueue_sweep(reason, latest_policy=options['latest_policy'])
                self.stdout.write('Sweep candidates: %s' % count)
            if sweep or options['drain']:
                stats = drain(limit)
                failed += stats['failed']
                self.stdout.write(str(stats))
                self.stdout.write('Pending jobs: %s; delayed jobs: %s' % (
                    WorkflowForecastRefresh.objects.count(),
                    WorkflowForecastRefresh.objects.filter(available_at__gt=timezone.now()).count()))
        if failed:
            raise CommandError('%s calculation(s) failed; queued failures remain retryable.' % failed)
