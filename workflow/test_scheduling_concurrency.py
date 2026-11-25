"""Run only against a disposable PostgreSQL test database."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase, override_settings
from order.forecast_service import recalculate
from order.models import Order
from order.scheduling_seed import seed_policy
from workflow.models import WorkFlow
from workflow.scheduling.models import WorkflowForecast, WorkflowSchedulePolicy
from workflow.scheduling.policies import clone_policy


@skipUnless(connection.vendor == 'postgresql','PostgreSQL row locking required')
@override_settings(WORKFLOW_SCHEDULING_AUTO_ENABLED=False)
class SchedulingConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(username='schedule_concurrency_admin', password=None)
        self.policy,_ = seed_policy('order',user=self.user,publish=True)
        self.order = Order.objects.create(quantity=10,production_lead_time=0,transportation_method='air')
        self.ct = ContentType.objects.get_for_model(Order)
        WorkFlow.objects.create(content_type=self.ct,object_id=self.order.pk,state='تایید مدیر فروش',
            current_state_name='تایید بازرگانی',wf_status=3,to_user=self.user)

    def concurrently(self,operation):
        barrier = Barrier(2,timeout=10)
        def worker():
            close_old_connections()
            try:
                with connections['default'].cursor() as cursor:
                    cursor.execute("SET lock_timeout = '10s'")
                barrier.wait()
                return operation()
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker) for _ in range(2)]
            return [future.result(timeout=30) for future in futures]

    def test_two_clones_receive_distinct_versions(self):
        policy_id, user_id = self.policy.pk, self.user.pk
        def clone():
            user = get_user_model().objects.get(pk=user_id)
            return clone_policy(policy_id,user=user).version
        self.assertEqual(sorted(self.concurrently(clone)),[2,3])
        self.assertEqual(WorkflowSchedulePolicy.objects.filter(workflow_key='order',code=self.policy.code).count(),3)

    def test_two_refreshes_create_only_one_revision(self):
        pk = self.order.pk
        def refresh():
            forecast, changed = recalculate('order',pk,reason='backfill')
            return forecast.pk, changed
        results = self.concurrently(refresh)
        self.assertEqual(results[0][0],results[1][0])
        self.assertEqual(sorted(r[1] for r in results),[False,True])
        self.assertEqual(WorkflowForecast.objects.filter(content_type=self.ct,object_id=pk).count(),1)
