"""Validate and execute a configured, generic policy without database access."""
from dataclasses import dataclass, field
from datetime import date
from itertools import combinations, product
from functools import lru_cache
from .engine import (Calendar, Component, Edge, Rule, SchedulingError, days,
                     matches, apply_rules, resolve_routes, forecast_routes)


@dataclass(frozen=True)
class StageTiming:
    base: Component
    rules: tuple = ()
    strategy: str = 'elapsed'
    overdue: int = 0


@dataclass(frozen=True)
class Policy:
    workflow_key: str
    calendars: dict
    timings: dict
    edges: tuple = ()
    unknown: dict = field(default_factory=dict)
    route_mode: str = 'alternatives'


def condition_fields(node):
    if not isinstance(node, dict):
        raise SchedulingError('Invalid condition')
    if not node:
        return set()
    if 'and' in node or 'or' in node:
        children = node.get('and', node.get('or'))
        return set().union(*(condition_fields(child) for child in children))
    if 'not' in node:
        return condition_fields(node['not'])
    if node.get('operator') in ('is_null', 'is_not_null'):
        return set()
    return {node['field']}


def normalize_condition(node, binding, depth=0):
    if not isinstance(node, dict) or depth > 12:
        raise SchedulingError('Invalid condition')
    if not node:
        return {}
    if set(node) in ({'and'}, {'or'}, {'not'}):
        key = next(iter(node))
        value = node[key]
        if key == 'not':
            return {key: normalize_condition(value, binding, depth + 1)}
        if not isinstance(value, list) or not 1 <= len(value) <= 50:
            raise SchedulingError('Invalid condition group')
        return {key: [normalize_condition(v, binding, depth + 1) for v in value]}
    key = node.get('field')
    if not isinstance(key, str) or key not in binding.fields:
        raise SchedulingError('Unregistered context field')
    spec = binding.fields[key]
    result = dict(node)
    def convert(value):
        if spec.kind == 'date' and isinstance(value, str):
            try:
                value = date.fromisoformat(value)
            except ValueError as exc:
                raise SchedulingError('Invalid ISO date') from exc
        if not spec.accepts(value):
            raise SchedulingError('Invalid value for ' + key)
        return value
    if 'value' in node:
        if node.get('operator') in ('in', 'not_in') and isinstance(node['value'], list):
            result['value'] = [convert(v) for v in node['value']]
        else:
            result['value'] = convert(node['value'])
    matches(result, dict.fromkeys(binding.fields), binding.schema)
    return result


def disjoint(a, b):
    """Conservative proof for common equality/membership conditions."""
    if a.get('field') is None or a.get('field') != b.get('field'):
        return False
    def values(node):
        if node.get('operator') == 'eq':
            return {node['value']}
        if node.get('operator') == 'in':
            return set(node['value'])
        if node.get('operator') == 'is_null':
            return {None}
        return None
    x, y = values(a), values(b)
    return x is not None and y is not None and x.isdisjoint(y)


def _unknown_values(spec, config):
    if not isinstance(config, dict):
        raise SchedulingError('Invalid unknown field policy')
    mode = config.get('mode')
    if mode == 'USE_DEFAULT' and set(config) == {'mode', 'value'}:
        values = [config['value']]
    elif mode == 'USE_SCENARIOS' and set(config) == {'mode', 'values'}:
        values = config['values']
        if not isinstance(values, list) or not 1 <= len(values) <= 16 or any(v is None for v in values):
            raise SchedulingError('Invalid scenario values')
    elif mode in ('MARK_INCOMPLETE', 'BLOCK_FORECAST') and set(config) == {'mode'}:
        return mode, []
    else:
        raise SchedulingError('Invalid unknown field policy')
    converted = []
    for value in values:
        if spec.kind == 'date' and isinstance(value, str):
            try:
                value = date.fromisoformat(value)
            except ValueError as exc:
                raise SchedulingError('Invalid ISO date default') from exc
        if not spec.accepts(value):
            raise SchedulingError('Invalid unknown policy value')
        converted.append(value)
    return mode, converted


