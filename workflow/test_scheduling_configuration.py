from datetime import datetime, date, timezone
from unittest import TestCase
from workflow.scheduling.engine import Calendar, Component, Edge, Rule, SchedulingError
from workflow.scheduling.registry import ContextRegistry, Binding, ContextField, StageState
from workflow.scheduling.configuration import Policy, StageTiming, validate_policy, calculate


class Document:
    pass


class ConfigurationTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 25, 9, tzinfo=timezone.utc)
        self.state = StageState('quote.review', self.now)
        self.fields = {'method': ContextField('string', 'Method', ('air', 'sea')),
                       'lead': ContextField('number', 'Lead'),
                       'due': ContextField('date', 'Due')}
        self.binding = Binding('quote', Document, lambda obj: self.state,
                               lambda obj: {'method': 'air', 'lead': 0}, self.fields,
                               frozenset(('quote.review', 'contract.done')),
                               (Edge('quote.review', 'contract.done'),),
                               frozenset(('quote.review',)), frozenset(('contract.done',)))
        self.calendars = {'work': Calendar('UTC', frozenset((0, 1, 2, 5, 6))), 'all': Calendar('UTC')}
        self.base = {'quote.review': StageTiming(Component(1, 'work'), (
            Rule('lead', {}, {'operation': 'add_field_duration', 'field': 'lead', 'calendar': 'all'}),)),
            'contract.done': StageTiming(Component(1, 'all'))}

    def policy(self, **kwargs):
        params = dict(workflow_key='quote', calendars=self.calendars, timings=self.base)
        params.update(kwargs)
        return validate_policy(Policy(**params), self.binding)

    def forecast(self, policy, **kwargs):
        context = self.binding.context(Document())
        context.update(kwargs)
        return calculate(policy, self.binding, self.state, context, 'contract.done', 'exit', self.now)

    def test_registry_and_cross_workflow(self):
        registry = ContextRegistry()
        registry.register(self.binding)
        self.assertIs(registry.for_instance(Document()), self.binding)
        with self.assertRaises(SchedulingError):
            registry.register(self.binding)
        result = self.forecast(self.policy())
        self.assertEqual(result.estimated_at.date(), date(2026, 11, 29))
        self.assertEqual(result.status, 'estimated')

    def test_default_null_and_zero(self):
        policy = self.policy(unknown={'lead': {'mode': 'USE_DEFAULT', 'value': 5}})
        result = self.forecast(policy, lead=None)
        self.assertEqual(result.estimated_at.date(), date(2026, 12, 4))
        self.assertEqual(result.status, 'provisional')
        self.assertEqual(result.scenarios[0].assumptions[0]['value'], 5)
        self.assertEqual(self.forecast(policy, lead=0).estimated_at.date(), date(2026, 11, 29))

    def test_unknown_scenarios_and_block(self):
        policy = self.policy(unknown={'lead': {'mode': 'USE_SCENARIOS', 'values': [0, 5]}})
        result = self.forecast(policy, lead=None)
        self.assertIsNone(result.estimated_at)
        self.assertEqual(len(result.scenarios), 2)
        for mode in ('BLOCK_FORECAST', 'MARK_INCOMPLETE'):
            result = self.forecast(self.policy(unknown={'lead': {'mode': mode}}), lead=None)
            self.assertIsNone(result.estimated_at)
            self.assertEqual(result.scenarios[0].assumptions[0]['mode'], mode)

    def test_inactive_rule_and_unused_field(self):
        policy = self.policy(timings={'quote.review': StageTiming(Component(1, 'work'), (
            Rule('disabled', {'field': 'unknown'}, {}, active=False),
            Rule('sea', {'field': 'method', 'operator': 'eq', 'value': 'sea'},
                 {'operation': 'add_field_duration', 'field': 'lead'}),)),
            'contract.done': self.base['contract.done']})
        self.assertIsNotNone(self.forecast(policy, lead=None).estimated_at)

    def test_conflict_and_disjoint(self):
        def rule(key, value):
            return Rule(key, {'field': 'method', 'operator': 'eq', 'value': value}, {'operation': 'set_duration', 'value': 3})
        self.base['quote.review'] = StageTiming(Component(1, 'work'), (rule('a', 'air'), rule('b', 'sea')))
        self.assertIsNotNone(self.forecast(self.policy()).estimated_at)
        self.base['quote.review'] = StageTiming(Component(1, 'work'), (rule('a', 'air'), rule('b', 'air')))
        with self.assertRaises(SchedulingError):
            self.policy()

    def test_invalid_field_and_cycle(self):
        with self.assertRaises(SchedulingError):
            self.policy(edges=(Edge('contract.done', 'quote.review'),))
        self.base['quote.review'] = StageTiming(Component(1, 'work'), (Rule('bad', {'field': '__dict__', 'operator': 'eq', 'value': 2}, {'operation': 'skip_stage'}),))
        with self.assertRaises(SchedulingError):
            self.policy()

    def test_iso_date_and_null_predicate(self):
        self.base['quote.review'] = StageTiming(Component(1, 'work'), (
            Rule('date', {'field': 'due', 'operator': 'is_null'}, {'operation': 'set_duration', 'value': 2}),))
        self.assertEqual(self.forecast(self.policy()).estimated_at.date(), date(2026, 11, 30))
        self.base['quote.review'] = StageTiming(Component(1, 'work'), (
            Rule('date', {'field': 'due', 'operator': 'eq', 'value': '2026-11-25'}, {'operation': 'set_duration', 'value': 2}),))
        self.assertEqual(self.forecast(self.policy(), due=date(2026, 11, 25)).estimated_at.date(), date(2026, 11, 30))

    def test_cancelled(self):
        result = calculate(self.policy(), self.binding, StageState('quote.review', cancelled=True), {}, 'contract.done', 'exit', self.now)
        self.assertEqual(result.status, 'cancelled')
        self.assertIsNone(result.estimated_at)
