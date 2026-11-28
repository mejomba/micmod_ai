"""Queue schema only; no historical calculations in migrations."""
from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):
    dependencies = [('workflow', '0011_workflow_scheduling')]
    operations = [
        migrations.CreateModel(
            name='WorkflowForecastRefresh',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('workflow_key', models.CharField(max_length=100)),
                ('object_id', models.PositiveBigIntegerField()),
                ('reason', models.CharField(max_length=100)),
                ('requested_at', models.DateTimeField(default=timezone.now)),
                ('available_at', models.DateTimeField(default=timezone.now)),
                ('attempts', models.PositiveIntegerField(default=0)),
                ('last_error', models.TextField(blank=True)),
                ('latest_policy', models.BooleanField(default=False)),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=['workflow_key', 'object_id'], name='wf_forecast_refresh_unique')],
                'indexes': [models.Index(fields=['available_at', 'id'], name='wf_forecast_refresh_due')],
            },
        ),
    ]