def validate_policy(policy, binding):
    if policy.workflow_key != binding.workflow_key or policy.route_mode not in ('alternatives', 'parallel'):
        raise SchedulingError('Policy does not match registry')
    if not policy.timings or len(policy.timings) > 256 or not set(policy.timings) <= binding.stages:
        raise SchedulingError('Unknown or missing stage timings')
    for key, config in policy.unknown.items():
        if key not in binding.fields:
            raise SchedulingError('Unknown policy field: ' + key)
        _unknown_values(binding.fields[key], config)
    normalized = {}
    for stage, timing in policy.timings.items():
        if timing.base.calendar not in policy.calendars or timing.strategy not in ('elapsed', 'restart'):
            raise SchedulingError('Invalid stage calendar or strategy')
        days(timing.overdue)
        rules = []
        for rule in timing.rules:
            if not rule.active:
                continue
            condition = normalize_condition(rule.condition, binding)
            effect = rule.effect
            if not isinstance(effect, dict):
                raise SchedulingError('Invalid rule effect')
            op = effect.get('operation')
            required = {'set_duration': {'value'}, 'add_duration': {'value'}, 'add_field_duration': {'field'}, 'set_calendar': {'calendar'}, 'skip_stage': set()}
            if not isinstance(op, str) or op not in required or not required[op] <= effect.keys() or effect.keys() - ({'operation', 'unit', 'calendar'} | required[op]):
                raise SchedulingError('Invalid effect fields')
            if op == 'add_field_duration' and binding.schema.get(effect.get('field')) != 'number':
                raise SchedulingError('Duration field must be numeric')
            if op in ('add_duration', 'set_duration'):
                days(effect['value'])
            if effect.get('unit', 'day') != 'day' or effect.get('calendar', timing.base.calendar) not in policy.calendars:
                raise SchedulingError('Invalid effect calendar or unit')
            rules.append(Rule(rule.key, condition, effect, rule.priority))
        for a, b in combinations(rules, 2):
            op = a.effect['operation']
            if op in ('set_duration', 'set_calendar', 'skip_stage') and op == b.effect['operation'] and a.priority == b.priority and not disjoint(a.condition, b.condition):
                raise SchedulingError('Potential same-priority conflict at ' + stage)
        normalized[stage] = StageTiming(timing.base, tuple(rules), timing.strategy, timing.overdue)
    # A configured source replaces that source's default outgoing edges.
    overridden = {e.source for e in policy.edges if e.active}
    edges = tuple(e for e in binding.edges if e.source not in overridden) + policy.edges
    active = tuple(Edge(e.source, e.target, normalize_condition(e.condition, binding), e.priority)
                   for e in edges if e.active)
    graph = {key: set() for key in normalized}
    for e in active:
        if e.source not in graph or e.target not in graph:
            raise SchedulingError('Route endpoint has no active timing')
        graph[e.source].add(e.target)
    visiting, visited = set(), set()
    def visit(node):
        if node in visiting:
            raise SchedulingError('Cycle in policy graph')
        if node not in visited:
            visiting.add(node)
            for other in graph[node]:
                visit(other)
            visiting.remove(node)
            visited.add(node)
    for node in graph:
        visit(node)
    @lru_cache(maxsize=None)
    def reach(source):
        seen = {source}
        for next_ in graph[source]:
            seen |= reach(next_)
        return seen
    if not (binding.entry_stages | binding.targets) <= graph.keys():
        raise SchedulingError('Required entry or target timing missing')
    if binding.entry_stages:
        reachable = set().union(*(reach(e) for e in binding.entry_stages))
        if set(graph) - reachable:
            raise SchedulingError('Unreachable stage in policy graph')
    for entry in binding.entry_stages:
        if binding.targets - reach(entry):
            raise SchedulingError('Required target is unreachable')
    return Policy(policy.workflow_key, policy.calendars, normalized, active, policy.unknown, policy.route_mode)


@dataclass(frozen=True)
class Scenario:
    context: dict
    assumptions: tuple
    estimated_at: object = None
    routes: tuple = ()
    applied_rules: dict = field(default_factory=dict)
    status: str = 'incomplete'


@dataclass(frozen=True)
class ForecastResult:
    source_stage: str
    target_stage: str
    target_event: str
    status: str
    estimated_at: object
    scenarios: tuple


