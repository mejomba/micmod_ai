"""Create an explicit read-only group for Packing documents (no schema change)."""
from django.db import migrations


VIEW_ONLY_GROUP = 'packing_viewer'


def create_packing_viewer_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.using(schema_editor.connection.alias).get_or_create(
        name=VIEW_ONLY_GROUP,
    )


class Migration(migrations.Migration):
    dependencies = [
        ('order', '0129_packing_workflow_nine_stages'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(
            create_packing_viewer_group,
            migrations.RunPython.noop,
        ),
    ]
