# Scheduling persistence (phase 2)

This change adds nine generic workflow models and schema-only migration 0011.
It does not write legacy workflow deadlines or operational dates, seed policies,
or trigger any recalculation. Calendar rows and exceptions belong to a policy
version; subsequent policy versions must clone their calendar configuration.
Weekday integers follow Python (Monday=0). Duration units are currently days.
Forecast revisions use a conditional unique constraint to ensure one current
record per document, target and entry/exit event. The database stores source
dates independently; step components and policy snapshots preserve details.
Policy cloning and publication are provided in policies.py. The publication
entry point requires a registry-aware validator from the integration layer.
Previously published versions remain intact, and effective dates control
selection. The service is not wired to any public view or event hook.
Direct ORM writes are not yet guarded; append-only forecast writes and protected
draft editing must be implemented before enabling management or event hooks.
No production migration or backfill is performed by this change.

Local verification, using the actual portal test settings:
    python manage.py check
    python manage.py makemigrations workflow --check --dry-run
    python manage.py migrate --plan
    python manage.py test workflow.test_scheduling_models workflow.test_scheduling_policies
    python -m unittest workflow.test_scheduling_engine -v

The model tests require Django and a test database. Do not apply the migration
to production until the entire scheduling feature has passed integration tests.

## Phase 3: configured forecasts

Register a Binding with explicit typed fields, allowed stages, adapter and context provider.
Use scheduler.preview for draft calculations and scheduler.forecast for a published policy.
Use publish_configured_policy for registry-aware publication. Explicit configured outgoing
transitions replace the registered defaults for that source. Alternative routes and unknown
scenarios never silently choose a date; parallel mode requires all applicable paths. The
validator conservatively rejects same-priority replacement conditions unless it can prove
disjoint equality/membership. Complex AND/OR branch joins are not inferred. No business
adapters, policy seed, forecast writes or UI hooks are enabled yet.

Pure tests: python -m unittest workflow.test_scheduling_engine workflow.test_scheduling_configuration -v
Django tests: python manage.py test workflow.test_configured_scheduler

## Phase 8: publication and revision protection

PostgreSQL migration 0013 installs row-level guards for policy family identity,
published policy and calendar/stage/rule/transition rows, and append-only forecast
history. Only the validated publication service may move a draft to published,
and the history service may append details to a current revision in its
transaction-local write scope. Prior revisions can only lose their current marker.
Nullable audit-user references may be cleared (e.g. user deletion). No existing
policy or history data is rewritten. These guards protect against unintended
ORM/SQL mutations, not privileged administrators who can disable triggers,
truncate tables or deliberately enter internal write scopes. Other DB engines
do not get the PostgreSQL triggers and are not supported for production scheduling.
