# Nullable Order brand (no implicit default) and two independent row labels.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('order', '0135_packingitem_volume'),
        ('extra_data', '0130_alter_item_shop_limit_quantity_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='order', name='brand',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='orders_with_brand', to='extra_data.brand',
                verbose_name='Brand',
            ),
        ),
        migrations.AddField(
            model_name='packingitem', name='category',
            field=models.CharField(blank=True, null=True, max_length=150, verbose_name='Category'),
        ),
        migrations.AddField(
            model_name='packingitem', name='main_category',
            field=models.CharField(blank=True, null=True, max_length=150, verbose_name='Main Category'),
        ),
    ]
