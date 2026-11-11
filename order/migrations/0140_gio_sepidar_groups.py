"""Track every GIO Sepidar vendor/currency send independently."""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('order', '0139_packing_user_changer_group'),
    ]

    operations = [
        migrations.CreateModel(
            name='GIOSepidarGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('group_key', models.CharField(max_length=255)),
                ('status', models.CharField(
                    max_length=10, default='pending',
                    choices=[
                        ('pending', 'Pending'), ('sending', 'Sending'),
                        ('success', 'Success'), ('failed', 'Rejected'),
                        ('unknown', 'Needs manual reconciliation'),
                    ],
                )),
                ('invoice_id', models.BigIntegerField(blank=True, null=True)),
                ('invoice_number', models.CharField(max_length=64, blank=True, null=True)),
                ('receipt_id', models.BigIntegerField(blank=True, null=True)),
                ('receipt_number', models.CharField(max_length=64, blank=True, null=True)),
                ('voucher_id', models.BigIntegerField(blank=True, null=True)),
                ('voucher_number', models.CharField(max_length=64, blank=True, null=True)),
                ('items_snapshot', models.JSONField(default=list)),
                ('request_payload', models.JSONField(default=dict)),
                ('response_payload', models.JSONField(default=dict)),
                ('attempt_count', models.PositiveIntegerField(default=0)),
                ('last_error', models.TextField(blank=True, default='')),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('gio', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='sepidar_groups', to='order.gio',
                )),
            ],
        ),
        migrations.AddConstraint(
            model_name='giosepidargroup',
            constraint=models.UniqueConstraint(
                fields=('gio', 'group_key'), name='unique_gio_sepidar_group',
            ),
        ),
    ]
