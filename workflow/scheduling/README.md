# Scheduling persistence (phase 2)

This change adds nine generic workflow models and schema-only migration 0011.
It does not write legacy workflow deadlines or operational dates, seed policies,
or trigger any recalculation. Calendar rows and exceptions belong to a policy
version; subsequent policy versions must clone their calendar configuration.
Weekday integers follow Python (Monday=0). Duration units are currently days.
Forecast revisions use a conditional unique constraint to ensure one current
record per document, target and entry/exit event. The database stores source
dates independently; step components and policy snapshots preserve details.
The persistence layer does not yet enforce immutable published policies or
append-only revisions against direct ORM edits. The publication/recalculation
services must enforce that contract before enabling management or event hooks.
No production migration or backfill is performed by this change.

Local verification, using the actual portal test settings:
    python manage.py check
    python manage.py makemigrations workflow --check --dry-run
    python manage.py migrate --plan
    python manage.py test workflow.test_scheduling_models
    python -m unittest workflow.test_scheduling_engine -v

The model tests require Django and a test database. Do not apply the migration
to production until the entire scheduling feature has passed integration tests.
