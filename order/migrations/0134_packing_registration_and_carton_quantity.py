"""Add post-draft customs registration details and independent carton counts."""
from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [
        ('order', '0133_packing_sepidar_transfers'),
    ]

    operations = [
        migrations.AddField(
            model_name='packing',
            name='order_registration_number',
            field=models.CharField(
                verbose_name='شماره ثبت سفارش (۸ رقم)',
                max_length=8, null=True, blank=True,
                validators=[django.core.validators.RegexValidator(
                    regex=r'^[0-9]{8}$',
                    message='شماره ثبت سفارش باید دقیقاً ۸ رقم باشد.',
                )],
            ),
        ),
        migrations.AddField(
            model_name='packing',
            name='proforma_pi_number',
            field=models.CharField(
                verbose_name='شماره پرفورما (PI)',
                max_length=255, null=True, blank=True,
            ),
        ),
        migrations.AddField(
            model_name='packing',
            name='commercial_card',
            field=models.CharField(
                verbose_name='کارت بازرگانی',
                max_length=32, null=True, blank=True,
                choices=[
                    ('rahavard_tejarat_ayande', 'رهاورد تجارت آینده'),
                    ('rasoul_rafie', 'رسول رفیع'),
                    ('modern_electronic', 'مدرن الکترونیک'),
                    ('faraz_fanavaran_faran', 'فراز فن آوران فاران'),
                    ('hikar', 'هایکار'),
                    ('hibar', 'هایبار'),
                ],
            ),
        ),
        migrations.AddField(
            model_name='packingitem',
            name='carton_quantity',
            field=models.PositiveIntegerField(
                verbose_name='تعداد کارتن', null=True, blank=True,
            ),
        ),
    ]
