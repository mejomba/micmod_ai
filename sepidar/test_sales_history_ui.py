"""Lightweight regression checks for the sales history client interactions.

The widget's pure wheel-routing function is exercised in Node when available;
the structural checks can run with Django's standard test runner alone.
"""
from pathlib import Path
import re
import shutil
import subprocess
import unittest

from django.test import SimpleTestCase


TEMPLATE = Path(__file__).resolve().parent / "templates" / "sepidar" / "sales_history.html"


class SalesHistoryInteractionTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.source = TEMPLATE.read_text(encoding="utf-8")

    def test_disclosure_chevron_points_down_closed_and_up_open(self):
        self.assertIn('class="sh-advanced-arrow" aria-hidden="true"></span>', self.source)
        self.assertIn('border-right:2px solid currentColor;border-bottom:2px solid currentColor;transform:rotate(45deg)', self.source)
        self.assertIn('.sh-advanced-filters[open] .sh-advanced-arrow{transform:rotate(225deg)}', self.source)

    def test_busy_spinner_is_available_during_debounce_and_near_active_column(self):
        self.assertIn('class="sh-spinner" aria-hidden="true"', self.source)
        self.assertIn('role="status" aria-live="polite" hidden', self.source)
        self.assertIn('th.sh-searching-column::after', self.source)
        self.assertRegex(self.source, r'function schedule\(ms,origin\)\{[\s\S]*?setBusy\(true\);\s*timer=setTimeout\(search,ms\);')
        self.assertIn("if(!x)document.querySelectorAll('#sales-history-report .sh-searching-column')", self.source)

    def test_document_wheel_has_page_priority_and_table_reversal(self):
        self.assertIn('document.scrollingElement||document.documentElement', self.source)
        self.assertIn("if(destination==='page')", self.source)
        self.assertIn('window.scrollBy(0,delta)', self.source)
        self.assertIn("scrollArea.scrollTop=Math.max(0,Math.min(max,before+delta))", self.source)

    @unittest.skipUnless(shutil.which("node"), "Node.js needed for JS behavior tests")
    def test_wheel_destination_boundary_cases(self):
        match = re.search(
            r'    function wheelDestination\(delta,pageAtEnd,tableTop,tableMax\)\{[\s\S]*?\n    \}',
            self.source,
        )
        self.assertIsNotNone(match, "wheel policy must remain independently testable")
        assertions = """
const assert = require('node:assert/strict');
assert.equal(wheelDestination(120, false, 0, 500), 'page');
assert.equal(wheelDestination(120, false, 200, 500), 'page');
assert.equal(wheelDestination(120, true, 0, 500), 'table');
assert.equal(wheelDestination(120, true, 499, 500), 'page');
assert.equal(wheelDestination(-120, true, 150, 500), 'table');
assert.equal(wheelDestination(-120, true, 0, 500), 'page');
assert.equal(wheelDestination(0, true, 0, 500), 'page');
assert.equal(wheelDestination(120, true, 0, 0), 'page');
"""
        result = subprocess.run(
            ["node", "-e", match.group(0) + "\n" + assertions],
            check=False, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
