from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase
from workflow.scheduling.registry import Binding, StageState
from workflow.scheduling.configuration import calculate, validate_policy
from order.scheduling_rules import (FIELDS, KEYS, ORDER_KEYS, PACKING_KEYS, TARGET, ORDER_STAGES, PACKING_STAGES, initial_policy, transport_method, stage_state, Shipment, summarize_shipments, residual_gio_allocations)

class BusinessRulesTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 25, 9, tzinfo=timezone.utc)
        raw = initial_policy('order', 'UTC')
        self.binding = Binding('order', object, lambda x: None, lambda x: {}, FIELDS, frozenset(KEYS), entry_stages=frozenset((ORDER_KEYS[0],)), targets=frozenset((TARGET,)))
        self.policy = validate_policy(raw, self.binding)

    def predict(self, method='air', weight=15000, lead=0, inquiry=True, source=ORDER_KEYS[0]):
        return calculate(self.policy, self.binding, StageState(source, self.now), {'has_price_inquiry': inquiry, 'production_lead_time': lead, 'shipment_type': method, 'gio_weight_kg': weight}, TARGET, 'exit', self.now)

    def total(self, result):
        return sum(c.duration for s in result.scenarios[0].routes[0][1] for c in s.components)

    def test_table_totals(self):
        for method, expected in [('air', 18), ('sea', 80), ('road', 80), ('rail', 85)]:
            self.assertEqual(self.total(self.predict(method)), expected)
        self.assertEqual(transport_method('express'), 'air')
        self.assertIsNone(transport_method('unknown'))

    def test_inquiry_and_lead_time(self):
        self.assertEqual(self.total(self.predict(inquiry=False)), 21)
        missing = self.predict(lead=None)
        self.assertEqual(self.total(missing), 23)
        self.assertEqual(missing.status, 'provisional')
        self.assertEqual(self.total(self.predict(lead=10)), 28)
        self.assertEqual(self.total(self.predict(inquiry=False, source=ORDER_KEYS[1])), self.total(self.predict(source=ORDER_KEYS[1])))

    def test_weight_threshold_and_missing(self):
        self.assertEqual(self.total(self.predict(weight=Decimal('15000.001'))), 21)
        missing = self.predict(weight=None)
        self.assertEqual(self.total(missing), 18)
        self.assertEqual(missing.status, 'provisional')
        self.assertIsNone(self.predict(method=None).estimated_at)

    def test_stage_reassignment_and_return(self):
        def event(status, source, target, day):
            return SimpleNamespace(wf_status=status, state=source, current_state_name=target, created_date=self.now.replace(day=day))
        a, b = ORDER_STAGES[0][1], ORDER_STAGES[1][1]
        events = [event(3, a, b, 21), event(4, b, b, 22)]
        self.assertEqual(stage_state(events, ORDER_STAGES, 'order').entered_at.day, 21)
        events.append(event(2, b, a, 23))
        self.assertEqual(stage_state(events, ORDER_STAGES, 'order').entered_at.day, 23)
        self.assertEqual(stage_state([], ORDER_STAGES, 'order').stage, '')

    def test_multi_shipment_priority_and_unknown(self):
        a, b, c = (self.now.replace(day=d) for d in (25, 26, 27))
        rows = [Shipment('1', Decimal(400), calculated=c, declared=b, actual=a), Shipment('2', Decimal(350), calculated=c, declared=b), Shipment('3', Decimal(250), calculated=c)]
        result = summarize_shipments(1000, rows)
        self.assertEqual(result['first_arrival'], a)
        self.assertEqual(result['complete_arrival'], c)
        self.assertEqual(result['received_quantity'], 400)
        self.assertIsNone(summarize_shipments(1000, rows[:-1])['complete_arrival'])
        self.assertIsNone(summarize_shipments(1000, rows[:-1]+[Shipment('3', Decimal(250))])['complete_arrival'])

    def test_no_double_counting(self):
        result = residual_gio_allocations([(1, 500, 1200, None), (2, 300, 1500, None)], 400, 1000)
        self.assertEqual([(x[0], x[1]) for x in result], [(1, 100), (2, 300), (None, 200)])
