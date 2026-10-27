"""Guard the Quick Packing action bar and workflow control layout.

These checks are database-free and complement browser/manual visual QA.
"""
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class QuickPackingControlLayoutTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        path = Path(settings.BASE_DIR) / 'order/templates/order/packing/quick_packing_create.html'
        cls.markup = path.read_text(encoding='utf-8')

    def test_primary_actions_live_in_one_fixed_bottom_bar(self):
        html = self.markup
        self.assertEqual(html.count('<div class="pk-command-bar"'), 1)
        self.assertIn('    .pk-command-bar {\n        position: fixed;', html)
        self.assertIn('        bottom: 0;', html)
        # The bar is a footer sibling, not nested inside the scrolling card.
        self.assertGreater(html.index('<div class="pk-command-bar"'),
                           html.index('id="ajax-response"'))
        self.assertLess(html.index('<div class="pk-command-bar"'),
                        html.index('id="pk-change-history-modal"'))

    def test_footer_has_save_header_history_back_and_next(self):
        html = self.markup
        self.assertEqual(html.count('id="packing-top-save"'), 1)
        self.assertEqual(html.count('id="submit-packing"'), 1)
        self.assertEqual(html.count('data-change-target="packing"'), 1)
        self.assertEqual(html.count('data-action="back"'), 1)
        self.assertEqual(html.count('data-action="next"'), 1)
        self.assertIn('submitButton.click();', html)

    def test_workflow_strip_combines_note_assignee_and_durations(self):
        html = self.markup
        strip = html.split('<div class="pk-workflow-control-strip">', 1)[1]
        strip = strip.split('<div class="pk-workflow-scroll"', 1)[0]
        self.assertIn('id="packing-workflow-description"', strip)
        self.assertIn('id="packing-workflow-user"', strip)
        self.assertIn('data-action="change_user"', strip)
        self.assertIn('id="packing-toggle-durations"', strip)
        self.assertEqual(html.count('id="packing-workflow-user"'), 1)

    def test_navigation_icons_do_not_rely_on_optional_font_library(self):
        html = self.markup
        footer = html.split('<div class="pk-command-bar" role="group"', 1)[1]
        footer = footer.split('<div class="modal fade pk-change-history-modal"', 1)[0]
        self.assertNotIn('ti-arrow-back-up', footer)
        self.assertNotIn('ti-arrow-forward-up', footer)
        self.assertIn('<path d="m9 14-5-5 5-5">', footer)
        self.assertIn('<path d="m15 14 5-5-5-5">', footer)

    def test_cancel_edit_uses_bootstrap_light_danger_hover(self):
        html = self.markup
        self.assertIn('class="btn btn-sm btn-light-danger pk-row-cancel-edit"', html)
        self.assertNotIn('.pk-row-cancel-edit:hover', html)
        self.assertNotIn('.pk-row-cancel-edit:focus', html)