def _expand(policy, binding, context, fields, assumptions=()):
    dimensions = []
    notes = list(assumptions)
    for key in sorted(fields):
        if context[key] is not None or any(n['field'] == key for n in notes):
            continue
        mode, values = _unknown_values(binding.fields[key], policy.unknown.get(key, {'mode': 'MARK_INCOMPLETE'}))
        if not values:
            return [(context, tuple(notes + [{'field': key, 'mode': mode}]), mode)]
        dimensions.append((key, mode, values))
    count = 1
    for _, _, values in dimensions:
        count *= len(values)
        if count > 64:
            raise SchedulingError('Scenario limit exceeded')
    result = []
    for values in product(*(d[2] for d in dimensions)):
        updated = dict(context)
        extra = list(notes)
        for (key, mode, _), value in zip(dimensions, values):
            updated[key] = value
            extra.append({'field': key, 'mode': mode, 'value': value})
        result.append((updated, tuple(extra), None))
    return result


def calculate(policy, binding, state, context, target, target_event, as_of):
    if target_event not in ('entry', 'exit') or target not in policy.timings or state.stage not in policy.timings:
        raise SchedulingError('Invalid forecast endpoints')
    if state.cancelled:
        return ForecastResult(state.stage, target, target_event, 'cancelled', None, ())
    if as_of.utcoffset() is None or (state.entered_at and state.entered_at.utcoffset() is None):
        raise SchedulingError('Timezone-aware datetime required')
    # Only evaluate rules on future routes; never add durations from past stages.
    potential = resolve_routes(state.stage, target, [Edge(e.source, e.target) for e in policy.edges], {}, {})
    relevant = set().union(*map(set, potential))
    edges = [e for e in policy.edges if e.source in relevant and e.target in relevant]
    fields = set().union(*(condition_fields(e.condition) for e in edges))
    scenarios = []
    for ctx, notes, blocked in _expand(policy, binding, context, fields):
        if blocked:
            scenarios.append(Scenario(ctx, notes))
            continue
        try:
            routes = resolve_routes(state.stage, target, edges, ctx, binding.schema)
        except SchedulingError as exc:
            if str(exc) != 'Target is unreachable':
                raise
            scenarios.append(Scenario(ctx, notes, status='unreachable'))
            continue
        stages = set().union(*(set(r if target_event == 'exit' else r[:-1]) for r in routes))
        fields = set()
        for stage in stages:
            for rule in policy.timings[stage].rules:
                fields |= condition_fields(rule.condition)
        expanded = []
        for values, assumptions, blocked in _expand(policy, binding, ctx, fields, notes):
            if blocked:
                expanded.append((values, assumptions, blocked))
                continue
            duration_fields = {r.effect['field'] for stage in stages for r in policy.timings[stage].rules
                               if r.effect['operation'] == 'add_field_duration'
                               and matches(r.condition, values, binding.schema)}
            expanded.extend(_expand(policy, binding, values, duration_fields, assumptions))
            if len(expanded) > 64:
                raise SchedulingError('Scenario limit exceeded')
        for values, assumptions, blocked in expanded:
            if len(scenarios) >= 64:
                raise SchedulingError('Scenario limit exceeded')
            if blocked:
                scenarios.append(Scenario(values, assumptions))
                continue
            timings, applied, overdue = {}, {}, {}
            for stage in stages:
                timing = policy.timings[stage]
                timings[stage], applied[stage] = apply_rules(timing.base, timing.rules, values, binding.schema, policy.calendars)
                if timing.overdue:
                    overdue[stage] = Component(timing.overdue, timing.base.calendar)
            entered = state.entered_at if policy.timings[state.stage].strategy == 'elapsed' else None
            end, details = forecast_routes(routes, timings, policy.calendars, as_of, entered, target_event, policy.route_mode, overdue)
            status = 'incomplete' if end is None else 'provisional' if assumptions or entered is None or any(s.overdue for _, steps in details for s in steps) else 'estimated'
            scenarios.append(Scenario(values, assumptions, end, details, applied, status))
    effective = scenarios[0].estimated_at if len(scenarios) == 1 else None
    status = scenarios[0].status if len(scenarios) == 1 else 'incomplete'
    if status == 'unreachable':
        status = 'incomplete'
    return ForecastResult(state.stage, target, target_event, status, effective, tuple(scenarios))
