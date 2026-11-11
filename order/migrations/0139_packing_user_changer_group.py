"""Create the model-scoped Packing workflow assignee changer group."""
from django.db import migrations


USER_CHANGER_GROUP = 'packing_user_changer'


def create_packing_user_changer_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.using(schema_editor.connection.alias).get_or_create(
        name=USER_CHANGER_GROUP,
    )


class Migration(migrations.Migration):
    dependencies = [
        ('order', '0138_packingitem_volume_is_confirmed'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(
            create_packing_user_changer_group,
            migrations.RunPython.noop,
        ),
    ]
