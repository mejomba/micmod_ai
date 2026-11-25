"""Persist manual GIO weight separately from the calculated value."""
from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('order', '0144_remove_legacy_packing_fields')]

    operations = [
        migrations.AddField(
            model_name='gio', name='manual_weight_kg',
            field=models.DecimalField(
                blank=True, null=True, max_digits=18, decimal_places=6,
                validators=[MinValueValidator(0)], verbose_name='Manual GIO weight (kg)',
            ),
        ),
        migrations.AddConstraint(
            model_name='gio',
            constraint=models.CheckConstraint(
                check=models.Q(manual_weight_kg__isnull=True) | models.Q(manual_weight_kg__gte=0),
                name='order_gio_manual_weight_nonneg',
            ),
        ),
    ]
