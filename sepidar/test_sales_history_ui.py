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
        self.assertIn('.sh-search-head th.sh-searching-column .sh-col-filter-shell .sh-col-loader', self.source)
        self.assertNotIn('th.sh-searching-column::after', self.source)
        self.assertNotIn('padding-left:25px!important', self.source)
        self.assertIn("function showColumnSpinner(field)", self.source)
        self.assertIn("}).on('focus',function(){", self.source)
        self.assertIn('showColumnSpinner(null);', self.source)
        self.assertRegex(self.source, r'function schedule\(ms,origin\)\{[\s\S]*?showColumnSpinner\(origin\);\s*setBusy\(true\);\s*timer=setTimeout\(search,ms\);')
        self.assertIn('if(!x)showColumnSpinner(null)', self.source)

    def test_column_spinner_is_separate_from_input_clear_control(self):
        self.assertIn("shell.className='sh-col-filter-shell'", self.source)
        self.assertIn("loader.className='sh-col-loader'", self.source)
        self.assertIn('shell.appendChild(this);', self.source)
        self.assertIn('shell.appendChild(loader);', self.source)
        self.assertIn("loader.setAttribute('aria-hidden','true')", self.source)
        self.assertIn('.sh-col-filter-shell .sh-col-search', self.source)
        self.assertIn('flex:0 0 13px', self.source)
        self.assertIn("if(th)th.classList.add('sh-searching-column')", self.source)
        self.assertNotIn('th.sh-searching-column::after', self.source)

    def test_document_wheel_restored_and_can_scroll_above_table(self):
        self.assertIn('document.scrollingElement||document.documentElement', self.source)
        self.assertIn("if(destination==='page')", self.source)
        self.assertIn("if(scrollArea.contains(e.target))", self.source)
        self.assertIn('window.scrollBy(0,delta)', self.source)
        self.assertIn("scrollArea.scrollTop=Math.max(0,Math.min(max,before+delta))", self.source)
        self.assertIn('if(remaining>170)return;', self.source)
        self.assertNotIn('moveWheel(', self.source)
        self.assertNotIn('stopWheelAnimation()', self.source)

    def test_initial_loader_visible_until_window_load(self):
        self.assertIn('id="sh-initial-loading" role="status"', self.source)
        self.assertIn('class="sh-initial-spinner"', self.source)
        self.assertIn('#sh-initial-loading[hidden]{display:none!important}', self.source)
        self.assertIn("window.addEventListener('load',finishInitialLoading,{once:true})", self.source)
        self.assertIn("if(document.readyState==='complete')finishInitialLoading()", self.source)
        self.assertIn('if(overlay)overlay.hidden=true', self.source)


    def test_calendar_month_year_picker_and_navigation(self):
        self.assertIn('data-mode="months"', self.source)
        self.assertIn('data-mode="years"', self.source)
        self.assertIn('data-select-month', self.source)
        self.assertIn('data-select-year', self.source)
        self.assertIn('data-year-shift', self.source)
        self.assertIn('data-nav="-1" aria-label="ماه قبل">‹', self.source)
        self.assertIn('data-nav="1" aria-label="ماه بعد">›', self.source)

    def test_calendar_keeps_month_and_year_controls_visible_in_every_mode(self):
        self.assertIn('function calendarHeaderHTML()', self.source)
        self.assertIn('var html=calendarHeaderHTML();', self.source)
        self.assertIn("aria-expanded=\\\"'+(calendarMode==='months')+'\\\"", self.source)
        self.assertIn("aria-expanded=\\\"'+(calendarMode==='years')+'\\\"", self.source)
        self.assertIn("calendarMode=calendarMode===targetMode?'days':targetMode", self.source)
        self.assertIn('ماه موردنظر را انتخاب کنید', self.source)
        self.assertIn('سال موردنظر را انتخاب کنید', self.source)
        self.assertIn("data-year-nav", self.source)

    def test_advanced_filters_have_clear_groups_and_help_text(self):
        self.assertIn('class="sh-filters-toolbar"', self.source)
        self.assertIn('class="sh-filters-intro"', self.source)
        self.assertIn('class="sh-filter-group-title"', self.source)
        self.assertIn('sh-filter-group-title--secondary', self.source)
        self.assertIn('id="sh-clear-all"', self.source)
        self.assertIn('بدون بارگذاری دوباره صفحه', self.source)
        self.assertIn('.sh-compact-form>.sh-mini-field:focus-within', self.source)

    def test_calendar_date_fields_live_in_advanced_form_only(self):
        form = self.source.split('<form class="sh-compact-form"', 1)[1].split('</form>', 1)[0]
        self.assertIn('id="sh-date-from"', form)
        self.assertIn('id="sh-date-to"', form)
        self.assertEqual(self.source.count('id="sh-date-from"'), 1)
        self.assertEqual(self.source.count('id="sh-date-to"'), 1)
        self.assertNotIn('<div class="sh-table-tools">', self.source)
        self.assertNotIn('type="submit">اعمال', self.source)

    def test_auto_ajax_advanced_filters_and_global_clear(self):
        self.assertIn("advancedForm.addEventListener('input'", self.source)
        self.assertIn("advancedForm.addEventListener('change'", self.source)
        self.assertIn("advancedForm.addEventListener('submit'", self.source)
        self.assertIn("var data=new FormData(advancedForm)", self.source)
        self.assertIn("$('#sh-clear-table, #sh-clear-all').on('click',clearAllFilters)", self.source)
        self.assertIn("if(!p.toString())p.set('all_dates','1')", self.source)
        self.assertIn('id="sh-clear-all"', self.source)
        self.assertIn('id="sh-clear-table"', self.source)
        self.assertNotIn('advancedParams=new URLSearchParams', self.source)
        self.assertNotIn('sh-filter-actions a', self.source)

    def test_ajax_chips_clear_any_type_of_filter(self):
        self.assertIn("key.indexOf('col_')===0", self.source)
        self.assertIn("key==='date_from'", self.source)
        self.assertIn("key==='date_to'", self.source)
        self.assertIn("advancedForm.querySelectorAll('[name=", self.source)

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
assert.equal(wheelDestination(-120, false, 0, 500), 'page'); // upward at top: scroll document
assert.equal(wheelDestination(-120, false, 1, 500), 'page'); // very near the top
assert.equal(wheelDestination(-120, false, 25, 500), 'table'); // upward inside table
assert.equal(wheelDestination(0, true, 0, 500), 'page');
assert.equal(wheelDestination(120, true, 0, 0), 'page');
"""
        helpers = [match.group(0)]
        for name, args in (("columnSearchDelay", "tag,value"),):
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
"""
        result = subprocess.run(
            ["node", "-e", "\n".join(helpers) + "\n" + assertions],
            check=False, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
