"""Add a strict read-only financial viewer group for Packing documents."""
from django.db import migrations


FINANCE_VIEW_ONLY_GROUP = 'packing_finance_viewer'


def create_finance_viewer_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.using(schema_editor.connection.alias).get_or_create(
        name=FINANCE_VIEW_ONLY_GROUP,
    )


class Migration(migrations.Migration):
    dependencies = [
        ('order', '0130_packing_viewer_group'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(create_finance_viewer_group, migrations.RunPython.noop),
    ]
