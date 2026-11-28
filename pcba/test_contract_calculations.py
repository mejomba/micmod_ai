"""Regression tests for PCBA pad totals, contract pricing and dashboard KPIs."""
from datetime import timedelta

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from django.template.loader import get_template

from extra_data.models import Item, PurchaseGroup
from pcba.forms import ContractForm
from pcba.models import Contract


class ContractCalculationTests(SimpleTestCase):
    def test_three_pad_categories_are_added_on_contract_form(self):
        contract = Contract(
            pad_count=21, ic_pad_count=4, not_assembly_pad_count=7,
            customer_total_board_count=30
        )
        self.assertEqual(contract.total_pads_per_board, 32)
        self.assertEqual(contract.assembled_pads_per_board, 25)
        # Annual mounted pads intentionally exclude paste/glue without assembly.
        self.assertEqual(contract.annual_assembled_pad_count, 750)

    def test_price_includes_normal_ic_paste_two_setups_and_extra_cost(self):
        contract = Contract(
            customer_total_board_count=100,
            pad_count=20, ic_pad_count=5, not_assembly_pad_count=3,
            pad_cost=8, ic_pad_cost=15,
            first_setup_cost=400, second_setup_cost=250,
            extra_total_cost=350,
        )
        # ((20 + 3) * 8 + 5 * 15) * 100 + 400 + 250 + 350
        self.assertEqual(contract.contract_cost, 26900)

    def test_setup_and_extra_costs_are_flat_not_per_board(self):
        contract = Contract(
            customer_total_board_count=5,
            first_setup_cost=100, second_setup_cost=250, extra_total_cost=300
        )
        self.assertEqual(contract.contract_cost, 650)

    def test_blank_optional_costs_do_not_break_total(self):
        contract = Contract(
            customer_total_board_count=10,
            pad_count=3, ic_pad_count=2, not_assembly_pad_count=1,
            pad_cost=None, ic_pad_cost=None,
            first_setup_cost=None, second_setup_cost=None,
            extra_total_cost=0,
        )
        self.assertEqual(contract.contract_cost, 0)
        self.assertEqual(contract.total_pads_per_board, 6)

    def test_new_extra_cost_field_is_in_model_and_contract_form(self):
        field = Contract._meta.get_field('extra_total_cost')
        self.assertEqual(field.default, 0)
        self.assertIn('extra_total_cost', ContractForm._meta.fields)

    def test_contract_page_exposes_live_pad_count_and_cost(self):
        source = get_template('pcba/view.html').template.source
        self.assertIn('form.not_assembly_pad_count', source)
        self.assertIn('form.extra_total_cost', source)
        self.assertIn('pcba-total-pads-per-board', source)
        self.assertIn('pcba-calculated-contract-cost', source)
        self.assertIn('pcba_contract_calculations.js', source)


    def test_calculation_totals_share_one_compact_box_below_cost_fields(self):
        source = get_template('pcba/view.html').template.source
        self.assertEqual(source.count('class="pcba-contract-summary"'), 1)
        self.assertEqual(source.count('id="pcba-total-pads-per-board"'), 1)
        self.assertEqual(source.count('id="pcba-calculated-contract-cost"'), 1)
        cost_fields_end = source.index(
            "{% render_field_by_order form form.pad_cost form.ic_pad_cost"
        )
        summary_position = source.index('class="pcba-contract-summary"')
        image_wrapper_position = source.index('id="image-wrapper"')
        self.assertLess(cost_fields_end, summary_position)
        self.assertLess(summary_position, image_wrapper_position)
        self.assertLess(summary_position, source.index("form form.description"))
        self.assertNotIn('class="pcba-pad-summary"', source)
        self.assertNotIn('class="pcba-cost-summary', source)
        self.assertIn('grid-template-columns: repeat(2, minmax(0, 1fr))', source)
        self.assertIn('@media (max-width: 767px)', source)
        self.assertIn('grid-template-columns: 1fr', source)


class ContractPadKpiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        group = PurchaseGroup.objects.create(title='PCBA calculation test group')
        goods = Item.objects.create(
            part_number='PCBA-KPI-TEST-PART', purchase_group=group,
        )
        cls.first = Contract.objects.create(
            goods_code_fk=goods, customer_total_board_count=100,
            pad_count=10, ic_pad_count=3, not_assembly_pad_count=70,
        )
        cls.second = Contract.objects.create(
            goods_code_fk=goods, customer_total_board_count=20,
            pad_count=2, ic_pad_count=5, not_assembly_pad_count=10,
        )
        cls.older = Contract.objects.create(
            goods_code_fk=goods, customer_total_board_count=30,
            pad_count=9, ic_pad_count=9, not_assembly_pad_count=30,
        )
        Contract.objects.filter(pk=cls.older.pk).update(
            created_date=timezone.now() - timedelta(days=400)
        )

    def test_this_year_pad_count_uses_mounted_normal_and_ic_times_boards(self):
        response = self.client.get(
            reverse('pcba:this_year_pad_count'), {'q': 'this_year_pad_count'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['this_year_pad_count'], 1440)

    def test_today_pad_count_uses_same_definition(self):
        response = self.client.get(
            reverse('pcba:today_pad_count'), {'q': 'today_pad_count'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['today_pad_count'], 1440)

    def test_invalid_query_keeps_prior_endpoint_contract(self):
        response = self.client.get(reverse('pcba:this_year_pad_count'))
        self.assertEqual(response.json(), {'error': 'Invalid'})

    def test_contract_cost_defaults_preserve_existing_records(self):
        contract = Contract.objects.get(pk=self.first.pk)
        self.assertEqual(contract.extra_total_cost, 0)
        self.assertEqual(contract.annual_assembled_pad_count, 1300)
