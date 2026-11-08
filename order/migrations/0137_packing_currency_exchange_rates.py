# Store the user's per-currency conversion rates; do NOT store totals.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('order', '0136_order_brand_packingitem_independent_categories'),
    ]

    operations = [
        migrations.AddField(
            model_name='packing', name='currency_exchange_rates',
            field=models.JSONField(
                blank=True, default=dict, verbose_name='نرخ‌های تبدیل ارز',
            ),
        ),
    ]
