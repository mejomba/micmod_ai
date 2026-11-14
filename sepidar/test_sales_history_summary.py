"""Backend financial totals for incremental sales history."""
from django.test import SimpleTestCase
from sepidar.sales_history_summary import _currency, summarize_sales_history


class SalesHistorySummaryTests(SimpleTestCase):
    def test_currency_aliases_do_not_split_same_money(self):
        self.assertEqual(_currency('ریال')[0], 'IRR')
        self.assertEqual(_currency('Rial')[0], 'IRR')
        self.assertEqual(_currency('rmb')[0], 'CNY')
        self.assertEqual(_currency('یوان')[0], 'CNY')
        self.assertEqual(_currency('ero')[0], 'EUR')

    def test_weighted_average_and_totals_use_entire_input_not_first_page(self):
        records = [
            {'source': 'portal', 'doc_type': 'invoice', 'Number': '1',
             'year_title': '1405', 'currency': 'ریال', 'Quantity': 2,
             'Fee': 100, 'Price': 180, 'customer_code': 'A', 'item_code': 'T'},
            {'source': 'sepidar', 'doc_type': 'invoice', 'Number': '2',
             'year_title': '1405', 'currency': 'Rial', 'Quantity': 3,
             'Fee': 200, 'Price': 570, 'customer_code': 'B', 'item_code': 'T'},
            {'source': 'portal', 'doc_type': 'quotation', 'Number': '3',
             'year_title': '1405', 'currency': 'USD', 'Quantity': 4,
             'Fee': 10, 'Price': 40, 'customer_code': 'B', 'item_code': 'Z'},
        ]
        info = summarize_sales_history(records, truncated=True)
        buckets = {r['key']: r for r in info['currencies']}
        self.assertEqual(buckets['IRR']['value'], '750000000')
        self.assertEqual(buckets['IRR']['weight'], '5000000')
        self.assertEqual(buckets['IRR']['feeWeighted'], '800000000000000')
        self.assertEqual(buckets['USD']['value'], '40000000')
        self.assertEqual(info['quantity_scaled'], '9000000')
        self.assertEqual(info['sources'], {'sepidar': 1, 'portal': 2})
        self.assertEqual(info['distinct']['item'], 2)
        self.assertEqual(info['distinct']['document'], 3)
        self.assertTrue(info['truncated'])

    def test_empty_and_zero_quantity(self):
        info = summarize_sales_history([
            {'source': 'sepidar', 'currency': 'IRR', 'Quantity': 0,
             'Fee': 450, 'Price': 5},
        ])
        self.assertEqual(info['currencies'][0]['weight'], '0')
        self.assertEqual(info['currencies'][0]['value'], '5000000')
        self.assertEqual(summarize_sales_history([])['row_count'], 0)
