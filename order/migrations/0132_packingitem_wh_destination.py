from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('order', '0131_packing_finance_viewer_group')]

    operations = [
        migrations.AddField(
            model_name='packingitem',
            name='wh_destination',
            field=models.CharField('انبار مقصد', max_length=16, null=True, blank=True),
        ),
    ]
