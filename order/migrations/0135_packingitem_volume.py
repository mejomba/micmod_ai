# Optional decimal Packing item volume. This migration is not run automatically.
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('order', '0134_packing_registration_and_carton_quantity'),
    ]

    operations = [
        migrations.AddField(
            model_name='packingitem',
            name='volume',
            field=models.DecimalField(
                blank=True, decimal_places=6, max_digits=18, null=True,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name='Volume',
            ),
        ),
    ]
