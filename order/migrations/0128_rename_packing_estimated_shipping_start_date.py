# Rename the existing Packing column without losing stored dates.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0127_remove_packing_source_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='packing',
            old_name='estimated_delivery_date',
            new_name='estimated_shipping_start_date',
        ),
        migrations.AlterField(
            model_name='packing',
            name='estimated_shipping_start_date',
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name='تاریخ پیش‌بینی شروع حمل بار',
            ),
        ),
    ]
