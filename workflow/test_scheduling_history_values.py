from datetime import datetime, timezone, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase
from workflow.scheduling.history_values import arrival_dates, fingerprint, json_value


class HistoryValuesTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 25, 9, tzinfo=timezone.utc)
        self.later = self.now + timedelta(days=1)

    def shipment(self, calculated=None, declared=None, actual=None):
        return SimpleNamespace(quantity=Decimal('1'), calculated=calculated,
                               declared=declared, actual=actual)

    def test_fingerprint_intraday_and_actual_precision(self):
        a = {'estimated_at': self.now, 'actual_at': self.now}
        b = {'estimated_at': self.now + timedelta(hours=1), 'actual_at': self.now}
        self.assertEqual(fingerprint(a, timezone.utc), fingerprint(b, timezone.utc))
        b['actual_at'] += timedelta(seconds=1)
        self.assertNotEqual(fingerprint(a, timezone.utc), fingerprint(b, timezone.utc))
        self.assertEqual(fingerprint({'routes': [(self.now, ())]}, timezone.utc),
                         fingerprint({'routes': [(self.now + timedelta(hours=1), ())]}, timezone.utc))
        b = dict(a, estimated_at=self.later)
        self.assertNotEqual(fingerprint(a, timezone.utc), fingerprint(b, timezone.utc))

    def test_json_decimal_and_aware_date(self):
        self.assertEqual(json_value(Decimal('15000.0010')), '15000.001')
        with self.assertRaises(ValueError):
            json_value(datetime(2026, 11, 25))

    def test_mixed_is_not_whole_order_declaration(self):
        data = dict(shipments=[self.shipment(declared=self.now), self.shipment(calculated=self.later)],
                    complete_arrival=self.later, status='provisional')
        dates = arrival_dates(data)
        self.assertEqual(dates['calculated_estimated_at'], self.later)
        self.assertIsNone(dates['declared_at'])

    def test_all_pending_declared_with_actual_partial(self):
        data = dict(shipments=[self.shipment(actual=self.now), self.shipment(declared=self.later)],
                    complete_arrival=self.later, status='provisional')
        dates = arrival_dates(data)
        self.assertEqual(dates['declared_at'], self.later)
        self.assertEqual(dates['forecast_status'], 'declared')

    def test_incomplete_and_cancelled(self):
        for status in ('incomplete', 'cancelled'):
            dates = arrival_dates(dict(shipments=[self.shipment(calculated=self.now)],
                                       complete_arrival=None, status=status))
            self.assertIsNone(dates['calculated_estimated_at'])
            self.assertEqual(dates['forecast_status'], status)

    def test_actual_only_when_complete(self):
        dates = arrival_dates(dict(shipments=[self.shipment(actual=self.now)],
                                   complete_arrival=self.now, status='actual'))
        self.assertEqual(dates['actual_at'], self.now)
        self.assertIsNone(dates['calculated_estimated_at'])
