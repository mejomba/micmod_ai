from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('extra_data', '0130_alter_item_shop_limit_quantity_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='legal_profiles',
            field=models.JSONField(blank=True, default=list, verbose_name='پروفایل‌های حقوقی'),
        ),
    ]
