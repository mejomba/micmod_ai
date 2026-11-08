"""Regression coverage for the read-only Packing transportation schedule."""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import reverse, resolve

from order.packing_transport_schedule import (
    PackingTransportScheduleView, build_schedule_row, confirmed_milestones,
    current_workflow_stage, dates_overlap, delay_information,
    has_global_schedule_access, matches_status, visible_schedule_packings,
    workflow_destination,
)


BASE = datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc)


def event(status, source, target, days, created=True):
    return SimpleNamespace(
        wf_status=status,
        state=source,
        current_state_name=target,
        created_date=BASE + timedelta(days=days) if created else None,
    )


def packing(planned_start=None, planned_arrival=None):
    order = SimpleNamespace(pk=4, order_number='ORD-4', item_trade=None, item=None)
    return SimpleNamespace(
        pk=18, packing_number='PK-18', bl_number='BL-18',
        estimated_shipping_start_date=planned_start,
        estimated_arrive_to_wh_date=planned_arrival,
        shipment_type='sea', transportation_company='Example Line',
        origin='Shanghai', destination='Tehran',
        active_schedule_items=[
            SimpleNamespace(pk=1, order=order, quantity=4, part_number='SKU-4'),
            SimpleNamespace(pk=2, order=order, quantity=6, part_number='SKU-4'),
        ],
    )


