"""Audit superuser reconciliations of uncertain Sepidar sends."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ('order', '0140_gio_sepidar_groups'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='giosepidargroup',
            name='status',
            field=models.CharField(
                max_length=10, default='pending', choices=[
                    ('pending', 'Pending'), ('sending', 'Sending'),
                    ('success', 'Success'), ('failed', 'Rejected'),
                    ('unknown', 'Needs manual reconciliation'),
                    ('reviewed', 'Manually reviewed; explicit retry permitted'),
                ],
            ),
        ),
        migrations.CreateModel(
            name='GIOSepidarManualReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('reason', models.TextField()),
                ('previous_error', models.TextField(blank=True, default='')),
                ('previous_request_payload', models.JSONField(default=dict)),
                ('previous_response_payload', models.JSONField(default=dict)),
                ('previous_attempt_count', models.PositiveIntegerField()),
                ('confirmations', models.JSONField(default=dict)),
                ('group', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, related_name='manual_reviews',
                    to='order.giosepidargroup',
                )),
                ('reviewer', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='gio_sepidar_manual_reviews', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-created_at', '-pk']},
        ),
    ]
