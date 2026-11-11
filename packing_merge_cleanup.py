#!/usr/bin/env python3
"""Audited cleanup for mejomba/micmod_ai main after packing/GIO merge.

Default is dry-run. Use --apply on a CLEAN local checkout of main.
No Git commits or database migrations are executed by this script.
"""
from __future__ import annotations

import argparse
import difflib
import subprocess
import sys
from pathlib import Path

EXPECTED_MODEL_BLOB = "b54b901046ab5859ff1ed19d48b65140a51f7b5b"
MIGRATION_NAME = "0144_remove_legacy_packing_fields.py"
TEST_NAME = "test_packing_merge_cleanup.py"

MIGRATION = '''"""Safely reconcile then remove merge-reintroduced legacy Packing fields.

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
'''

TESTS = '''"""Regression checks for removal of stale Packing merge artifacts."""
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import resolve, reverse

from order.forms import PackingSafeForm
from order.models import Packing
from order.views import PackingView, QuickPackingView


class PackingMergeCleanupTests(SimpleTestCase):
    def test_legacy_fields_are_not_in_the_model(self):
        names = {field.name for field in Packing._meta.get_fields()}
        self.assertFalse({'source', 'transporter_company'} & names)
        self.assertTrue({'origin', 'destination', 'transportation_company'} <= names)
        self.assertEqual(
            sum(field.name == 'destination' for field in Packing._meta.fields), 1,
        )

    def test_old_workflow_method_is_not_reintroduced(self):
        self.assertNotIn('submit_flow', Packing.__dict__)
        self.assertTrue(callable(Packing.workflow_state_index))

    def test_packing_form_whitelist_uses_canonical_fields(self):
        fields = set(PackingSafeForm.field_layout)
        self.assertTrue({'origin', 'destination', 'transportation_company'} <= fields)
        self.assertFalse({'source', 'transporter_company'} & fields)

    def test_both_registered_packing_routes_are_retained(self):
        self.assertIs(resolve(reverse('order:packing.view')).func.view_class, PackingView)
        self.assertIs(resolve(reverse('order:quick_packing')).func.view_class, QuickPackingView)

    def test_inactive_template_does_not_reference_old_fields(self):
        path = (Path(settings.BASE_DIR) / 'order' / 'templates' / 'order'
                / 'packing' / 'quick_packing_update.html')
        template = path.read_text(encoding='utf-8')
        self.assertNotIn('form.source', template)
        self.assertNotIn('form.transporter_company', template)
        self.assertIn('form.origin', template)
        self.assertIn('form.transportation_company', template)
'''


def run_git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ['git', *args], cwd=root, text=True, stderr=subprocess.STDOUT,
    ).strip()


def cleanup_model(original: str) -> str:
    # Exactly three added definitions from the wrong conflict resolution.
    obsolete = (
        "    source = models.CharField(_('source'), null=True, blank=True)\n",
        "    destination = models.CharField(_('destination'), null=True, blank=True)\n",
        "    transporter_company = models.CharField(_('transporter_company'), null=True, blank=True)\n",
    )
    new = original
    for entry in obsolete:
        if new.count(entry) != 1:
            raise ValueError(f'Expected exactly one obsolete declaration: {entry!r}')
        new = new.replace(entry, '', 1)

    marker = '    def submit_flow(self, request, is_new):\n'
    after = '    @property\n    def computed_estimated_shipping_start_date(self):\n'
    if new.count(marker) != 2:
        # There is another, legitimate method on the Payment model.
        raise ValueError('Unexpected number of submit_flow definitions; refusing edit')
    start = new.index(marker, new.index('class Packing('))
    end = new.index(after, start)
    if '"packing_user_dep"' not in new[start:end] or 'return last_flow' not in new[start:end]:
        raise ValueError('Packing.submit_flow does not match the inspected legacy method')
    return new[:start] + new[end:]


def cleanup_template(original: str) -> str:
    before = 'form.source form.destination form.transporter_company'
    after = 'form.origin form.destination form.transportation_company'
    if original.count(before) != 1:
        raise ValueError('Stale template field sequence has changed; refusing edit')
    return original.replace(before, after, 1)


def show_diff(path: Path, old: str, new: str, root: Path) -> None:
    relative = path.relative_to(root).as_posix()
    output = difflib.unified_diff(
        old.splitlines(keepends=True), new.splitlines(keepends=True),
        fromfile=f'a/{relative}' if old else '/dev/null',
        tofile=f'b/{relative}',
    )
    print(''.join(output), end='')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path('.'),
                        help='Local project root containing manage.py')
    parser.add_argument('--apply', action='store_true',
                        help='Actually write changed files. Without this, print a diff only.')
    args = parser.parse_args()
    root = args.repo.resolve()
    if not (root / 'manage.py').is_file():
        raise SystemExit('Not a Django project root (manage.py missing).')
    if run_git(root, 'rev-parse', '--abbrev-ref', 'HEAD') != 'main':
        raise SystemExit('Expected checked-out main, where migration 0143 exists. No files changed.')
    if run_git(root, 'status', '--porcelain'):
        raise SystemExit('Working tree is not clean. Commit/stash your work first. No files changed.')

    model_path = root / 'order' / 'models.py'
    template_path = root / 'order' / 'templates' / 'order' / 'packing' / 'quick_packing_update.html'
    migrations = root / 'order' / 'migrations'
    if not (migrations / '0143_packing_source_packing_transporter_company_and_more.py').is_file():
        raise SystemExit('Expected already-applied 0143 migration in checkout. No files changed.')
    if list(migrations.glob('0144*.py')):
        raise SystemExit('A 0144 migration already exists. Resolve migration numbering first.')
    if (root / 'order' / TEST_NAME).exists():
        raise SystemExit(f'{TEST_NAME} already exists. No files changed.')
    sha = run_git(root, 'hash-object', 'order/models.py')
    if sha != EXPECTED_MODEL_BLOB:
        raise SystemExit(f'order/models.py changed since audit ({sha}); re-audit before editing.')

    original_model = model_path.read_text(encoding='utf-8')
    original_template = template_path.read_text(encoding='utf-8')
    changes = [
        (model_path, original_model, cleanup_model(original_model)),
        (template_path, original_template, cleanup_template(original_template)),
        (migrations / MIGRATION_NAME, '', MIGRATION),
        (root / 'order' / TEST_NAME, '', TESTS),
    ]
    for path, old, new in changes:
        if path.exists() and old == new:
            raise ValueError(f'Unexpected no-op: {path}')
        if not path.exists() and old:
            raise ValueError(f'Expected to read existing file: {path}')
        if path.exists() and not old:
            raise ValueError(f'Will not overwrite existing file: {path}')
        if path.suffix == '.py':
            compile(new, str(path), 'exec')

    if not args.apply:
        print('DRY RUN: no files will be modified. Use --apply to write the changes.\n')
        for path, old, new in changes:
            show_diff(path, old, new, root)
        return

    for path, old, new in changes:
        path.write_text(new, encoding='utf-8')
        print(f'Updated: {path.relative_to(root)}')
    print('\nNo commits made. Do NOT rewrite applied migration 0143.')
    print('Next: python manage.py check')
    print('      python manage.py makemigrations --check --dry-run')
    print('      python manage.py test order.test_packing_merge_cleanup order.test_packing_workflow_stages')
    print('      python manage.py migrate order 0144')
    print('If a data conflict is reported, investigate the specific Packing row before retrying.')


if __name__ == '__main__':
    main()
