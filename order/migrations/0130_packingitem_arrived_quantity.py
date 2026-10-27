from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('order', '0129_packing_workflow_nine_stages'),
    ]

    operations = [
        migrations.AddField(
            model_name='packingitem',
            name='arrived_quantity',
            field=models.FloatField(blank=True, null=True, verbose_name='arrived_quantity'),
        ),
    ]
