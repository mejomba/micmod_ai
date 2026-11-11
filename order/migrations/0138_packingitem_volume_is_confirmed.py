"""Distinguish manually confirmed packing volume from test-generated values."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('order', '0137_packing_currency_exchange_rates'),
    ]

    operations = [
        migrations.AddField(
            model_name='packingitem',
            name='volume_is_confirmed',
            field=models.BooleanField(
                default=False, verbose_name='حجم واقعی تأییدشده',
            ),
        ),
    ]
