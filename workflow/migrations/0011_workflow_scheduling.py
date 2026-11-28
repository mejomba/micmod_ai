"""Add the scheduling tables without modifying legacy Workflow rows."""
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone

class Migration(migrations.Migration):
    dependencies = [
        ('workflow', '0010_workflow_current_state_name'),
        ('contenttypes', '0002_remove_content_type_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name='WorkflowSchedulePolicy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('code', models.CharField(max_length=100)),
                ('workflow_key', models.CharField(max_length=100)),
                ('version', models.PositiveIntegerField(default=1)),
                ('status', models.CharField(max_length=10, choices=[('draft', 'draft'), ('published', 'published'), ('archived', 'archived')], default='draft')),
                ('is_active', models.BooleanField(default=False)),
                ('effective_from', models.DateTimeField(null=True, blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name='created_schedule_policies', null=True, blank=True)),
                ('published_at', models.DateTimeField(null=True, blank=True)),
                ('published_by', models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name='published_schedule_policies', null=True, blank=True)),
                ('description', models.TextField(blank=True)),
                ('unknown_policies', models.JSONField(default=dict, blank=True)),
                ('route_mode', models.CharField(max_length=12, choices=[('alternatives', 'alternatives'), ('parallel', 'parallel')], default='alternatives')),
            ],
            options={
                'constraints': [
                    models.UniqueConstraint(fields=["workflow_key","code","version"], name='wf_sched_policy_version'),
                    models.CheckConstraint(check=models.Q(version__gt=0), name='wf_sched_policy_version_gt0'),
                    models.CheckConstraint(check=models.Q(is_active=False) | models.Q(status='published'), name='wf_sched_active_published'),
                    models.CheckConstraint(check=models.Q(status='draft') | models.Q(published_at__isnull=False), name='wf_sched_published_at'),
                ],
                'indexes': [
                    models.Index(fields=["workflow_key","status","is_active","effective_from"], name='wf_sched_policy_lookup'),
                ],
                'permissions': [('publish_schedule_policy', 'Can publish workflow schedule policies')],
            },
        ),
        migrations.CreateModel(
            name='WorkflowCalendar',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('policy', models.ForeignKey('workflow.workflowschedulepolicy', on_delete=models.PROTECT, related_name='calendars')),
                ('name', models.CharField(max_length=200)),
                ('code', models.CharField(max_length=100)),
                ('timezone', models.CharField(max_length=64, default='Asia/Tehran')),
                ('working_weekdays', models.JSONField(default=list, blank=True)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'constraints': [
                    models.UniqueConstraint(fields=["policy","code"], name='wf_sched_cal_code'),
                ],
            },
        ),
        migrations.CreateModel(
            name='WorkflowCalendarException',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('calendar', models.ForeignKey('workflow.workflowcalendar', on_delete=models.PROTECT, related_name='exceptions')),
                ('date', models.DateField()),
                ('is_working_day', models.BooleanField(default=False)),
                ('description', models.CharField(max_length=255, blank=True)),
            ],
            options={
                'constraints': [
                    models.UniqueConstraint(fields=["calendar","date"], name='wf_sched_cal_exception'),
                ],
            },
        ),
        migrations.CreateModel(
            name='WorkflowStageTiming',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('policy', models.ForeignKey('workflow.workflowschedulepolicy', on_delete=models.PROTECT, related_name='stage_timings')),
                ('workflow_key', models.CharField(max_length=100)),
                ('stage_key', models.CharField(max_length=100)),
                ('default_duration', models.PositiveIntegerField(default=0)),
                ('duration_unit', models.CharField(max_length=10, choices=[('day', 'day')], default='day')),
                ('calendar', models.ForeignKey('workflow.workflowcalendar', on_delete=models.PROTECT, related_name='stage_timings')),
                ('remaining_time_strategy', models.CharField(max_length=16, choices=[('elapsed', 'elapsed'), ('restart', 'restart')], default='elapsed')),
                ('overdue_duration', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'constraints': [
                    models.UniqueConstraint(fields=["policy","workflow_key","stage_key"], name='wf_sched_stage_unique'),
                    models.CheckConstraint(check=models.Q(default_duration__lte=36600, overdue_duration__lte=36600), name='wf_sched_duration_max'),
                ],
            },
        ),
        migrations.CreateModel(
            name='WorkflowTimingRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stage_timing', models.ForeignKey('workflow.workflowstagetiming', on_delete=models.CASCADE, related_name='rules')),
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('condition_json', models.JSONField(default=dict, blank=True)),
                ('effect_json', models.JSONField(default=dict, blank=True)),
                ('priority', models.IntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'indexes': [
                    models.Index(fields=["stage_timing","is_active","priority"], name='wf_sched_rule_priority'),
                ],
            },
        ),
        migrations.CreateModel(
            name='WorkflowScheduleTransition',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('policy', models.ForeignKey('workflow.workflowschedulepolicy', on_delete=models.PROTECT, related_name='transitions')),
                ('source_workflow', models.CharField(max_length=100)),
                ('source_stage', models.CharField(max_length=100)),
                ('target_workflow', models.CharField(max_length=100)),
                ('target_stage', models.CharField(max_length=100)),
                ('condition_json', models.JSONField(default=dict, blank=True)),
                ('priority', models.IntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'indexes': [
                    models.Index(fields=["policy","source_workflow","source_stage"], name='wf_sched_route_source'),
                ],
            },
        ),
        migrations.CreateModel(
            name='WorkflowForecast',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content_type', models.ForeignKey('contenttypes.contenttype', on_delete=models.PROTECT, related_name='workflow_forecasts')),
                ('object_id', models.PositiveBigIntegerField()),
                ('policy', models.ForeignKey('workflow.workflowschedulepolicy', on_delete=models.PROTECT, related_name='forecasts')),
                ('policy_version', models.PositiveIntegerField()),
                ('revision', models.PositiveIntegerField(default=1)),
                ('source_stage', models.CharField(max_length=200)),
                ('target_stage', models.CharField(max_length=200)),
                ('target_event', models.CharField(max_length=5, choices=[('entry', 'entry'), ('exit', 'exit')], default='exit')),
                ('calculated_at', models.DateTimeField(default=timezone.now)),
                ('as_of', models.DateTimeField()),
                ('initial_estimated_at', models.DateTimeField(null=True, blank=True)),
                ('initial_is_backfill', models.BooleanField(default=False)),
                ('calculated_estimated_at', models.DateTimeField(null=True, blank=True)),
                ('declared_at', models.DateTimeField(null=True, blank=True)),
                ('effective_estimated_at', models.DateTimeField(null=True, blank=True)),
                ('actual_at', models.DateTimeField(null=True, blank=True)),
                ('forecast_source', models.CharField(max_length=12, choices=[('calculated', 'calculated'), ('declared', 'declared'), ('actual', 'actual'), ('none', 'none')], default='none')),
                ('forecast_status', models.CharField(max_length=12, choices=[('estimated', 'estimated'), ('provisional', 'provisional'), ('incomplete', 'incomplete'), ('declared', 'declared'), ('actual', 'actual'), ('cancelled', 'cancelled')], default='incomplete')),
                ('context_snapshot', models.JSONField(default=dict, blank=True)),
                ('assumptions', models.JSONField(default=list, blank=True)),
                ('policy_snapshot', models.JSONField(default=dict, blank=True)),
                ('calculation_reason', models.CharField(max_length=100, blank=True)),
                ('calculation_version', models.CharField(max_length=32, default='1')),
                ('fingerprint', models.CharField(max_length=64, blank=True)),
                ('is_current', models.BooleanField(default=True)),
            ],
            options={
                'constraints': [
                    models.UniqueConstraint(fields=["content_type","object_id","target_stage","target_event","revision"], name='wf_sched_forecast_revision'),
                    models.UniqueConstraint(fields=["content_type","object_id","target_stage","target_event"], name='wf_sched_forecast_current', condition=models.Q(is_current=True)),
                    models.CheckConstraint(check=models.Q(revision__gt=0, policy_version__gt=0, object_id__gt=0), name='wf_sched_revision_gt0'),
                ],
                'indexes': [
                    models.Index(fields=["is_current","effective_estimated_at"], name='wf_sched_forecast_date'),
                    models.Index(fields=["is_current","forecast_status"], name='wf_sched_forecast_status'),
                ],
            },
        ),
        migrations.CreateModel(
            name='WorkflowForecastStep',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('forecast', models.ForeignKey('workflow.workflowforecast', on_delete=models.CASCADE, related_name='steps')),
                ('sequence', models.PositiveIntegerField()),
                ('workflow_key', models.CharField(max_length=100)),
                ('stage_key', models.CharField(max_length=100)),
                ('estimated_start_at', models.DateTimeField(null=True, blank=True)),
                ('estimated_end_at', models.DateTimeField(null=True, blank=True)),
                ('actual_start_at', models.DateTimeField(null=True, blank=True)),
                ('actual_end_at', models.DateTimeField(null=True, blank=True)),
                ('standard_duration', models.PositiveIntegerField(default=0)),
                ('elapsed_duration', models.PositiveIntegerField(default=0)),
                ('remaining_duration', models.PositiveIntegerField(default=0)),
                ('calendar', models.ForeignKey('workflow.workflowcalendar', on_delete=models.PROTECT, related_name='forecast_steps', null=True, blank=True)),
                ('duration_components', models.JSONField(default=list, blank=True)),
                ('applied_rules', models.JSONField(default=list, blank=True)),
                ('calculation_details', models.JSONField(default=dict, blank=True)),
                ('status', models.CharField(max_length=32, blank=True)),
                ('assumptions', models.JSONField(default=list, blank=True)),
            ],
            options={
                'constraints': [
                    models.UniqueConstraint(fields=["forecast","sequence"], name='wf_sched_forecast_step'),
                ],
                'ordering': ["sequence"],
            },
        ),
        migrations.CreateModel(
            name='WorkflowForecastAnchor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('forecast', models.ForeignKey('workflow.workflowforecast', on_delete=models.CASCADE, related_name='anchors')),
                ('stage_key', models.CharField(max_length=200)),
                ('target_event', models.CharField(max_length=5, choices=[('entry', 'entry'), ('exit', 'exit')], default='exit')),
                ('anchor_type', models.CharField(max_length=12, choices=[('actual', 'actual'), ('declared', 'declared'), ('calculated', 'calculated')])),
                ('anchor_datetime', models.DateTimeField()),
                ('source_content_type', models.ForeignKey('contenttypes.contenttype', on_delete=models.PROTECT, related_name='workflow_forecast_anchors', null=True, blank=True)),
                ('source_object_id', models.PositiveBigIntegerField(null=True, blank=True)),
                ('description', models.TextField(blank=True)),
            ],
            options={
                'constraints': [
                    models.CheckConstraint(check=(models.Q(source_content_type__isnull=True, source_object_id__isnull=True) | models.Q(source_content_type__isnull=False, source_object_id__gt=0, source_object_id__isnull=False)), name='wf_sched_anchor_source_pair'),
                ],
            },
        ),
    ]
