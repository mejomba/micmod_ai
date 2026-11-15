# Versioned quotation pricing: preserve all existing row amounts and BI fields.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('micmod_base', '0110_quotation_sale_type_multi_condition'),
    ]

    operations = [
        migrations.AddField(
            model_name='quotationitem', name='pricing_version',
            field=models.PositiveSmallIntegerField(default=1, db_index=True, verbose_name='نسخه قیمت‌گذاری'),
        ),
        migrations.AddField(
            model_name='quotationitem', name='system_price_method',
            field=models.CharField(max_length=128, null=True, blank=True, verbose_name='روش قیمت مرجع'),
        ),
        migrations.AddField(
            model_name='quotationitem', name='system_price_snapshot',
            field=models.JSONField(null=True, blank=True, verbose_name='تصویر قیمت مرجع'),
        ),
        migrations.AddField(
            model_name='quotationitem', name='system_price',
            field=models.DecimalField(max_digits=22, decimal_places=4, null=True, blank=True, verbose_name='قیمت مرجع سیستم'),
        ),
        migrations.AddField(
            model_name='quotationitem', name='manager_approved_price',
            field=models.DecimalField(max_digits=22, decimal_places=4, null=True, blank=True, verbose_name='قیمت مصوب مدیر'),
        ),
        migrations.AddField(
            model_name='quotationitem', name='effective_unit_price',
            field=models.DecimalField(max_digits=22, decimal_places=4, null=True, blank=True, verbose_name='فی پس از تخفیف'),
        ),
        migrations.AddField(
            model_name='quotationitem', name='calculated_row_discount',
            field=models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True, verbose_name='تخفیف محاسباتی ردیف'),
        ),
        migrations.AddField(
            model_name='quotationitem', name='manager_price_difference',
            field=models.DecimalField(max_digits=22, decimal_places=4, null=True, blank=True, verbose_name='اختلاف فی مصوب با سیستم'),
        ),
        migrations.AddField(
            model_name='quotationitem', name='manager_positive_difference',
            field=models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True, verbose_name='عملکرد مثبت فروش کل ردیف'),
        ),
    ]
