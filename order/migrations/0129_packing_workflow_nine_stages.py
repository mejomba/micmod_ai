"""Keep existing Packing workflow history aligned with the new nine-stage process."""
from django.db import migrations


OLD_STAGE_NAMES = {
    'پیش نویس': 'پیش‌نویس',
    'پیشنویس': 'پیش‌نویس',
    'DEP': 'تحویل شرکت حمل',
    'arrive': 'حمل',
    '10%': 'قبض انبار',
    'اظهار گمرکی': 'اظهار',
    'ترخیص گمرک': 'ترخیص',
}

GROUP_BY_STAGE = {
    'پیش‌نویس': 'packing_user_p',
    'تحویل شرکت حمل': 'packing_user_dep',
    'حمل': 'packing_user_ship',
    'قبض انبار': 'packing_user_ghabz',
    'تحویل اسناد': 'trade_user_asnad',
    'اظهار': 'trade_user_ezhar',
    'ضمانتنامه': 'trade_user_zemanat',
    'ترخیص': 'trade_user_tarkhis',
    'انبار': 'wh_user',
}


def upgrade_packing_workflows(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    WorkFlow = apps.get_model('workflow', 'WorkFlow')

    # Create groups, but do not copy old memberships into newly restricted
    # stages. Administrators should grant membership explicitly per stage.
    for group_name in GROUP_BY_STAGE.values():
        Group.objects.using(schema_editor.connection.alias).get_or_create(
            name=group_name,
        )

    histories = WorkFlow.objects.using(schema_editor.connection.alias).filter(
        content_type__app_label='order',
        content_type__model='packing',
    )
    for flow in histories.iterator(chunk_size=500):
        changed = []

        # state stores the source step of next/back, current_state_name is the
        # destination. Mapping these independently preserves historical routes.
        source_stage = OLD_STAGE_NAMES.get(flow.state, flow.state)
        current_stage = OLD_STAGE_NAMES.get(
            flow.current_state_name, flow.current_state_name
        )
        if flow.state != source_stage:
            flow.state = source_stage
            changed.append('state')
        if flow.current_state_name != current_stage:
            flow.current_state_name = current_stage
            changed.append('current_state_name')

        # belong_to_group always refers to the *source* group of the record.
        source_group = GROUP_BY_STAGE.get(source_stage)
        if source_group and flow.belong_to_group != source_group:
            flow.belong_to_group = source_group
            changed.append('belong_to_group')

        if changed:
            flow.save(update_fields=changed)


class Migration(migrations.Migration):
    dependencies = [
        ('order', '0128_rename_packing_estimated_shipping_start_date'),
        ('workflow', '0010_workflow_current_state_name'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RunPython(upgrade_packing_workflows, migrations.RunPython.noop),
    ]
