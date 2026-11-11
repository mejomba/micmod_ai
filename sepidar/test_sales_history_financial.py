"""Read-only check. Run: python manage.py shell < test_sales_history_financial.py"""
from math import isclose
from sepidar.sales_history_service import _portal_history
from micmod_base.models import QuotationItem
from factor.models import FactorItem
from inquiry.models import CurrencyAmount


def close(a, b):
    return isclose(float(a or 0), float(b or 0), rel_tol=1e-9, abs_tol=1e-3)


rows = _portal_history({'item_code': '899'})
assert rows, 'No rows from Portal for item 899; use a known item code.'
assert all(r['source'] == 'portal' for r in rows)

for row in rows[:30]:
    if row['doc_type'] == 'quotation':
        obj = QuotationItem.objects.get(pk=row['itemId'])
        expect_price = float(obj.price or 0) + row['addition_allocated']
        expected_fee = float(obj.fee_() or 0) - (
            float(obj.discount_value or 0) / float(obj.quantity)
            if obj.quantity else 0
        )
        assert row['Rate'] is None, ('quotation Rate', row)
    else:
        obj = FactorItem.objects.get(pk=row['itemId'])
        expect_price = (
            float(obj.row_price or 0) - float(obj.discount_value or 0)
            + float(obj.tax or 0) + row['addition_allocated']
        )
        expected_fee = float(obj.fee_after_discount or 0)
        factor = obj.factor
        curid = factor.currency_ref_id or (
            factor.q.currency_ref_id if factor.q else None
        )
        ca = (CurrencyAmount.objects.filter(currency_id=curid, is_deleted=False)
              .order_by('-created_date', '-pk').first()) if curid else None
        expect_rate = factor.rate or (ca.open_rate if ca else None)
        assert (row['Rate'] is None and expect_rate is None) or close(row['Rate'], expect_rate), ('rate', row, expect_rate)

    assert close(row['Price'], expect_price), ('Price', row, expect_price)
    assert close(row['fee_after_discount'], expected_fee), ('fee after discount', row, expected_fee)
    print(row['doc_type'], 'id=', row['itemId'], 'Price=', row['Price'],
          'fee_after_discount=', row['fee_after_discount'],
          'Rate=', row['Rate'], 'OK')

print('Checked:', min(30, len(rows)), 'of', len(rows), 'Portal rows')
