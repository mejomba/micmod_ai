# Phase 7 — portal scheduling interface

URL: /workflow/scheduling/ (also linked in the settings section of the sidebar).
Requires workflow.view_workflowschedulepolicy. Editing a draft uses the
respective model add/change/delete permissions; cloning requires
add_workflowschedulepolicy; publishing and applying the latest effective
version to open documents require publish_schedule_policy. Viewing
calculation history requires workflow.view_workflowforecast independently,
plus access to the real Order/Packing document. The summary in an already
authorized operational page does not expose detailed rules without that
permission. No changes to the existing seeded policies or schema.

The editor supports policy versions, stages, calendars/weekly workdays and
exceptions, rules (typed visual AND/OR/NOT tree), transitions, unknown-value
behavior, and read-only previews on real authorized documents. Validation
and publication are server-side. Existing published versions are read-only
through these views; arbitrary ORM changes are not prevented by this phase.
"Apply to open documents" queues the selected operational workflow, only
for the latest currently effective central-arrival policy, without running
forecasts in the web request. The existing worker/drain processes the queue.

Order list uses correlated SQL subqueries for stored effective date, status,
source and initial forecast, and a DB date-difference annotation. Date and
status filters are SQL-backed; display dates are Jalali for Persian and ISO
for English. Variance is signed calendar days against the initial forecast.
The existing column layout remains role-specific. No per-row forecast query
or recalculation. Order and Packing panels show stored summary and, with
history permission, stored step/route/assumption/calendar and shipment
details. The separate paginated history permits selecting an older revision.
The actual stages section is live history, so it is omitted for old revisions.
The portal's existing Dason-language preference is mirrored to a cookie;
the server-rendered editor and panels reflect it on the next page load.
Date filter, exception entry and publication inputs use native Gregorian
inputs, with labels distinguishing them from Jalali operational display.
Browser layout and DataTable end-to-end behavior still require validation
in the portal environment. No new migration.

Tests:
    python manage.py test order.test_scheduling_portal
    python manage.py test order.test_forecast_history order.test_operational_scheduling
    python -m unittest workflow.test_scheduling_engine workflow.test_scheduling_configuration workflow.test_scheduling_history_values order.test_scheduling_business_rules -v
