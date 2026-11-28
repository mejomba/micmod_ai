from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from order.scheduling_seed import seed_policy


class Command(BaseCommand):
    help = 'Seed initial order/packing scheduling policies without overwriting existing policies.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--publish', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        user = get_user_model().objects.filter(username=options['username'], is_active=True).first()
        if not user or not user.has_perm('workflow.add_workflowschedulepolicy'):
            raise CommandError('An active authorized user is required.')
        if options['publish'] and not user.has_perm('workflow.publish_schedule_policy'):
            raise CommandError('Publication permission required.')
        for key in ('order', 'packing'):
            policy, created = seed_policy(key, user=user, publish=options['publish'])
            self.stdout.write('%s: %s (v%s, %s)' % (key, 'created' if created else 'unchanged',
                                                   policy.version, policy.status))
