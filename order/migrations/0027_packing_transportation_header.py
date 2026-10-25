# Generated for Packing transportation header fields

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('transportation', '0014_rename_arrive_time_transportationcalender_arrive_date_and_more'),
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
            name='transportation_calendar',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='order_packings',
                to='transportation.transportationcalender',
                verbose_name='transportation_calendar',
            ),
        ),
        migrations.AddField(
            model_name='packing',
            name='transportation_company',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='transportation_company'),
        ),
    ]
