"""Audit of manually entered Sepidar invoice, receipt and voucher references."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ('order', '0141_gio_sepidar_manual_review'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='GIOSepidarManualDocumentEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(
                    default=django.utils.timezone.now, editable=False)),
                ('reason', models.TextField()),
                ('previous_status', models.CharField(max_length=10, blank=True)),
                ('previous_documents', models.JSONField(default=dict)),
                ('new_documents', models.JSONField(default=dict)),
                ('group', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='manual_document_entries', to='order.giosepidargroup')),
                ('actor', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='gio_sepidar_manual_document_entries',
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at', '-pk']},
        ),
    ]
