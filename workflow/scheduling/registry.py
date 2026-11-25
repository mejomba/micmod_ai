"""Explicit adapter and field registry; no operational model imports."""
from dataclasses import dataclass, field
from datetime import datetime
from .engine import Edge, SchedulingError, typed


@dataclass(frozen=True)
class ContextField:
    kind: str
    label: str
    choices: tuple = ()

    def __post_init__(self):
        if self.kind not in ('number', 'boolean', 'string', 'date'):
            raise SchedulingError('Unsupported context type')
        if any(x is None or not typed(x, self.kind) for x in self.choices):
            raise SchedulingError('Invalid context choices')

    def accepts(self, value):
        return typed(value, self.kind) and (value is None or not self.choices or value in self.choices)


@dataclass(frozen=True)
class StageState:
    stage: str
    entered_at: datetime = None
    cancelled: bool = False


@dataclass(frozen=True)
class Binding:
    workflow_key: str
    model: type
    adapter: object
    provider: object
    fields: dict
    stages: frozenset
    edges: tuple = ()
    entry_stages: frozenset = field(default_factory=frozenset)
    targets: frozenset = field(default_factory=frozenset)

    @property
    def schema(self):
        return {key: value.kind for key, value in self.fields.items()}

    def context(self, instance):
        raw = self.provider(instance)
        if not isinstance(raw, dict) or set(raw) - set(self.fields):
            raise SchedulingError('Provider returned unregistered context fields')
        values = {key: raw.get(key) for key in self.fields}
        for key, value in values.items():
            if not self.fields[key].accepts(value):
                raise SchedulingError('Invalid context value: ' + key)
        return values


class ContextRegistry:
    def __init__(self):
        self._bindings = {}
        self._models = {}

    def register(self, binding):
        if binding.workflow_key in self._bindings or binding.model in self._models:
            raise SchedulingError('Duplicate workflow registration')
        if not callable(binding.adapter) or not callable(binding.provider):
            raise SchedulingError('Adapter and provider must be callable')
        if not binding.stages or not (binding.entry_stages | binding.targets) <= binding.stages:
            raise SchedulingError('Invalid registered stages')
        if any(not isinstance(e, Edge) or e.source not in binding.stages or e.target not in binding.stages for e in binding.edges):
            raise SchedulingError('Invalid registered route')
        if any(not isinstance(f, ContextField) for f in binding.fields.values()):
            raise SchedulingError('Invalid field metadata')
        self._bindings[binding.workflow_key] = binding
        self._models[binding.model] = binding

    def by_key(self, workflow_key):
        try:
            return self._bindings[workflow_key]
        except KeyError as exc:
            raise SchedulingError('Workflow is not registered: ' + workflow_key) from exc

    def for_instance(self, instance):
        try:
            return self._models[type(instance)]
        except KeyError as exc:
            raise SchedulingError('Document type is not registered') from exc


registry = ContextRegistry()
