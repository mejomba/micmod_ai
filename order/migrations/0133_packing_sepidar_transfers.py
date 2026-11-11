from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0132_packingitem_wh_destination'),
    ]

    operations = [
        migrations.CreateModel(
            name='PackingSepidarTransfer',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('transfer_type', models.CharField(max_length=10, choices=[('normal', 'Normal'), ('damaged', 'Damaged')])),
                ('source_stock_ref', models.PositiveIntegerField()),
                ('destination_stock_ref', models.PositiveIntegerField()),
                ('status', models.CharField(max_length=10, default='pending', choices=[('pending', 'Pending'), ('sending', 'Sending'), ('success', 'Success'), ('failed', 'Failed'), ('unknown', 'Needs reconciliation')])),
                ('delivery_id', models.BigIntegerField(null=True, blank=True)),
                ('delivery_number', models.CharField(max_length=64, null=True, blank=True)),
                ('receipt_id', models.BigIntegerField(null=True, blank=True)),
                ('receipt_number', models.CharField(max_length=64, null=True, blank=True)),
                ('request_payload', models.JSONField(default=dict)),
                ('response_payload', models.JSONField(default=dict)),
                ('attempt_count', models.PositiveIntegerField(default=0)),
                ('last_error', models.TextField(blank=True, default='')),
                ('sent_at', models.DateTimeField(null=True, blank=True)),
                ('packing', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='sepidar_transfers', to='order.packing')),
            ],
        ),
        migrations.CreateModel(
            name='PackingSepidarTransferItem',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('item_ref', models.PositiveIntegerField()),
                ('quantity', models.DecimalField(max_digits=18, decimal_places=4)),
                ('packing_item', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='sepidar_transfer_lines', to='order.packingitem')),
                ('transfer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='order.packingsepidartransfer')),
            ],
        ),
        migrations.AddConstraint(
            model_name='packingsepidartransfer',
            constraint=models.UniqueConstraint(fields=('packing', 'transfer_type', 'destination_stock_ref'), name='unique_packing_sepidar_transfer'),
        ),
        migrations.AddConstraint(
            model_name='packingsepidartransferitem',
            constraint=models.UniqueConstraint(fields=('transfer', 'packing_item'), name='unique_packing_transfer_item'),
        ),
    ]
