"""Extend existing transport choices without changing stored values."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('order', '0145_gio_manual_weight')]

    operations = [
        migrations.AlterField(
            model_name='order', name='transportation_method',
            field=models.CharField(max_length=64, choices=[('express', 'express'), ('air', 'air'), ('sea', 'sea'), ('road', 'road'), ('rail', 'rail')], default='air', null=True, blank=True, verbose_name='روش حمل'),
        ),
        migrations.AlterField(
            model_name='packing', name='shipment_type',
            field=models.CharField(max_length=255, choices=[('express', 'express'), ('air', 'air'), ('sea', 'sea'), ('road', 'road'), ('rail', 'rail')], null=True, blank=True, verbose_name='نوع حمل'),
        ),
    ]
