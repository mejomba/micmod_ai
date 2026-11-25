from datetime import date, datetime, timezone
from decimal import Decimal
from unittest import TestCase
from workflow.scheduling.engine import (
    Calendar, Component, Edge, Rule, SchedulingError, apply_rules,
    forecast_route, matches, resolve_routes,
)


class SchedulingEngineTests(TestCase):
    def setUp(self):
        self.start = datetime(2026, 11, 25, 9, tzinfo=timezone.utc)
        self.cal = {'work': Calendar('UTC', frozenset({5, 6, 0, 1, 2})),
                    'all': Calendar('UTC')}
        self.schema = {'weight': 'number', 'lead': 'number', 'has_price': 'boolean'}
        self.context = {'weight': Decimal('15000.001'), 'lead': 0, 'has_price': False}

    def test_workdays_weekend_and_zero(self):
        self.assertEqual(self.cal['work'].add(self.start, 1).date(), date(2026, 11, 28))
        self.assertEqual(self.cal['work'].add(self.start, 0), self.start)
        self.assertEqual(self.cal['all'].add(self.start, 1).date(), date(2026, 11, 26))

    def test_exception(self):
        cal = Calendar('UTC', frozenset({0, 1, 2, 5, 6}), {date(2026, 11, 26): True})
        self.assertEqual(cal.add(self.start, 1).date(), date(2026, 11, 26))
        self.assertEqual(cal.elapsed(self.start, cal.add(self.start, 2)), 2)

    def test_condition_types(self):
        with self.assertRaises(SchedulingError):
            matches({'field': 'weight', 'operator': 'gt', 'value': '15000'}, self.context, self.schema)
        with self.assertRaises(SchedulingError):
            matches({'field': '__class__', 'operator': 'eq', 'value': 1}, self.context, self.schema)
        self.assertTrue(matches({'and': [{'field': 'lead', 'operator': 'eq', 'value': 0},
                                        {'field': 'has_price', 'operator': 'eq', 'value': False}]}, self.context, self.schema))

    def test_weight_boundary_and_rule_priority(self):
        rules = [Rule('large', {'field': 'weight', 'operator': 'gt', 'value': 15000},
                      {'operation': 'set_duration', 'value': 4}, 10),
                 Rule('fallback', {}, {'operation': 'set_duration', 'value': 1}, 0)]
        for value, expected in [(299, 1), (300, 1), (301, 1), (14999, 1), (15000, 1), (Decimal('15000.001'), 4), (15001, 4)]:
            components, _ = apply_rules(Component(1, 'work'), rules, dict(self.context, weight=value), self.schema, self.cal)
            self.assertEqual(components[0].duration, expected)

    def test_additive_mixed_calendar(self):
        rules = [Rule('lead', {}, {'operation': 'add_field_duration', 'field': 'lead', 'calendar': 'all'})]
        result, applied = apply_rules(Component(1, 'work'), rules, dict(self.context, lead=5), self.schema, self.cal)
        self.assertEqual(result, (Component(1, 'work'), Component(5, 'all')))
        self.assertEqual(applied, ('lead',))
        end, _ = forecast_route(('stage',), {'stage': result}, self.cal, self.start)
        self.assertEqual(end.date(), date(2026, 12, 3))

    def test_conflict_and_negative(self):
        effect = {'operation': 'set_duration', 'value': 1}
        with self.assertRaises(SchedulingError):
            apply_rules(Component(1, 'work'), [Rule('a', {}, effect), Rule('b', {}, effect)], self.context, self.schema, self.cal)
        with self.assertRaises(SchedulingError):
            Component(-1, 'work')

    def test_routes_independent_of_business_models(self):
        edges = [Edge('quote.draft', 'quote.review'), Edge('quote.review', 'contract.ready'), Edge('quote.draft', 'contract.ready')]
        routes = resolve_routes('quote.draft', 'contract.ready', edges, {}, {})
        self.assertEqual(len(routes), 2)
        with self.assertRaises(SchedulingError):
            resolve_routes('quote.draft', 'missing', edges, {}, {})
        with self.assertRaises(SchedulingError):
            resolve_routes('a', 'z', [Edge('a', 'b'), Edge('b', 'a')], {}, {})

    def test_remaining_and_entry_exit(self):
        entered = datetime(2026, 11, 24, 9, tzinfo=timezone.utc)
        timings = {'a': (Component(2, 'work'),), 'b': (Component(1, 'all'),)}
        end, steps = forecast_route(('a', 'b'), timings, self.cal, self.start, entered)
        self.assertEqual(steps[0].remaining[0].duration, 1)
        self.assertEqual(end.date(), date(2026, 11, 29))
        entry, _ = forecast_route(('a', 'b'), timings, self.cal, self.start, entered, 'entry')
        self.assertEqual(entry.date(), date(2026, 11, 28))

    def test_overdue_cannot_end_in_past(self):
        entered = datetime(2026, 11, 20, 9, tzinfo=timezone.utc)
        end, steps = forecast_route(('a',), {'a': (Component(1, 'work'),)}, self.cal, self.start, entered)
        self.assertTrue(steps[0].overdue)
        self.assertEqual(end, self.start)

    def test_parallel_and_alternative_policy(self):
        from workflow.scheduling.engine import forecast_routes
        routes = [('a', 'b'), ('a', 'c', 'b')]
        timings = {key: (Component(1, 'all'),) for key in ('a', 'b', 'c')}
        date_, results = forecast_routes(routes, timings, self.cal, self.start)
        self.assertIsNone(date_)
        self.assertEqual(len(results), 2)
        date_, _ = forecast_routes(routes, timings, self.cal, self.start, mode='parallel')
        self.assertEqual(date_.date(), date(2026, 11, 28))
