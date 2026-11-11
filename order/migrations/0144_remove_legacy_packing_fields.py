"""Safely reconcile then remove merge-reintroduced legacy Packing fields.

0143 has already been applied in some environments; never rewrite it.
"""
from django.db import migrations
from django.db.models import F, Q
from django.db.models.functions import Length


def reconcile_legacy_packing_values(apps, schema_editor):
    Packing = apps.get_model('order', 'Packing')
    using = schema_editor.connection.alias
    pairs = (
        ('source', 'origin'),
        ('transporter_company', 'transportation_company'),
    )
    for obsolete, canonical in pairs:
        nonempty = (Q(**{f'{obsolete}__isnull': False})
                    & ~Q(**{obsolete: ''}))
        queryset = Packing.objects.using(using).filter(nonempty)
        populated = (Q(**{f'{canonical}__isnull': False})
                     & ~Q(**{canonical: ''}))
        conflict = queryset.filter(populated).exclude(
            **{canonical: F(obsolete)}
        ).values_list('pk', flat=True).first()
        if conflict is not None:
            raise RuntimeError(
                f'Packing {conflict}: conflicting values for {obsolete} and '
                f'{canonical}. Reconcile the data before migrating.'
            )

        missing = (Q(**{f'{canonical}__isnull': True})
                   | Q(**{canonical: ''}))
        to_copy = queryset.filter(missing)
        oversize = to_copy.annotate(
            _old_length=Length(obsolete)
        ).filter(_old_length__gt=255).values_list('pk', flat=True).first()
        if oversize is not None:
            raise RuntimeError(
                f'Packing {oversize}: {obsolete} exceeds 255 characters; '
                f'cannot safely copy to {canonical}.'
            )
        to_copy.update(**{canonical: F(obsolete)})


class Migration(migrations.Migration):
    dependencies = [
        ('order', '0143_packing_source_packing_transporter_company_and_more'),
    ]

    operations = [
        migrations.RunPython(
            reconcile_legacy_packing_values,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RemoveField(model_name='packing', name='source'),
        migrations.RemoveField(model_name='packing', name='transporter_company'),
    ]