class PackingTransportScheduleTests(SimpleTestCase):
    def test_shipping_and_warehouse_entries_are_forward_events_only(self):
        records = [
            event(5, 'پیش‌نویس', 'پیش‌نویس', 0),
            event(3, 'تحویل شرکت حمل', 'حمل', 1),
            event(4, 'حمل', 'حمل', 2),
            event(3, 'حمل', 'قبض انبار', 3),
            event(3, 'ترخیص', 'انبار', 6),
            event(4, 'انبار', 'انبار', 7),
            event(3, 'انبار', 'اتمام کار', 8),
        ]
        dates = confirmed_milestones(records)
        self.assertEqual(dates['actual_start'], date(2026, 10, 21))
        self.assertEqual(dates['actual_arrival'], date(2026, 10, 26))
        self.assertEqual(current_workflow_stage(records), 'اتمام کار')

    def test_reentry_replaces_previous_actual_milestone(self):
        records = [
            event(3, 'تحویل شرکت حمل', 'حمل', 1),
            event(2, 'حمل', 'تحویل شرکت حمل', 2),
            event(3, 'تحویل شرکت حمل', 'حمل', 4),
        ]
        self.assertEqual(
            confirmed_milestones(records)['actual_start'], date(2026, 10, 24),
        )

    def test_historical_state_names_are_normalized(self):
        self.assertEqual(
            workflow_destination(event(3, 'DEP', 'arrive', 1)), 'حمل',
        )
        self.assertEqual(
            workflow_destination(event(3, 'ترخیص گمرک', None, 1)), 'انبار',
        )
        self.assertEqual(
            workflow_destination(event(3, 'اظهار گمرکی', None, 1)), 'ترخیص',
        )
        self.assertIsNone(confirmed_milestones([
            event(4, 'حمل', 'انبار', 1),
        ])['actual_arrival'])

    def test_missing_or_wrong_status_does_not_invent_actual_dates(self):
        values = confirmed_milestones([
            event(5, 'پیش‌نویس', 'پیش‌نویس', 0),
            event(3, 'تحویل شرکت حمل', 'حمل', 1, created=False),
            event(2, 'انبار', 'ترخیص', 2),
            event(4, 'ترخیص', 'انبار', 3),
        ])
        self.assertEqual(values, {'actual_start': None, 'actual_arrival': None})

    def test_row_uses_plan_and_workflow_independently_with_order_totals(self):
        row = build_schedule_row(
            packing(date(2026, 10, 20), date(2026, 10, 30)),
            [event(3, 'تحویل شرکت حمل', 'حمل', 1)],
            date(2026, 11, 1),
        )
        self.assertEqual(row['status'], 'in_transit')
        self.assertEqual(row['stage'], 'حمل')
        self.assertEqual(row['order_count'], 1)
        self.assertEqual(row['total_quantity'], 10)
        self.assertEqual(row['orders'][0]['number'], 'ORD-4')
        self.assertEqual(row['orders'][0]['quantity'], 10)
        self.assertEqual(row['start_delay'], 1)
        self.assertEqual(row['arrival_delay'], 2)
        self.assertTrue(row['is_delayed'])

    def test_missing_estimates_are_unknown_not_false_delays(self):
        row = build_schedule_row(packing(), [], date(2026, 11, 1))
        self.assertTrue(row['unscheduled'])
        self.assertFalse(row['is_delayed'])
        self.assertIsNone(row['start_delay'])
        self.assertIsNone(row['arrival_delay'])
        self.assertTrue(matches_status(row, 'unscheduled'))

    def test_arrived_late_and_on_time_are_distinguished(self):
        late = delay_information(
            date(2026, 10, 20), date(2026, 10, 24),
            date(2026, 10, 21), date(2026, 10, 26),
            date(2026, 11, 1),
        )
        self.assertEqual((late['start_delay'], late['arrival_delay']), (1, 2))
        self.assertTrue(late['is_delayed'])
        on_time = delay_information(
            date(2026, 10, 20), date(2026, 10, 24),
            date(2026, 10, 19), date(2026, 10, 24),
            date(2026, 11, 1),
        )
        self.assertFalse(on_time['is_delayed'])

    def test_date_filters_match_overlap_and_handle_undated_rows(self):
        row = build_schedule_row(
            packing(date(2026, 10, 20), date(2026, 11, 10)),
            [], date(2026, 11, 1),
        )
        self.assertTrue(dates_overlap(row, date(2026, 11, 1), date(2026, 11, 3)))
        self.assertFalse(dates_overlap(row, date(2026, 12, 1), None))
        self.assertFalse(dates_overlap(build_schedule_row(packing(), [], date(2026, 11, 1)),
                                       date(2026, 10, 1), None))

    def test_read_only_users_only_receive_authorized_document_rows(self):
        user = Mock(is_superuser=False)
        user.groups.filter.return_value.exists.return_value = False
        denied = Mock()
        denied.user_can_view_workflow.return_value = False
        permitted = Mock()
        permitted.user_can_view_workflow.return_value = True
        self.assertFalse(has_global_schedule_access(user))
        self.assertEqual(
            list(visible_schedule_packings(user, [denied, permitted])),
            [permitted],
        )
        user.groups.filter.return_value.exists.return_value = True
        self.assertEqual(
            list(visible_schedule_packings(user, [denied, permitted])),
            [denied, permitted],
        )

    def test_route_and_template_are_present(self):
        url = reverse('order:packing.transport_schedule')
        self.assertIn('/packing/transport-schedule/', url)
        self.assertIs(resolve(url).func.view_class, PackingTransportScheduleView)
        html = (Path(settings.BASE_DIR) /
                'order/templates/order/packing/transport_schedule.html').read_text(
                    encoding='utf-8',
                )
        self.assertIn('packing-transport-data', html)
        self.assertIn('row.orders', html)
        self.assertIn('row.actual_start', html)
        self.assertIn('row.actual_arrival', html)


    def test_timeline_contains_embedded_details_instead_of_second_table(self):
        html = (Path(settings.BASE_DIR) /
                'order/templates/order/packing/transport_schedule.html').read_text(
                    encoding='utf-8',
                )
        self.assertIn('pt-detail-source-{{ row.id }}', html)
        self.assertIn('row.unique_carton_count', html)
        self.assertIn('pt-chart-toggle', html)
        self.assertIn('row.cartons', html)
        self.assertIn('row.category_groups', html)
        self.assertIn('data-pt-group="category"', html)
        self.assertIn('item.net_percent', html)
        self.assertIn('item.entered_percent', html)
        self.assertIn('carton.size_conflict', html)
        self.assertNotIn('<h2>جدول مرور حمل</h2>', html)
        self.assertIn("if (!values.length) values.push(timestamp(today));", html)
        self.assertIn('renderTableDates(panel)', html)
