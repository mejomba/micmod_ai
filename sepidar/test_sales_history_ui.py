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

    def test_busy_spinner_follows_new_input_not_previous_field(self):
        self.assertIn('class="sh-spinner" aria-hidden="true"', self.source)
        self.assertIn('role="status" aria-live="polite" hidden', self.source)
        self.assertIn('th.sh-searching-column::after', self.source)
        self.assertIn("function showColumnSpinner(field)", self.source)
        self.assertIn("}).on('focus',function(){", self.source)
        self.assertIn('showColumnSpinner(null);', self.source)
        self.assertRegex(self.source, r'function schedule\(ms,origin\)\{[\s\S]*?showColumnSpinner\(origin\);\s*setBusy\(true\);\s*timer=setTimeout\(search,ms\);')
        self.assertIn('if(!x)showColumnSpinner(null)', self.source)

    def test_document_wheel_has_page_priority_and_smooth_table_animation(self):
        self.assertIn('document.scrollingElement||document.documentElement', self.source)
        self.assertIn("if(destination==='page'&&!insideTable)", self.source)
        self.assertIn("moveWheel(destination==='table'?scrollArea:page,delta,instant)", self.source)
        self.assertIn("wheelMotion.frame=requestAnimationFrame(animateWheel)", self.source)
        self.assertIn("if(instant)", self.source)
        self.assertIn("Math.max(280,scrollArea.clientHeight*.7)", self.source)

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
        helpers = [match.group(0)]
        for name, args in (("wheelStep", "current,target,elapsed"),
                           ("columnSearchDelay", "tag,value")):
            found = re.search(
                r"    function " + name + r"\(" + args + r"\)\{[\s\S]*?\n    \}",
                self.source,
            )
            self.assertIsNotNone(found, name)
            helpers.append(found.group(0))
        assertions += """
assert.equal(columnSearchDelay('INPUT', '123'), 280);
assert.equal(columnSearchDelay('INPUT', ''), 0);
assert.equal(columnSearchDelay('SELECT', 'portal'), 0);
assert.ok(wheelStep(0, 150, 16)>0 && wheelStep(0, 150, 16)<150);
assert.ok(wheelStep(150, 0, 16)>0 && wheelStep(150, 0, 16)<150);
assert.equal(wheelStep(149.7, 150, 16), 150);
"""
        result = subprocess.run(
            ["node", "-e", "\n".join(helpers) + "\n" + assertions],
            check=False, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
