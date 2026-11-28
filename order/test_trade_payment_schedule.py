import ast
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase

from order.trade_payment_schedule import render_payment_links, render_payment_schedule


TODAY = date(2026, 11, 28)


def currency(name):
    return SimpleNamespace(title_en=name)


def item(pk, day, paid=False, header=None, cur=None, amount=12500, deleted=False):
    return SimpleNamespace(
        pk=pk, pay_date=date(2026, 11, day) if day else None,
        is_pay=paid, payment_id=pk if header else None,
        payment=header, currency=cur, total_amount=amount, is_deleted=deleted,
    )


class PaymentScheduleTests(TestCase):
    def test_future_with_and_without_header_and_sorting(self):
        header = SimpleNamespace(currency=currency('USD'))
        rows = [item(2, 30, cur=currency('RMB')), item(1, 29, header=header)]
        future, past = render_payment_schedule(rows, None, TODAY)
        self.assertIn('12,500 USD 2026/11/29', future)
        self.assertIn('12,500 RMB 2026/11/30', future)
        self.assertLess(future.index('USD'), future.index('RMB'))
        self.assertEqual(future.count('dir="ltr"'), 2)
        self.assertIn('—', past)

    def test_past_paid_and_overdue_are_separate_and_unpaid_first(self):
        rows = [item(1, 20, True, cur=currency('USD')), item(2, 25, cur=currency('RMB'))]
        future, past = render_payment_schedule(rows, None, TODAY)
        self.assertIn('—', future)
        self.assertIn('text-danger', past)
        self.assertIn('text-success', past)
        self.assertLess(past.index('RMB'), past.index('USD'))

    def test_today_and_future_paid(self):
        rows = [item(1, 28), item(2, 28, True), item(3, 29, True)]
        future, past = render_payment_schedule(rows, 'RMB', TODAY)
        self.assertIn('text-warning', future)
        self.assertIn('text-success', future)
        self.assertIn('text-success', past)
        self.assertEqual(future.count('2026/11/28'), 1)
        self.assertEqual(past.count('2026/11/28'), 1)
        self.assertNotIn('text-danger', future)

    def test_missing_dates_deleted_rows_and_empty(self):
        rows = [item(1, None), item(2, 29, deleted=True)]
        future, past = render_payment_schedule(rows, None, TODAY)
        self.assertIn('—', future)
        self.assertIn('—', past)
        self.assertNotIn('12,500', future + past)

    def test_currency_priority_fractional_amount_and_escaping(self):
        header = SimpleNamespace(currency=currency('USD'))
        rows = [
            item(1, 29, header=header, cur=currency('RMB'), amount=12.345),
            item(2, 29, header=SimpleNamespace(currency=None), cur=currency('EUR'), amount=0),
            item(3, 29, amount=1000.0),
        ]
        future, _ = render_payment_schedule(rows, '<RMB>', TODAY)
        self.assertIn('12.345 USD', future)
        self.assertIn('0 EUR', future)
        self.assertIn('1,000 &lt;RMB&gt;', future)
        self.assertNotIn('<RMB>', future)
        self.assertIn('ارز نامشخص', render_payment_schedule([item(1, 29)], None, TODAY)[0])

    def test_existing_links_and_unattached_rows(self):
        rows = [item(1, None, header=SimpleNamespace(currency=currency('USD'))),
                item(2, 29, cur=currency('RMB')), item(3, 29, deleted=True)]
        html = render_payment_links(rows, None, lambda pk: f'/payment/{pk}/')
        self.assertIn('href="/payment/1/"', html)
        self.assertIn('بدون سربرگ پرداخت', html)
        self.assertIn('12,500 RMB', html)
        self.assertEqual(html.count('<hr>'), 1)


class PaymentScheduleWiringTests(TestCase):
    """Source-level regression checks; do not require the portal database."""

    @classmethod
    def setUpClass(cls):
        cls.source = Path(__file__).with_name('views.py').read_text(encoding='utf-8')
        tree = ast.parse(cls.source)
        cls.view = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                        and node.name == 'OrderDataTableListView')

    def method_source(self, name):
        method = next(node for node in self.view.body if isinstance(node, ast.FunctionDef)
                      and node.name == name)
        return ast.get_source_segment(self.source, method)

    def test_trade_columns_before_gio_and_superuser_columns_supported(self):
        source = self.method_source('get_column_defs')
        trade = source.split("elif self.request.user.base_group == 'trade':")[1].split(
            "elif self.request.user.base_group == 'mac':")[0]
        self.assertLess(trade.index("'name': 'future_payments'"), trade.index("'name': 'past_payments'"))
        self.assertLess(trade.index("'name': 'past_payments'"), trade.index("'name': 'gio'"))
        self.assertEqual(source.count("'name': 'future_payments'"), 1)
        self.assertEqual(source.count("'name': 'past_payments'"), 1)

    def test_prefetch_and_render_use_same_rows(self):
        source = self.method_source('get_initial_queryset')
        self.assertIn('if can_view_order_payments(request.user):', source)
        self.assertIn("list_order_currency_title=F('currency__title_en')", source)
        self.assertIn("to_attr='list_payment_items'", source)
        self.assertIn("'payment__currency', 'currency'", source)
        trade = self.method_source('customize_row_trade')
        payments = self.method_source('customize_payment_columns')
        self.assertIn('self.customize_payment_columns(row, obj)', trade)
        self.assertIn('obj.list_payment_items', payments)
        self.assertIn('render_payment_schedule(items, obj.list_order_currency_title, timezone.localdate())', payments)
        self.assertNotIn("obj.order_payment_items.select_related", payments)
        self.assertIn("row['gio']", trade)
        self.assertIn("row['packing']", trade)
