# Generated for Packing transportation header fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0026_packingitem_carton_number'),
    ]

    operations = [
        migrations.AddField(
            model_name='packing',
            name='bl_date',
            field=models.DateField(blank=True, null=True, verbose_name='bl_date'),
        ),
        migrations.AddField(
            model_name='packing',
            name='destination',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='destination'),
        ),
        migrations.AddField(
            model_name='packing',
            name='origin',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='origin'),
        ),
        migrations.AddField(
            model_name='packing',
            name='transportation_company',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='transportation_company'),
        ),
    ]
