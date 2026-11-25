"""Read-only deployment diagnostics; never creates or recalculates forecasts."""
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone
from workflow.scheduling.engine import SchedulingError
from workflow.scheduling.models import WorkflowForecast, WorkflowForecastRefresh
from workflow.scheduling.policies import select_policy
from workflow.scheduling.registry import registry
from workflow.scheduling.scheduler import compile_policy
from order.scheduling_rules import POLICY_CODE


class Command(BaseCommand):
    help = 'Check scheduling database guards, effective policies and queue without writes.'

    def handle(self,*args,**options):
        issues=[]
        self.stdout.write('Database vendor: '+connection.vendor)
        if connection.vendor != 'postgresql':
            issues.append('Production scheduling requires PostgreSQL.')
        else:
            tables = ('workflowschedulepolicy','workflowcalendar','workflowcalendarexception',
                'workflowstagetiming','workflowtimingrule','workflowscheduletransition',
                'workflowforecast','workflowforecaststep','workflowforecastanchor')
            with connection.cursor() as cursor:
                cursor.execute('SHOW server_version')
                self.stdout.write('PostgreSQL: '+str(cursor.fetchone()[0]))
                for name in tables:
                    table='workflow_'+name
                    cursor.execute("""SELECT tgenabled FROM pg_trigger
                        WHERE tgrelid=to_regclass(%s) AND tgname='wf_sched_guard' AND NOT tgisinternal""",[table])
                    row=cursor.fetchone()
                    if row is None or row[0] not in ('O','A'):
                        issues.append('Missing/disabled guard: '+table)
            self.stdout.write('Guard tables checked: '+str(len(tables)))
        for key in ('order','packing'):
            policy=select_policy(key,POLICY_CODE)
            if policy is None:
                issues.append('Missing effective policy: '+key)
                continue
            try:
                compile_policy(policy,registry.by_key(key))
            except (SchedulingError,ValueError,TypeError,KeyError) as exc:
                issues.append('Invalid policy %s: %s' % (key,exc))
            self.stdout.write('%s effective policy: v%s (ID %s)' % (key,policy.version,policy.pk))
        pending=WorkflowForecastRefresh.objects.count()
        retrying=WorkflowForecastRefresh.objects.filter(attempts__gt=0).count()
        delayed=WorkflowForecastRefresh.objects.filter(available_at__gt=timezone.now()).count()
        self.stdout.write('Pending jobs: %s; retrying: %s; delayed: %s' % (pending,retrying,delayed))
        self.stdout.write('Current forecasts: %s' % WorkflowForecast.objects.filter(is_current=True).count())
        for issue in issues:
            self.stderr.write(issue)
        if issues:
            raise CommandError('Scheduling deployment checks failed.')
        self.stdout.write(self.style.SUCCESS('Scheduling deployment checks passed (not a replacement for tests).'))
