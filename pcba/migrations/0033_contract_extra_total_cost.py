from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pcba', '0032_contract_assembly_type_contract_contract_end_date_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='contract',
            name='extra_total_cost',
            field=models.PositiveBigIntegerField(
                default=0, verbose_name='هزینه‌های مازاد کل قرارداد'
            ),
        ),
    ]
