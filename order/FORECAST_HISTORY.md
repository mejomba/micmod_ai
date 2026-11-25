# Phase 6 — forecast history and refresh

Apply workflow/0012_workflow_forecast_refresh after 0011; no data migration
or automatic backfill. The existing seeded policies are not modified.

Preview one order, then calculate it:
    python manage.py recalculate_workflow_forecasts --order-id 123 --dry-run
    python manage.py recalculate_workflow_forecasts --order-id 123

Backfill / reconcile open orders and packing, then process a bounded batch:
    python manage.py recalculate_workflow_forecasts --backfill --limit 200
    python manage.py recalculate_workflow_forecasts --drain --limit 200

Use repeated --order-id and --packing-id for selected documents. --sweep queues
open documents and drains a batch; --dry-run --sweep previews at most --limit
documents without creating history or jobs. Existing forecasts keep their
policy version unless --latest-policy is explicitly chosen, for example
--sweep --latest-policy. Completed actual forecasts are excluded from sweeps.

Initial forecast is the first nonempty expected date; late/backfill creation is
marked initial_is_backfill. Revisions store policy, inputs, assumptions, stage
components, anchors and per-shipment evidence. Meaningful change creates a
revision; unchanged day-level estimates do not. Actual receipt timestamps are
not rounded in fingerprints. Mixed-source arrival is a composite estimate;
the original sources remain in the shipment snapshot. First arrival and
quantities are currently stored in context_snapshot.result (not indexed).
No operational dates, workflow deadlines or Sepidar data are rewritten.

Enable automatic event registration and Celery beat schedules with environment
variable WORKFLOW_SCHEDULING_AUTO_ENABLED=1 in web, worker and beat processes,
only after migration and seed. Uses the existing _keenthemes.celery_main app;
worker and beat must actually be running (or invoke the CLI periodically).
The daily task queues open documents at 02:00 in Celery's configured timezone;
the drain runs every 60 seconds, processing up to 200 records per execution.
If the installation uses the django-celery-beat database scheduler, confirm
these two periodic tasks are registered and enabled, with no duplicate schedules.

Normal model saves/deletes are observed and related documents queued after
successful commit. The manual GIO weight endpoint explicitly notifies after
its bulk update. Other arbitrary QuerySet.update, bulk_create, raw SQL, external
item changes and the small crash window between business commit and enqueue
are reconciled by the daily sweep, not guaranteed instant updates. Hard-deleted
documents retain their historical revisions. Failed refreshes remain in
WorkflowForecastRefresh with retry time and error; no operational rollback.
The queue uses PostgreSQL row locking and the default DB only. The view layer
must read the stored latest revision, not run the calculation per list row.
The first prediction can lag the entry event by queue processing time; the
stored calculated_at/as_of always reflect actual computation time.

Tests:
    python -m unittest workflow.test_scheduling_history_values workflow.test_scheduling_engine workflow.test_scheduling_configuration order.test_scheduling_business_rules -v
    python manage.py test order.test_forecast_history
