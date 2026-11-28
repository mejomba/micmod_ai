"""Business policy defaults and pure stage/quantity helpers (not engine code)."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from workflow.scheduling.engine import Calendar, Component, Edge, Rule, SchedulingError
from workflow.scheduling.configuration import Policy, StageTiming
from workflow.scheduling.registry import ContextField, StageState

ORDER_STAGES = (
    ('trade_approval', 'تایید بازرگانی', 1),
    ('engineering_approval', 'تایید مهندس', 2),
    ('supplier_dispatch', 'ارسال به تامین کننده', 0),
    ('supplier_approval', 'تایید تامین کننده', 2),
    ('final_trade_approval', 'تایید نهایی بازرگانی', 1),
    ('payment_gio', 'پرداخت / PACKING / GIO', 2),
)
PACKING_STAGES = (
    ('draft', 'پیش‌نویس', 1), ('handover', 'تحویل شرکت حمل', 2),
    ('shipping', 'حمل', 0), ('warehouse_bill', 'قبض انبار', 0),
    ('documents', 'تحویل اسناد', 2), ('declaration', 'اظهار', 1),
    ('guarantee', 'ضمانتنامه', 2), ('clearance', 'ترخیص', 1),
    ('warehouse', 'انبار', 1), ('done', 'اتمام کار', 0),
)
TARGET = 'packing.warehouse'
POLICY_CODE = 'central-arrival'
METHODS = ('air', 'sea', 'road', 'rail')
FIELDS = {
    'has_price_inquiry': ContextField('boolean', 'Price inquiry selected'),
    'production_lead_time': ContextField('number', 'Production lead time'),
    'shipment_type': ContextField('string', 'Transport method', METHODS),
    'gio_weight_kg': ContextField('number', 'Effective GIO weight (kg)'),
}


def transport_method(value):
    value = 'air' if value == 'express' else value
    return value if value in METHODS else None


def stage_keys(workflow, rows):
    return tuple(workflow + '.' + row[0] for row in rows)


ORDER_DONE = 'order.done'
ORDER_KEYS = stage_keys('order', ORDER_STAGES)
PACKING_KEYS = stage_keys('packing', PACKING_STAGES)
KEYS = ORDER_KEYS + PACKING_KEYS


def initial_policy(workflow_key, timezone_name='Asia/Tehran'):
    calendars = {'working': Calendar(timezone_name, frozenset((0, 1, 2, 5, 6))),
                 'calendar': Calendar(timezone_name)}
    keys = KEYS if workflow_key == 'order' else PACKING_KEYS
    timings = {}
    for key, (_, _, duration) in zip(KEYS, ORDER_STAGES + PACKING_STAGES):
        if key in keys:
            timings[key] = StageTiming(Component(duration, 'calendar' if key == 'packing.shipping' else 'working'))
    def add(key, rules):
        timings[key] = StageTiming(timings[key].base, tuple(rules))
    if workflow_key == 'order':
        add('order.trade_approval', [Rule('no-inquiry', {'field': 'has_price_inquiry', 'operator': 'eq', 'value': False}, {'operation': 'add_duration', 'value': 3})])
        add('order.final_trade_approval', [Rule('production', {}, {'operation': 'add_field_duration', 'field': 'production_lead_time', 'calendar': 'calendar'})])
    add('packing.draft', [Rule('heavy-gio', {'field': 'gio_weight_kg', 'operator': 'gt', 'value': 15000}, {'operation': 'set_duration', 'value': 4})])
    # Use explicit method predicates even when the default happens to be zero.
    for key, values in {'handover': (2, 10, 10, 10), 'shipping': (0, 45, 45, 50),
                        'warehouse_bill': (0, 2, 2, 2), 'clearance': (1, 5, 5, 5),
                        'warehouse': (1, 4, 4, 4)}.items():
        add('packing.' + key, [Rule(key + '-' + method, {'field': 'shipment_type', 'operator': 'eq', 'value': method},
            {'operation': 'set_duration', 'value': value}) for method, value in zip(METHODS, values)])
    unknown = {'production_lead_time': {'mode': 'USE_DEFAULT', 'value': 5},
               'shipment_type': {'mode': 'MARK_INCOMPLETE'},
               'gio_weight_kg': {'mode': 'USE_DEFAULT', 'value': 0}}
    return Policy(workflow_key, calendars, timings, tuple(Edge(a, b) for a, b in zip(keys, keys[1:])), unknown)


def normalize_label(value):
    return (value or '').replace('ي', 'ی').replace('ك', 'ک').replace('\u200c', ' ').strip()


def stage_state(events, rows, workflow, normalize=normalize_label, cancelled=False, created_at=None):
    """Only stage changes start a new period; unrecognized states fail closed."""
    keys = [workflow + '.' + r[0] for r in rows]
    labels = {normalize(r[1]): i for i, r in enumerate(rows)}
    current, entered = None, None
    for event in events:
        status = event.wf_status
        if status not in (1, 2, 3, 5):
            continue
        target = labels.get(normalize(event.current_state_name))
        if target is None and event.current_state_name:
            current, entered = None, None
            continue
        if target is None:
            source = labels.get(normalize(event.state))
            if source is not None:
                target = max(0, source - 1) if status == 2 else min(len(keys)-1, source+1) if status == 3 else source
                if workflow == 'packing' and status == 3 and event.state == 'اظهار گمرکی':
                    target = keys.index('packing.clearance')
                if workflow == 'packing' and status == 2 and event.state == 'ترخیص گمرک':
                    target = keys.index('packing.declaration')
        if target is None:
            current, entered = None, None
        elif current != target or status in (2, 3, 5):
            current, entered = target, event.created_date
    if current is None and not events and workflow == 'packing':
        current, entered = 0, created_at
    return StageState(keys[current] if current is not None else '', entered, cancelled)


def quantity(value):
    try:
        n = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(0)
    return n if n.is_finite() and n > 0 else Decimal(0)


@dataclass(frozen=True)
class Shipment:
    key: str
    quantity: Decimal
    calculated: object = None
    declared: object = None
    actual: object = None
    status: str = 'incomplete'
    details: object = None

    @property
    def effective(self):
        return self.actual or self.declared or self.calculated

    @property
    def source(self):
        return 'actual' if self.actual else 'declared' if self.declared else 'calculated' if self.calculated else 'none'


def summarize_shipments(required, shipments):
    required = quantity(required)
    covered = sum((s.quantity for s in shipments), Decimal(0))
    dates = [s.effective for s in shipments if s.quantity > 0 and s.effective is not None]
    arrived = sum((s.quantity for s in shipments if s.actual), Decimal(0))
    # Over-allocation is a discrepancy, not permission to silently count extra units.
    complete = bool(required and covered == required and all(s.effective is not None for s in shipments if s.quantity > 0))
    return {'first_arrival': min(dates) if dates else None,
            'complete_arrival': max(dates) if complete else None,
            'received_quantity': min(required, arrived),
            'remaining_quantity': max(Decimal(0), required - arrived),
            'allocation_discrepancy': covered != required,
            'status': 'actual' if complete and arrived == required else 'provisional' if complete and any(s.status == 'provisional' or not s.calculated and not s.actual for s in shipments) else 'estimated' if complete else 'incomplete'}


def residual_gio_allocations(gios, packed, required):
    """Consume existing packed quantity once; unknown association is explicit.

    GIOs are (id, amount, weight, date). A deterministic FIFO allocation is
    only a forecast assumption, never a persisted GIO/Packing association.
    """
    packed, required = quantity(packed), quantity(required)
    left = max(Decimal(0), required - packed)
    consumed = packed
    result = []
    for key, amount, weight, entered in gios:
        amount = quantity(amount)
        used = min(consumed, amount)
        consumed -= used
        amount = min(left, amount - used)
        if amount:
            result.append((key, amount, weight, entered))
            left -= amount
    if left:
        result.append((None, left, None, None))
    return result
