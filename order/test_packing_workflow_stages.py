"""Packing workflow stage order, groups, and legacy destination compatibility."""
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase

from core.models import Base
from order.models import Packing


EXPECTED_STAGES = [
    'پیش‌نویس',
    'تحویل شرکت حمل',
    'حمل',
    'قبض انبار',
    'تحویل اسناد',
    'اظهار',
    'ضمانتنامه',
    'ترخیص',
    'انبار',
]

EXPECTED_GROUPS = [
    'packing_user_p',
    'packing_user_dep',
    'packing_user_ship',
    'packing_user_ghabz',
    'trade_user_asnad',
    'trade_user_ezhar',
    'trade_user_zemanat',
    'trade_user_tarkhis',
    'wh_user',
]


class PackingWorkflowStagesTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = Base.get_flow_config(
            settings.BASE_DIR / '_keenthemes/view_config.json',
            'PackingView',
        )

    def test_stage_names_and_groups_match(self):
        self.assertEqual(self.config['flow_state_list'], EXPECTED_STAGES)
        self.assertEqual(self.config['flow_users_groups'], EXPECTED_GROUPS)

    def test_old_stage_names_resolve_to_new(self):
        self.assertEqual(Packing.normalize_workflow_state_name('DEP'), 'تحویل شرکت حمل')
        self.assertEqual(Packing.normalize_workflow_state_name('10%'), 'قبض انبار')
        self.assertEqual(Packing.normalize_workflow_state_name('ترخیص گمرک'), 'ترخیص')

    def test_group_matches_current_and_legacy_names(self):
        self.assertEqual(
            Packing.workflow_group_for_state('اظهار گمرکی'),
            'trade_user_ezhar',
        )
        self.assertEqual(
            Packing.workflow_group_for_state('ضمانتنامه'),
            'trade_user_zemanat',
        )

    def test_legacy_clearance_destination_skips_new_guarantee_stage(self):
        packing = Packing(pk=123)
        old_transition = SimpleNamespace(
            state='اظهار گمرکی',
            current_state_name='ترخیص گمرک',
            wf_status=3,
        )
        with (
            patch('workflow.models.WorkFlow.objects.filter') as queryset,
            patch('django.contrib.contenttypes.models.ContentType.objects.get_for_model'),
        ):
            queryset.return_value.order_by.return_value.last.return_value = old_transition
            self.assertEqual(packing.workflow_state_index(), 7)

    def test_old_transition_without_destination_still_skips_guarantee(self):
        packing = Packing(pk=123)
        transition = SimpleNamespace(
            state='اظهار گمرکی',
            current_state_name=None,
            wf_status=3,
        )
        with (
            patch('workflow.models.WorkFlow.objects.filter') as queryset,
            patch('django.contrib.contenttypes.models.ContentType.objects.get_for_model'),
        ):
            queryset.return_value.order_by.return_value.last.return_value = transition
            self.assertEqual(packing.workflow_state_index(), 7)

    def test_new_guarantee_destination_is_stage_six(self):
        packing = Packing(pk=123)
        transition = SimpleNamespace(
            state='اظهار',
            current_state_name='ضمانتنامه',
            wf_status=3,
        )
        with (
            patch('workflow.models.WorkFlow.objects.filter') as queryset,
            patch('django.contrib.contenttypes.models.ContentType.objects.get_for_model'),
        ):
            queryset.return_value.order_by.return_value.last.return_value = transition
            self.assertEqual(packing.workflow_state_index(), 6)
