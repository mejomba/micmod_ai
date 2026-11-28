from datetime import datetime, date, timezone as utc
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from workflow.scheduling.models import (WorkflowSchedulePolicy, WorkflowCalendar,
    WorkflowStageTiming, WorkflowTimingRule)
from workflow.scheduling.registry import ContextRegistry, Binding, ContextField, StageState
from workflow.scheduling.engine import Edge
from workflow.scheduling.scheduler import Scheduler, publish_configured_policy


class Document:
    pass


class ConfiguredSchedulerTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 25, 9, tzinfo=utc.utc)
        self.user = get_user_model().objects.create_superuser(username='scheduler_admin', password=None)
        self.registry = ContextRegistry()
        self.registry.register(Binding('demo', Document, lambda obj: StageState('demo.start', self.now),
            lambda obj: {'days': 3}, {'days': ContextField('number', 'Days')},
            frozenset(('demo.start', 'demo.end')), (Edge('demo.start', 'demo.end'),),
            frozenset(('demo.start',)), frozenset(('demo.end',))))
        self.policy = WorkflowSchedulePolicy.objects.create(name='Demo', code='standard', workflow_key='demo')
        calendar = WorkflowCalendar.objects.create(policy=self.policy, code='days', name='All',
            timezone='UTC', working_weekdays=list(range(7)))
        self.start = WorkflowStageTiming.objects.create(policy=self.policy, workflow_key='demo',
            stage_key='start', calendar=calendar, default_duration=1)
        WorkflowStageTiming.objects.create(policy=self.policy, workflow_key='demo',
            stage_key='end', calendar=calendar, default_duration=2)
        self.rule = WorkflowTimingRule.objects.create(stage_timing=self.start, name='extra',
            effect_json={'operation': 'add_field_duration', 'field': 'days'})

    def test_preview_and_published_forecast(self):
        engine = Scheduler(self.registry)
        result = engine.preview(Document(), policy=self.policy, target='demo.end', as_of=self.now)
        self.assertEqual(result.estimated_at.date(), date(2026, 12, 1))
        publish_configured_policy(self.policy.pk, user=self.user, effective_from=self.now,
                                  context_registry=self.registry)
        result = engine.forecast(Document(), policy_code='standard', target='demo.end', as_of=self.now)
        self.assertEqual(result.estimated_at.date(), date(2026, 12, 1))

    def test_publication_rejects_unregistered_field(self):
        self.rule.effect_json = {'operation': 'add_field_duration', 'field': 'private'}
        self.rule.save(update_fields=['effect_json'])
        with self.assertRaises(ValidationError):
            publish_configured_policy(self.policy.pk, user=self.user, context_registry=self.registry)
        self.policy.refresh_from_db()
        self.assertEqual(self.policy.status, 'draft')
