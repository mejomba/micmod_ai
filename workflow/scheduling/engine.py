"""Pure day-based scheduling primitives; no Django or business-model imports.

Dates use the calendar's local timezone. The start date is excluded, the
end date included; zero days never shifts the input. Time of day is retained.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo


class SchedulingError(ValueError):
    pass


def days(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise SchedulingError('Duration must be a non-negative whole number of days')
    try:
        n = Decimal(str(value))
        if not n.is_finite() or n < 0 or n != n.to_integral_value() or n > 36600:
            raise SchedulingError('Invalid day duration')
    except InvalidOperation as exc:
        raise SchedulingError('Invalid day duration') from exc
    return int(n)


@dataclass(frozen=True)
class Calendar:
    timezone: str
    weekdays: frozenset = frozenset(range(7))
    exceptions: dict = field(default_factory=dict)

    def __post_init__(self):
        ZoneInfo(self.timezone)
        if not self.weekdays or not self.weekdays <= set(range(7)):
            raise SchedulingError('Calendar needs valid working weekdays')
        if any(type(k) is not date or type(v) is not bool for k, v in self.exceptions.items()):
            raise SchedulingError('Invalid calendar exception')

    def local(self, value):
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise SchedulingError('Timezone-aware datetime required')
        return value.astimezone(ZoneInfo(self.timezone))

    def is_working_day(self, value):
        return self.exceptions.get(value, value.weekday() in self.weekdays)

    def add(self, start, duration):
        duration = days(duration)
        local = self.local(start)
        if not duration:
            return start
        while duration:
            local += timedelta(days=1)
            if self.is_working_day(local.date()):
                duration -= 1
        return local

    def elapsed(self, start, end):
        first, last = self.local(start).date(), self.local(end).date()
        total = 0
        while first < last:
            first += timedelta(days=1)
            total += self.is_working_day(first)
        return total

    def next_working_day(self, value):
        return self.add(value, 1)


OPERATORS = {'eq', 'ne', 'gt', 'gte', 'lt', 'lte', 'in', 'not_in', 'is_null', 'is_not_null'}
NUMERIC = (int, float, Decimal)


def typed(value, kind):
    if value is None:
        return True
    if kind == 'number':
        return type(value) in NUMERIC and Decimal(str(value)).is_finite()
    return {'boolean': bool, 'string': str, 'date': date}.get(kind) is type(value)


def matches(node, context, schema, depth=0):
    """Evaluate a bounded declarative expression against an explicit field registry."""
    if depth > 12 or not isinstance(node, dict):
        raise SchedulingError('Invalid condition')
    if not node:
        return True
    if set(node) in ({'and'}, {'or'}, {'not'}):
        key = next(iter(node))
        children = node[key]
        if key == 'not':
            return not matches(children, context, schema, depth + 1)
        if not isinstance(children, list) or not 1 <= len(children) <= 50:
            raise SchedulingError('Invalid condition group')
        results = [matches(child, context, schema, depth + 1) for child in children]
        return all(results) if key == 'and' else any(results)
    if set(node) - {'field', 'operator', 'value'}:
        raise SchedulingError('Invalid condition keys')
    name, op = node.get('field'), node.get('operator')
    if not isinstance(name, str) or name not in schema or name not in context:
        raise SchedulingError('Unregistered or missing context field')
    if not isinstance(op, str) or op not in OPERATORS:
        raise SchedulingError('Invalid condition operator')
    actual, expected, kind = context[name], node.get('value'), schema[name]
    if not typed(actual, kind):
        raise SchedulingError('Invalid context type')
    if op in ('is_null', 'is_not_null'):
        if 'value' in node:
            raise SchedulingError('Null operator cannot have a value')
        return (actual is None) == (op == 'is_null')
    if 'value' not in node:
        raise SchedulingError('Condition value required')
    if op in ('in', 'not_in'):
        if not isinstance(expected, list) or len(expected) > 100 or any(not typed(x, kind) for x in expected):
            raise SchedulingError('Invalid membership values')
        return (actual in expected) == (op == 'in')
    if not typed(expected, kind):
        raise SchedulingError('Invalid condition value type')
    if op == 'eq':
        return actual == expected
    if op == 'ne':
        return actual != expected
    if kind not in ('number', 'date') or expected is None:
        raise SchedulingError('Invalid ordered comparison')
    if actual is None:
        return False
    return {'gt': actual > expected, 'gte': actual >= expected,
            'lt': actual < expected, 'lte': actual <= expected}[op]


@dataclass(frozen=True)
class Component:
    duration: int
    calendar: str

    def __post_init__(self):
        days(self.duration)


@dataclass(frozen=True)
class Rule:
    key: str
    condition: dict
    effect: dict
    priority: int = 0
    active: bool = True


def apply_rules(base, rules, context, schema, calendars):
    """Highest-priority replacement wins; independent additions keep their calendars."""
    if base.calendar not in calendars:
        raise SchedulingError('Unknown base calendar')
    valid = []
    for rule in rules:
        if not rule.active:
            continue
        effect = rule.effect
        op = effect.get('operation')
        if op not in ('set_duration', 'add_duration', 'add_field_duration', 'set_calendar', 'skip_stage'):
            raise SchedulingError('Invalid rule operation')
        allowed = {'operation', 'value', 'field', 'calendar', 'unit'}
        if set(effect) - allowed or effect.get('unit', 'day') != 'day':
            raise SchedulingError('Unsupported effect')
        if effect.get('calendar', base.calendar) not in calendars:
            raise SchedulingError('Unknown rule calendar')
        if op in ('set_duration', 'add_duration'):
            days(effect.get('value'))
        if op == 'set_calendar' and 'calendar' not in effect:
            raise SchedulingError('Calendar required')
        if op == 'add_field_duration' and schema.get(effect.get('field')) != 'number':
            raise SchedulingError('Duration field must be registered numeric')
        if matches(rule.condition, context, schema):
            valid.append(rule)
    valid.sort(key=lambda r: (-r.priority, r.key))

    def winner(op):
        candidates = [r for r in valid if r.effect['operation'] == op]
        if len(candidates) > 1 and candidates[0].priority == candidates[1].priority:
            raise SchedulingError('Conflicting equally prioritized rules')
        return candidates[0] if candidates else None

    replacement, calendar_rule = winner('set_duration'), winner('set_calendar')
    skipped = winner('skip_stage')
    if skipped:
        return (), (skipped.key,)
    effect = replacement.effect if replacement else {}
    calendar = effect.get('calendar', base.calendar)
    if calendar_rule:
        calendar = calendar_rule.effect['calendar']
    components = [Component(days(effect.get('value', base.duration)), calendar)]
    applied = [r.key for r in (replacement, calendar_rule) if r]
    for rule in valid:
        effect = rule.effect
        op = effect['operation']
        if op not in ('add_duration', 'add_field_duration'):
            continue
        value = context.get(effect['field']) if op == 'add_field_duration' else effect['value']
        components.append(Component(days(value), effect.get('calendar', calendar)))
        applied.append(rule.key)
    return tuple(components), tuple(applied)


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    condition: dict = field(default_factory=dict)
    priority: int = 0
    active: bool = True


def resolve_routes(source, target, edges, context, schema, limit=128):
    """Return alternatives explicitly, never silently choose shortest route."""
    graph = {}
    for edge in edges:
        if edge.active and matches(edge.condition, context, schema):
            graph.setdefault(edge.source, []).append(edge)
    for outgoing in graph.values():
        outgoing.sort(key=lambda e: (-e.priority, e.target))
    result = []
    visits = 0

    def walk(node, path):
        nonlocal visits
        visits += 1
        if visits > 10000 or len(path) > 256:
            raise SchedulingError('Route search limit exceeded')
        if node in path:
            raise SchedulingError('Cycle in forecast route')
        path = path + (node,)
        if node == target:
            if path not in result:
                result.append(path)
            if len(result) > limit:
                raise SchedulingError('Too many forecast routes')
            return
        for edge in graph.get(node, []):
            walk(edge.target, path)

    walk(source, ())
    if not result:
        raise SchedulingError('Target is unreachable')
    return tuple(result)


@dataclass(frozen=True)
class Step:
    stage: str
    start: datetime
    end: datetime
    components: tuple
    remaining: tuple
    overdue: bool = False


def forecast_route(route, timings, calendars, as_of, entered_at=None,
                   target_event='exit', overdue_days=None):
    """Forecast one explicit route. Completed stages must not be in route.

    Components run sequentially; elapsed time is consumed using their own
    calendars. Only the current stage can consume prior elapsed time.
    """
    if target_event not in ('entry', 'exit') or not route:
        raise SchedulingError('Invalid forecast target')
    if as_of.utcoffset() is None or (entered_at and entered_at.utcoffset() is None):
        raise SchedulingError('Timezone-aware datetime required')
    if entered_at and entered_at > as_of:
        raise SchedulingError('Stage entry is in the future')
    cursor = as_of
    steps = []
    stages = route if target_event == 'exit' else route[:-1]
    for index, stage in enumerate(stages):
        if stage not in timings:
            raise SchedulingError('Missing stage timing')
        components = tuple(timings[stage])
        remaining = []
        anchor = entered_at if index == 0 and entered_at else cursor
        for component in components:
            cal = calendars[component.calendar]
            end = cal.add(anchor, component.duration)
            spent = min(days(component.duration), cal.elapsed(anchor, cursor))
            remaining.append(Component(days(component.duration) - spent, component.calendar))
            anchor = end
        overdue = bool(components and index == 0 and entered_at and anchor < as_of)
        if overdue and overdue_days and stage in overdue_days:
            extra = overdue_days[stage]
            remaining.append(extra)
        start = cursor
        for component in remaining:
            cursor = calendars[component.calendar].add(cursor, component.duration)
        steps.append(Step(stage, start, cursor, components, tuple(remaining), overdue))
    return cursor, tuple(steps)


def forecast_routes(routes, timings, calendars, as_of, entered_at=None,
                    target_event='exit', mode='alternatives', overdue_days=None):
    """Return route results and a date only when unambiguous or all routes required.

    Parallel mode is explicit: callers must supply the complete required paths.
    Nested AND/OR join policies are not inferred from the graph.
    """
    if mode not in ('alternatives', 'parallel'):
        raise SchedulingError('Unknown route policy')
    results = tuple(forecast_route(route, timings, calendars, as_of, entered_at,
                                   target_event, overdue_days) for route in routes)
    if not results:
        raise SchedulingError('No forecast routes')
    effective = max(result[0] for result in results) if mode == 'parallel' or len(results) == 1 else None
    return effective, results
