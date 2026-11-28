# Operational scheduling, phase 5

Approved initial durations are in scheduling_rules.py and are seeded into
versioned workflow models by seed_workflow_scheduling. The generic engine
contains no operational constants. Existing JSON workflow deadlines and
commitment dates are unchanged. The transport values road and rail extend
the choices; express maps to air only in scheduling.

After applying migrations, run (using an authorized portal user):
    python manage.py seed_workflow_scheduling --username YOUR_PORTAL_USER --publish

Without --publish the command creates drafts. It never overwrites or publishes
an existing policy. Existing draft publication must use publish_configured_policy.
The two policy families initially share the same packing table; changes to one
family do not yet synchronize the other.

Read-only forecast_order_arrival and forecast_packing_arrival select a published
policy, or accept an explicit policy for previews. They do not write forecast
history, modify operational fields, create virtual documents or contact Sepidar.

GIO and Packing rows are related through Order, without a direct allocation FK.
Residual GIO quantities use FIFO by date/ID when packed quantities exist, and
record an assumption. For a packing draft, multiple candidate GIOs mean unknown
weight rather than summing or selecting an arbitrary one. Virtual GIO weight
uses the policy default zero only as a calculation proxy for a one-day draft
(never a saved or actual weight); actual GIO with incomplete weight blocks the
draft prediction until a valid effective weight exists.

Arrival evidence is a successful normal transfer line to configured central
stock with a receipt ID and sent_at. Warehouse entry, other destinations,
damaged transfer and unconfirmed receipt quantity do not count as actual
central receipt. Declared arrival is preserved independently for pending
quantities; an expired date is flagged. The source is a date-only declaration
for central arrival, interpreted at local midnight; it is not a Sepidar receipt
timestamp. Actual quantity is capped per packing row. Legacy receipts lacking
durable transfer evidence and receipt discrepancies require reconciliation.
FIFO is a forecast assumption only, not an actual allocation. First arrival
is the earliest known date; if other portions are unknown, it is not definitive.

Current state uses actual forward/back transition history; reassignment is not
a new stage. The read-only service works on current document inputs; as_of is
not a historical reconstruction of previous data. Persistence, event-driven
invalidation, efficient list display, and full reconciliation are next phases.

Tests:
    python -m unittest order.test_scheduling_business_rules workflow.test_scheduling_engine workflow.test_scheduling_configuration -v
    python manage.py test order.test_operational_scheduling order.test_gio_weight_db order.test_packing_sepidar
