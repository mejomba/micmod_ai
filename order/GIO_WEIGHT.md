# GIO weight (phase 4)

The packing creation/edit paths use Order.final_item.weight directly in kg.
GIO follows that same operational weight source (trade item, otherwise sales
item). Sepidar's sales-item reference is left unchanged. No extra conversion
is applied because the packing code stores the product in net_weight_kg.

Only manual_weight_kg is persisted: NULL means automatic; explicit 0 means
a manual zero. The calculated/effective properties always derive from saved
active GIO rows and the current item weight. Missing/invalid rows produce
an unknown calculated total, not an artificial zero. The known subtotal is
available separately. A manual value remains effective even if rows change.
The weight form is independent of normal GIO saves and preserves Sepidar locks.
Permission is order.change_gio plus the existing object-access queryset.
For legacy GIO screens, the weight summary links to the Quick GIO editor.
The display reflects saved rows, not pending unsaved rows.

Forecast invalidation for changes in effective weight (including changes to
rows, orders or ItemWeight) belongs to the next operational/event integration
phase; no forecast is persisted or recalculated by this change.

Migration: order/0145_gio_manual_weight.py (depends on 0144). Existing GIO
rows default to automatic and no backfill is needed. It is independent of
workflow/0011_workflow_scheduling.py.

Tests:
    python -m unittest order.test_gio_weight_math -v
    python manage.py test order.test_gio_weight_db order.test_gio_sepidar
