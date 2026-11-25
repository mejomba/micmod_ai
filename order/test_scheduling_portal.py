import json
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, Client
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from order.forecast_service import recalculate
from order.forecast_presentation import annotate_order_forecasts, filter_order_forecasts, order_forecast_cells, panel_context
from order.models import Order
from order.scheduling_seed import seed_policy
from workflow.models import WorkFlow
from workflow.scheduling.models import WorkflowForecast, WorkflowForecastRefresh, WorkflowSchedulePolicy
from workflow.scheduling.policies import clone_policy
from workflow.scheduling.registry import registry
from workflow.scheduling.editor_forms import RuleForm, CalendarForm, TransitionForm


class SchedulingPortalTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(username='scheduling_ui_admin', password=None)
        self.viewer = User.objects.create_user(username='scheduling_ui_viewer', password=None)
        self.policy, _ = seed_policy('order',user=self.admin,publish=True)
        self.draft = clone_policy(self.policy.pk,user=self.admin)
        self.binding = registry.by_key('order')
        self.order = Order.objects.create(quantity=10,production_lead_time=0,transportation_method='air')
        WorkFlow.objects.create(content_type=ContentType.objects.get_for_model(Order),object_id=self.order.pk,
            state='تایید مدیر فروش',current_state_name='تایید بازرگانی',wf_status=3,to_user=self.admin)
        self.client.force_login(self.admin)

    def url(self,name,*args):
        return reverse('scheduling:'+name,args=args)

    def grant(self,*codes):
        for code in codes:
            self.viewer.user_permissions.add(Permission.objects.get(content_type__app_label='workflow',codename=code))

    def test_index_and_detail_render(self):
        self.client.cookies['portal_scheduling_language'] = 'fa'
        response = self.client.get(self.url('index'))
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'مدیریت زمان‌بندی گردش کار')
        response = self.client.get(self.url('detail',self.policy.pk))
        self.assertContains(response,'v1')
        self.assertNotContains(response,self.url('add',self.policy.pk,'rule'))
        response = self.client.get(self.url('add',self.draft.pk,'rule'))
        self.assertContains(response,'condition-builder')
        self.assertContains(response,'scheduling-field-metadata')

    def test_permission_separation_and_read_only_published(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(self.url('index')).status_code,403)
        self.grant('view_workflowschedulepolicy')
        self.assertEqual(self.client.get(self.url('index')).status_code,200)
        self.assertEqual(self.client.post(self.url('clone',self.policy.pk)).status_code,403)
        self.assertEqual(self.client.post(self.url('publish',self.draft.pk)).status_code,403)
        self.assertEqual(self.client.get(self.url('history','order',self.order.pk)).status_code,403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(self.url('add',self.policy.pk,'policy'),{'name':'changed'}).status_code,403)
        self.policy.refresh_from_db()
        self.assertNotEqual(self.policy.name,'changed')

    def test_create_visual_rule_and_cross_version_rejected(self):
        timing = self.draft.stage_timings.get(workflow_key='packing',stage_key='draft')
        other = self.policy.stage_timings.get(workflow_key='packing',stage_key='draft')
        data = dict(stage_timing=timing.pk,name='Heavy',description='',priority=20,is_active='on',
            operation='set_duration',duration=4,condition_json=json.dumps({'field':'gio_weight_kg','operator':'gt','value':15000}))
        url = self.url('add',self.draft.pk,'rule')
        response = self.client.post(url,data)
        self.assertEqual(response.status_code,302)
        self.assertEqual(timing.rules.get(name='Heavy').effect_json,{'operation':'set_duration','value':4})
        response = self.client.post(url,dict(data,stage_timing=other.pk,name='Forbidden'))
        self.assertEqual(response.status_code,200)
        self.assertFalse(other.rules.filter(name='Forbidden').exists())

    def test_invalid_rule_and_transition_forms_do_not_raise(self):
        timing = self.draft.stage_timings.first()
        data = dict(stage_timing=timing.pk,name='Invalid',priority=0,is_active='on',
                    operation='set_duration',duration='',condition_json='{}')
        form = RuleForm(data,policy=self.draft,binding=self.binding)
        self.assertFalse(form.is_valid())
        form = RuleForm(dict(data,duration=2,condition_json='{"field":"private","operator":"eq","value":1}'),
                        policy=self.draft,binding=self.binding)
        self.assertFalse(form.is_valid())
        form = TransitionForm(dict(source='order.trade_approval',target='order.trade_approval',priority=0,
                    is_active='on',condition_json='{}'),policy=self.draft,binding=self.binding)
        form.instance.policy = self.draft
        self.assertFalse(form.is_valid())

    def test_calendar_weekdays_and_exception(self):
        data = dict(name='Weekend',code='special',timezone='Asia/Tehran',working_weekdays=['5','6','0'],is_active='on')
        response = self.client.post(self.url('add',self.draft.pk,'calendar'),data)
        self.assertEqual(response.status_code,302)
        calendar = self.draft.calendars.get(code='special')
        self.assertEqual(set(calendar.working_weekdays),{0,5,6})
        response = self.client.post(self.url('add',self.draft.pk,'exception'),dict(calendar=calendar.pk,
                   date='2026-11-26',is_working_day='on',description='Working exception'))
        self.assertEqual(response.status_code,302)
        self.assertTrue(calendar.exceptions.get().is_working_day)

    def test_preview_no_history_or_document_writes(self):
        response = self.client.post(self.url('preview',self.draft.pk),{'document_id':self.order.pk})
        self.assertEqual(response.status_code,200)
        self.assertIsNotNone(response.context['preview_result']['complete_arrival'])
        self.assertFalse(WorkflowForecast.objects.exists())
        self.order.refresh_from_db()
        self.assertIsNone(self.order.trade_commitment_date)

    def test_publish_and_apply_to_open_documents(self):
        response = self.client.post(self.url('publish',self.draft.pk),{})
        self.assertEqual(response.status_code,302)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status,'published')
        response = self.client.post(self.url('refresh_open',self.draft.pk))
        self.assertEqual(response.status_code,200)
        self.assertTrue(WorkflowForecastRefresh.objects.filter(workflow_key='order',object_id=self.order.pk,latest_policy=True).exists())
        self.assertFalse(WorkflowForecastRefresh.objects.filter(workflow_key='packing').exists())
        self.assertEqual(self.client.post(self.url('refresh_open',self.policy.pk)).status_code,403)

    def test_database_filter_sort_and_no_row_queries(self):
        forecast,_=recalculate('order',self.order.pk,reason='backfill')
        missing=Order.objects.create(quantity=10,transportation_method='air')
        qs=annotate_order_forecasts(Order.objects.all())
        found=filter_order_forecasts(qs,{'forecast_status':forecast.forecast_status}).order_by('estimated_arrive_date')
        self.assertEqual(list(found.values_list('pk',flat=True)),[self.order.pk])
        self.assertIn(missing.pk,list(filter_order_forecasts(qs,{'forecast_status':'missing'}).values_list('pk',flat=True)))
        self.assertEqual(list(filter_order_forecasts(qs,{'forecast_from':timezone.localdate(forecast.effective_estimated_at).isoformat(),
            'forecast_to':timezone.localdate(forecast.effective_estimated_at).isoformat()}).values_list('pk',flat=True)),[self.order.pk])
        obj=qs.get(pk=self.order.pk)
        with self.assertNumQueries(0):
            cells=order_forecast_cells(obj,True)
        self.assertNotEqual(cells['estimated_arrive_date'],'—')
        self.assertEqual(obj.forecast_delay,timedelta(0))

    def test_history_permission_and_selected_revision(self):
        first,_=recalculate('order',self.order.pk,reason='backfill')
        Order.objects.filter(pk=self.order.pk).update(production_lead_time=10)
        second,_=recalculate('order',self.order.pk)
        url=self.url('history','order',self.order.pk)
        response=self.client.get(url,{'revision':first.revision})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.context['selected_panel']['historical'])
        self.assertEqual(response.context['selected_panel']['current'].pk,first.pk)
        self.assertFalse(response.context['selected_panel']['actual_stages'])
        self.assertEqual(WorkflowForecast.objects.count(),2)
        restricted=panel_context(self.order,'order',self.viewer,True)
        self.assertFalse(restricted['can_history'])
        self.assertNotIn('steps',restricted)
        self.assertEqual(restricted['current'].pk,second.pk)

    def test_read_only_panel_renders_both_languages(self):
        recalculate('order',self.order.pk,reason='backfill')
        for fa, title in ((True,'زمان‌بندی رسید کالا'),(False,'Arrival scheduling')):
            context = panel_context(self.order,'order',self.admin,fa)
            output = render_to_string('order/scheduling/panel.html',context)
            self.assertIn(title,output)
            self.assertIn('data-forecast-panel',output)
            self.assertIn(self.url('history','order',self.order.pk),output)
        self.assertEqual(WorkflowForecast.objects.count(),1)

    def test_mutations_require_post_and_csrf(self):
        self.assertEqual(self.client.get(self.url('clone',self.policy.pk)).status_code,405)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        self.assertEqual(csrf_client.post(self.url('clone',self.policy.pk)).status_code,403)
        self.assertEqual(WorkflowSchedulePolicy.objects.count(),2)
