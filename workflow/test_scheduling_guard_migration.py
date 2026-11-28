"""Regression coverage for the scheduling guard migration's SQL framing."""
from importlib import import_module
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock

migration = import_module('workflow.migrations.0013_scheduling_history_guards')
NAMES = ('policy', 'config', 'forecast', 'detail')


class SchedulingGuardMigrationSQLTests(TestCase):
    def editor(self, vendor='postgresql'):
        return SimpleNamespace(connection=SimpleNamespace(vendor=vendor), execute=Mock())

    def test_install_executes_four_independent_complete_functions_before_triggers(self):
        editor = self.editor()
        migration.install(None, editor)
        statements = [call.args[0] for call in editor.execute.call_args_list]
        self.assertEqual(len(statements), 13)
        for name, sql in zip(NAMES, statements[:4]):
            tag = '$' + name + '$'
            self.assertEqual(sql.count(tag), 2)
            self.assertIn('CREATE FUNCTION wf_sched_guard_' + name + '()', sql)
            self.assertEqual(sql.count('CREATE FUNCTION'), 1)
            self.assertTrue(sql.strip().endswith('END;\n' + tag + ';'))
        self.assertTrue(all(sql.startswith('CREATE TRIGGER ') for sql in statements[4:]))
        self.assertEqual(len(set(statements[4:])), 9)

    def test_uninstall_drops_all_triggers_before_functions(self):
        editor = self.editor()
        migration.uninstall(None, editor)
        statements = [call.args[0] for call in editor.execute.call_args_list]
        self.assertEqual(len(statements), 13)
        self.assertTrue(all(sql.startswith('DROP TRIGGER IF EXISTS ') for sql in statements[:9]))
        self.assertEqual(statements[9:], [
            'DROP FUNCTION IF EXISTS wf_sched_guard_' + name + '()' for name in NAMES
        ])

    def test_other_database_engines_are_not_modified(self):
        editor = self.editor('sqlite')
        migration.install(None, editor)
        migration.uninstall(None, editor)
        editor.execute.assert_not_called()
