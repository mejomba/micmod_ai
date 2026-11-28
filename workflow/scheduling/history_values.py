"""JSON-safe and stable day-granularity history values (no ORM dependencies)."""
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
import json


_PREDICTED_KEYS = {'estimated_at', 'estimated_start_at', 'estimated_end_at',
                   'calculated', 'calculated_estimated_at', 'effective_estimated_at',
                   'first_arrival', 'complete_arrival', 'start', 'end'}


def json_value(value, *, day_zone=None, key=None):
    if isinstance(value, datetime):
        if value.utcoffset() is None:
            raise ValueError('History requires timezone-aware timestamps')
        if day_zone is not None and key in _PREDICTED_KEYS:
            return value.astimezone(day_zone).date().isoformat()
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError('Non-finite history number')
        return format(value.normalize(), 'f') if value else '0'
    if is_dataclass(value) and not isinstance(value, type):
        value = {field.name: getattr(value, field.name) for field in fields(value)}
    if isinstance(value, dict):
        return {str(k): json_value(v, day_zone=day_zone, key=k) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        if key == 'routes':
            return [[json_value(end, day_zone=day_zone, key='estimated_at'),
                     json_value(steps, day_zone=day_zone)] for end, steps in value]
        return [json_value(v, day_zone=day_zone, key=key) for v in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise TypeError('Unsupported history value: ' + type(value).__name__)


def fingerprint(value, day_zone):
    """Ignore intraday jitter in predicted timestamps, never in actual anchors."""
    payload = json.dumps(json_value(value, day_zone=day_zone), sort_keys=True,
                         separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    return sha256(payload.encode('utf-8')).hexdigest()


def arrival_dates(result):
    """Derive complete-order dates; preserve per-shipment sources in snapshot.

    A mixed-source total is a composite estimate, not a user declaration of
    the whole order. Incomplete totals must never expose a complete date.
    """
    shipments = [s for s in result['shipments'] if s.quantity > 0]
    complete = result.get('complete_arrival')
    status = result['status']
    if status == 'cancelled' or not shipments or complete is None:
        return dict(calculated_estimated_at=None, declared_at=None, actual_at=None,
                    forecast_status='cancelled' if status == 'cancelled' else 'incomplete')
    pending = [s for s in shipments if s.actual is None]
    calculated_dates = [s.actual or s.calculated for s in shipments]
    calculated = max(calculated_dates) if all(calculated_dates) and pending else None
    if not pending:
        return dict(calculated_estimated_at=None, declared_at=None, actual_at=complete,
                    forecast_status='actual')
    if all(s.declared is not None for s in pending):
        return dict(calculated_estimated_at=calculated, declared_at=complete, actual_at=None,
                    forecast_status='declared')
    return dict(calculated_estimated_at=complete, declared_at=None, actual_at=None,
                forecast_status=status if status in ('estimated', 'provisional') else 'provisional')
