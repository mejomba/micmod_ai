# Scheduling engine release gate (phase 8)

Target: feature/workflow-scheduling-engine -> mejomba_dev. Do not merge until
Django, PostgreSQL and browser regressions pass on the actual portal environment.

## Test environment, never production

1. Pull the feature branch. Check that local work is not overwritten.
2. Run `python manage.py check`, `python manage.py makemigrations --check --dry-run`
   and `python manage.py migrate --plan`.
3. Apply migrations to the development database. 0013 installs PostgreSQL
   triggers only; no policy reseed, no data backfill, no Sepidar call.
4. Run `python manage.py audit_workflow_scheduling` after applying migrations
   and confirming both central-arrival policies are published.
5. Run the new and prior tests on the disposable Django test database:

       python -m unittest workflow.test_scheduling_engine workflow.test_scheduling_configuration workflow.test_scheduling_history_values order.test_scheduling_business_rules order.test_gio_weight_math -v
       python manage.py test workflow.test_scheduling_models workflow.test_scheduling_policies workflow.test_configured_scheduler workflow.test_scheduling_protection workflow.test_scheduling_concurrency order.test_scheduling_portal order.test_forecast_history order.test_operational_scheduling order.test_gio_weight_db
       python manage.py test order workflow

   The last command covers the existing GIO/Packing, workflow, permissions,
   translation, layout and Sepidar mock-based regressions. Verify project test
   settings isolate external systems before running the full suite.
6. Browser verification: manage a cloned policy, reject an invalid rule,
   preview a real allowed order, verify forbidden access, inspect saved
   forecasts, sort/filter by date/status, switch Persian/English and reload.
7. Confirm PostgreSQL query plan and concurrent workload at representative scale.
8. Confirm Worker/Beat are running and the two scheduled tasks are registered
   once. A disabled auto flag means forecasts do not refresh automatically.
9. Verify a single-order dry-run, then calculate and review stored results.
   Inspect retries using the audit command; do not replay Sepidar requests.

## Known operational decisions / remaining verification

- The order and packing policies are two separately versioned families. Keep
  shared packing rules aligned when intended; automatic synchronization is
  not implemented. An order forecast uses the pinned order policy for its
  packing segments.
- No direct GIOItem-PackingItem link exists. FIFO is a forecast assumption,
  ambiguous draft weights are unknown; never invent an actual allocation.
- Central actual receipt means successful normal transfer to configured
  central stock with positive receipt ID and sent_at. Legacy receipts without
  durable evidence, damaged/noncentral quantities, or contradictory
  allocations need reconciliation. Date-only declared packing arrival is
  interpreted at local midnight; it is not a receipt timestamp.
- Actual current forecasts are frozen against normal refresh. Later evidence
  corrections require explicit investigation; an audited correction UI is
  not implemented.
- Standard save/delete signals run after commit. Arbitrary bulk/raw updates
  and the post-commit enqueue crash window are reconciled by the daily sweep;
  they are not guaranteed immediate. Closed actual records are excluded.
- The initial forecast may lag the entry by queue processing time; existing
  documents are marked backfill. Mixed-source complete dates are composite,
  with original sources retained per shipment.
- PostgreSQL trigger protections do not extend to other engines, privileged
  DB administrators, TRUNCATE or intentional internal service bypass.
- Server-rendered language follows the existing preference after reload.
  Native date entry and date filtering are Gregorian.
- The independent unit suite does not prove integration correctness, real
  database locking, migration validity, template behavior, or browser UX.

Production deployment: after verified merge, back up the database, apply the
schema migrations in a planned window, audit policies/guards, enable the
existing worker and beat tasks, and run bounded backfill/drain if required.
Do not reseed existing policies. No production database or Sepidar action is
authorized by this branch change.

Rollback: take a database backup before deploying. Reversing workflow/0013
removes its trigger protections only; earlier forecast history is retained.
Do not roll back 0011/0012 or order/0145/0146 casually, since dropping tables or
fields can destroy scheduling data. Disable automatic scheduling and stop
workers before rolling back the code/schema.
