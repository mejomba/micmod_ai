"""Regression tests for Packing timeline and user-entered workflow notes."""
from datetime import datetime, timedelta, timezone as dt_timezone
from types import SimpleNamespace

from django.test import SimpleTestCase

from order.packing_workflow_timeline import (
    build_packing_workflow_timeline, format_elapsed, format_elapsed_en,
)
from order.views import QuickPackingView


STATES = ['پیش‌نویس', 'تحویل شرکت حمل', 'حمل']


def event(status, at, source, target, description='', who='operator'):
    return SimpleNamespace(
        wf_status=status,
        created_date=at,
        state=source,
        current_state_name=target,
        action='next' if status == 3 else 'other',
        wf_description=description,
        from_user=who,
        creator_user='creator',
        to_user='assignee',
    )


class PackingTimelineTests(SimpleTestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 27, 8, 0, tzinfo=dt_timezone.utc)
        self.normalize = lambda stage: stage

    def timeline(self, *events):
        return build_packing_workflow_timeline(events, STATES, self.normalize)

    def test_forward_transitions_have_real_entry_times_and_durations(self):
        result = self.timeline(
            event(5, self.now, STATES[0], STATES[0], 'Created'),
            event(3, self.now + timedelta(hours=2), STATES[0], STATES[1], 'Handed over'),
            event(3, self.now + timedelta(hours=5), STATES[1], STATES[2]),
        )
        self.assertEqual(result['stages'][0]['entered_at'], self.now)
        self.assertEqual(result['stages'][1]['duration_to_next'], '3 ساعت')
        self.assertEqual(result['stages'][0]['duration_to_next'], '2 ساعت')
        self.assertEqual(result['stages'][0]['duration_to_next_en'], '2h')
        self.assertEqual(result['stages'][2]['entered_at'], self.now + timedelta(hours=5))
        self.assertEqual(result['history'][0]['description'], '')
        self.assertEqual(result['history'][-1]['description'], 'Created')

    def test_change_assignee_does_not_restart_stage_elapsed_time(self):
        result = self.timeline(
            event(5, self.now, STATES[0], STATES[0]),
            event(4, self.now + timedelta(minutes=30), STATES[0], STATES[0], 'Reassigned'),
            event(3, self.now + timedelta(hours=2), STATES[0], STATES[1]),
        )
        self.assertEqual(result['stages'][0]['duration_to_next'], '2 ساعت')
        self.assertEqual(result['history'][1]['action'], 'تغییر مسئول')
        self.assertEqual(result['history'][1]['description'], 'Reassigned')
        self.assertEqual(result['history'][1]['elapsed_since_previous'], '30 دقیقه')

    def test_backward_then_forward_uses_latest_real_transition(self):
        result = self.timeline(
            event(5, self.now, STATES[0], STATES[0]),
            event(3, self.now + timedelta(hours=1), STATES[0], STATES[1]),
            event(2, self.now + timedelta(hours=2), STATES[1], STATES[0]),
            event(3, self.now + timedelta(hours=4), STATES[0], STATES[1]),
        )
        self.assertEqual(result['stages'][0]['entered_at'], self.now + timedelta(hours=2))
        self.assertEqual(result['stages'][0]['duration_to_next'], '2 ساعت')
        self.assertEqual(result['stages'][1]['entered_at'], self.now + timedelta(hours=4))
        self.assertEqual(len(result['history']), 4)

    def test_skipped_or_unvisited_stage_does_not_invent_duration(self):
        result = self.timeline(
            event(5, self.now, STATES[0], STATES[0]),
            event(3, self.now + timedelta(hours=4), STATES[0], STATES[2]),
        )
        self.assertIsNone(result['stages'][0]['duration_to_next'])
        self.assertIsNone(result['stages'][1]['entered_at'])

    def test_empty_timeline_has_no_implicit_timestamps(self):
        result = self.timeline()
        self.assertEqual(result['history'], [])
        self.assertTrue(all(x['entered_at'] is None for x in result['stages']))
        self.assertTrue(all(x['duration_to_next'] is None for x in result['stages']))

    def test_duration_formatter_days_hours_minutes(self):
        value = timedelta(days=1, hours=2, minutes=3)
        self.assertEqual(format_elapsed(value), '1 روز و 2 ساعت و 3 دقیقه')
        self.assertEqual(format_elapsed_en(value), '1d 2h 3m')
        self.assertEqual(format_elapsed(timedelta(seconds=15)), '0 دقیقه')

    def test_workflow_note_max_length(self):
        view = QuickPackingView()
        view.request = SimpleNamespace(POST={'wf_description': '  توضیح آزمایشی  '})
        self.assertEqual(view._workflow_description(), 'توضیح آزمایشی')
        view.request = SimpleNamespace(POST={'wf_description': 'X' * 256})
        with self.assertRaises(ValueError):
            view._workflow_description()
