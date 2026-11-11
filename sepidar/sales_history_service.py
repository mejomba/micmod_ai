"""Read-only unified sales history from Sepidar (SQL Server) and Portal (PostgreSQL).

Copy this file to: sepidar/sales_history_service.py
The implementation is not executed here against live databases.
"""
from datetime import date, datetime

import jdatetime
from django.db import connections

from extra_data.models import (
    AccountingUser, Customer, Item, PurchaseGroup, SaleGroup,
)
from factor.models import Factor, FactorItem
from micmod_base.base import Currency
from micmod_base.models import Quotation, QuotationItem, SaleType


MAX_ROWS_PER_SOURCE = 3000
# Mapping from the existing HTML selector: Sepidar FiscalYearRef -> Jalali year.
FISCAL_YEAR_MAP = {
    '48': 1405, '46': 1404, '44': 1403, '42': 1402,
    '41': 1401, '31': 1400, '25': 1399, '23': 1398,
    '21': 1397, '14': 1396, '3': 1395,
}

# Keys used by the existing Django template, exactly as in the original query.
COLUMNS = (
    'Date', 'Number', 'coef', 'doc_type', 'Fee', 'itemId',
    'NetPrice', 'NetPriceInBaseCurrency', 'Price',
    'PriceInBaseCurrency', 'Quantity', 'Rate',
    'sales_type_code', 'sales_type', 'customer_creation_date',
    'customer_title', 'customer_code', 'DLId',
    'sales_user_code', 'sales_user_group', 'item_code',
    'item_title', 'purchase_group', 'sales_group',
    'year_title', 'currency', 'fee_after_discount',
)


def _is_digits(value):
    return bool(value) and str(value).strip().isdigit()


def _normalize_fa(value):
    return str(value).strip().replace('ي', 'ی').replace('ك', 'ک')


def _rows(db_alias, sql, params):
    """Return all rows as case-insensitive dicts (key names lowercase)."""
    with connections[db_alias].cursor() as cursor:
        cursor.execute(sql, params)
        names = [desc[0].lower() for desc in cursor.description]
        return [dict(zip(names, rec)) for rec in cursor.fetchall()]


def _normalize_result(raw, source):
    row = {column: raw.get(column.lower()) for column in COLUMNS}
    row['source'] = source
    row['row_key'] = f"{source}:{row['doc_type']}:{row['itemId']}"
    value = row['Date']
    if isinstance(value, datetime):
        value = value.date()
    row['Date'] = value
    if not row['year_title'] and value:
        row['year_title'] = str(jdatetime.date.fromgregorian(date=value).year)
    return row


def normalize_persian_sql(column):
    return f"""
        REPLACE(
            REPLACE(
                CONVERT(NVARCHAR(MAX), {column})
                    COLLATE Latin1_General_100_BIN2,
                N'ي', N'ی'
            ),
            N'ك', N'ک'
        )
    """

def _sepidar_history(filters):
    conditions = []
    params = []

    customer = str(filters.get('customer_code') or '').strip()
    item_code = str(filters.get('item_code') or '').strip()
    part = _normalize_fa(filters.get('part') or '')
    gp = _normalize_fa(filters.get('g_p') or '')
    fiscal_ref = str(filters.get('fisicalyearref') or '').strip()
    doc_type = str(filters.get('doc_type') or '').strip()

    if customer:
        if _is_digits(customer):
            conditions.append('AND dl.Code = %s')
            params.append(customer)
        else:
            conditions.append('AND dl.Title LIKE %s')
            # Normalize to the variant common in Sepidar input data.
            params.append('%' + customer.replace('ی', 'ي').replace('ک', 'ك') + '%')

    if item_code:
        conditions.append('AND Item.Code = %s')
        params.append(item_code)
    if part:
        conditions.append('AND Item.Title LIKE %s')
        params.append('%' + part + '%')
    if gp:
        conditions.append('AND g_p.Title LIKE %s')
        params.append('%' + gp + '%')
    if fiscal_ref:
        if fiscal_ref not in FISCAL_YEAR_MAP:
            raise ValueError('سال مالی انتخاب‌شده نامعتبر است.')
        conditions.append('AND docs.FiscalYearRef = %s')
        params.append(int(fiscal_ref))
    if doc_type:
        if doc_type not in ('invoice', 'quotation', 'returned_invoice'):
            raise ValueError('نوع سند انتخاب‌شده نامعتبر است.')
        conditions.append('AND docs.doc_type = %s')
        params.append(doc_type)

    where_sql = '\n'.join(conditions)
    query = f"""
    SELECT TOP ({MAX_ROWS_PER_SOURCE})
        docs.Date,
        docs.Number,
        docs.coef,
        docs.doc_type,
        docs.Fee,
        docs.itemId,
        docs.NetPrice,
        docs.NetPriceInBaseCurrency,
        docs.Price,
        docs.PriceInBaseCurrency,
        docs.Quantity,
        docs.Rate,

        st.Number AS sales_type_code,
        {normalize_persian_sql('st.Title')} AS sales_type,

        p.CreationDate AS customer_creation_date,

        {normalize_persian_sql('dl.Title')} AS customer_title,
        {normalize_persian_sql('dl.Code')} AS customer_code,

        dl.DLId,

        {normalize_persian_sql('g1.Code')} AS sales_user_code,
        {normalize_persian_sql('g1.Title')} AS sales_user_group,

        {normalize_persian_sql('Item.Code')} AS item_code,
        {normalize_persian_sql('Item.Title')} AS item_title,

        {normalize_persian_sql('g_p.Title')} AS purchase_group,
        {normalize_persian_sql('g_s.Title')} AS sales_group,

        {normalize_persian_sql('fy.Title')} AS year_title,
        {normalize_persian_sql('curr.Title')} AS currency,

        (docs.Fee * docs.Quantity - docs.Discount)
            / NULLIF(docs.Quantity, 0) AS fee_after_discount

    FROM (
        SELECT
            I.Date, I.Number, I.FiscalYearRef,
            I.CustomerPartyRef, I.SaleTypeRef,
            I.CurrencyRef, I.Rate,
            II.Discount, II.ItemRef,
            II.Quantity, II.Fee,
            II.NetPrice, II.NetPriceInBaseCurrency,
            II.Price, II.PriceInBaseCurrency,
            II.InvoiceItemID AS itemId,
            1 AS coef,
            'invoice' AS doc_type
        FROM [SLS].[Invoice] I
        JOIN [SLS].[InvoiceItem] II
            ON II.InvoiceRef = I.InvoiceId

        UNION ALL

        SELECT
            I.Date, I.Number, I.FiscalYearRef,
            I.CustomerPartyRef, I.SaleTypeRef,
            I.CurrencyRef, I.Rate,
            II.Discount, II.ItemRef,
            II.Quantity, II.Fee,
            II.NetPrice, II.NetPriceInBaseCurrency,
            II.Price, II.PriceInBaseCurrency,
            II.QuotationItemID AS itemId,
            0 AS coef,
            'quotation' AS doc_type
        FROM [SLS].[Quotation] I
        JOIN [SLS].[QuotationItem] II
            ON II.QuotationRef = I.QuotationId

        UNION ALL

        SELECT
            I.Date, I.Number, I.FiscalYearRef,
            I.CustomerPartyRef, I.SaleTypeRef,
            I.CurrencyRef, I.Rate,
            II.Discount, II.ItemRef,
            II.Quantity, II.Fee,
            -II.NetPrice, -II.NetPriceInBaseCurrency,
            -II.Price, -II.PriceInBaseCurrency,
            II.ReturnedInvoiceItemID AS itemId,
            -1 AS coef,
            'returned_invoice' AS doc_type
        FROM [SLS].[ReturnedInvoice] I
        JOIN [SLS].[ReturnedInvoiceItem] II
            ON II.ReturnedInvoiceRef = I.ReturnedInvoiceId

    ) docs

    JOIN [SLS].[SaleType] st
        ON st.SaleTypeId = docs.SaleTypeRef

    JOIN [INV].[Item] Item
        ON Item.ItemID = docs.ItemRef

    LEFT JOIN [GNR].[Grouping] g_p
        ON g_p.GroupingID = Item.PurchaseGroupRef

    LEFT JOIN [GNR].[Grouping] g_s
        ON g_s.GroupingID = Item.SaleGroupRef

    JOIN [GNR].[Party] p
        ON p.PartyId = docs.CustomerPartyRef

    JOIN [ACC].[DL] dl
        ON dl.DLId = p.DLRef

    LEFT JOIN [GNR].[Grouping] g1
        ON g1.GroupingID = p.CustomerGroupingRef

    JOIN [FMK].[FiscalYear] fy
        ON fy.FiscalYearId = docs.FiscalYearRef

    JOIN [GNR].[Currency] curr
        ON curr.CurrencyID = docs.CurrencyRef

    WHERE 1 = 1
    {where_sql}

    ORDER BY docs.Date DESC, docs.itemId DESC
    """
    return [_normalize_result(rec, 'sepidar') for rec in _rows('sepidar', query, params)]


def _portal_history(filters):
    """Portal DB uses PostgreSQL (as configured through PG_ENGIN).

    Important financial mapping:
      * Raw SQL performs lookup/filtering only; financial fields of Portal
        rows are overwritten from actual QuotationItem/FactorItem properties.
      * Price includes line discounts and tax plus an allocated document
        addition. Quotation Rate is empty; Factor Rate falls back to
        the latest CurrencyAmount.open_rate for its currency.
      * Currency-converted fields remain NULL until conversion rules are agreed.
    """
    db = connections['default']
    qn = db.ops.quote_name
    tables = {
        'q': Quotation, 'qi': QuotationItem,
        'f': Factor, 'fi': FactorItem,
        'c': Customer, 'i': Item,
        'pg': PurchaseGroup, 'sg': SaleGroup,
        'au': AccountingUser, 'st': SaleType, 'curr': Currency,
    }
    t = {key: qn(model._meta.db_table) for key, model in tables.items()}

    # Each SELECT returns the same columns and uses the original template keys.
    sql = f"""
    WITH docs AS (
        SELECT
            q.request_date::date AS "Date",
            q.id::text AS "Number",
            0 AS coef, 'quotation'::text AS doc_type,
            qi.final_price::double precision AS "Fee",
            qi.id::bigint AS "itemId",
            (COALESCE(qi.final_price, 0) * COALESCE(qi.quantity, 0))::double precision AS "NetPrice",
            NULL::double precision AS "NetPriceInBaseCurrency",
            qi.final_amount::double precision AS "Price",
            NULL::double precision AS "PriceInBaseCurrency",
            qi.quantity::double precision AS "Quantity",
            NULL::double precision AS "Rate",  -- Portal quotation rate is not reported
            st.number::text AS sales_type_code,
            st.title::text AS sales_type,
            c.created_date AS customer_creation_date,
            c.title::text AS customer_title,
            c.sepidar_dl_code::text AS customer_code,
            c.sepidar_dl_id::bigint AS "DLId",
            au.sepidar_id::text AS sales_user_code,
            au.title::text AS sales_user_group,
            COALESCE(i.sku, qi.goods_code)::text AS item_code,
            COALESCE(i.part_number, qi.goods_name, qi.customer_goods_name)::text AS item_title,
            pg.title::text AS purchase_group,
            sg.title::text AS sales_group,
            curr.title::text AS currency,
            (COALESCE(qi.final_price, 0) - COALESCE(qi.discount_per_item, 0))::double precision AS fee_after_discount
        FROM {t['qi']} qi
        JOIN {t['q']} q ON q.id = qi.quotation_id
        LEFT JOIN {t['c']} c ON c.sepidar_party_id = q.customer_party_id
        LEFT JOIN {t['i']} i ON i.id = qi.goods_code_fk_id
        LEFT JOIN {t['pg']} pg ON pg.id = i.purchase_group_id
        LEFT JOIN {t['sg']} sg ON sg.id = i.sale_group_id
        LEFT JOIN {t['au']} au ON au.id = c.accounting_user_id
        LEFT JOIN {t['st']} st ON st.id = q.sale_type_id
        LEFT JOIN {t['curr']} curr ON curr.id = q.currency_ref_id
        WHERE COALESCE(q.is_deleted, false) = false
          AND COALESCE(qi.is_deleted, false) = false
          AND COALESCE(q.cancel, false) = false

        UNION ALL

        SELECT
            f.created_date::date AS "Date",
            f.id::text AS "Number",
            1 AS coef, 'invoice'::text AS doc_type,
            fi.price::double precision AS "Fee",
            fi.id::bigint AS "itemId",
            (COALESCE(fi.price, 0) * COALESCE(fi.quantity, 0))::double precision AS "NetPrice",
            NULL::double precision AS "NetPriceInBaseCurrency",
            fi.final_amount::double precision AS "Price",
            NULL::double precision AS "PriceInBaseCurrency",
            fi.quantity::double precision AS "Quantity",
            f.rate::double precision AS "Rate",
            st.number::text AS sales_type_code,
            st.title::text AS sales_type,
            c.created_date AS customer_creation_date,
            c.title::text AS customer_title,
            c.sepidar_dl_code::text AS customer_code,
            c.sepidar_dl_id::bigint AS "DLId",
            au.sepidar_id::text AS sales_user_code,
            au.title::text AS sales_user_group,
            COALESCE(i.sku, qitem.goods_code)::text AS item_code,
            COALESCE(i.part_number, fi.part_number_show, fi.product_name, qitem.goods_name)::text AS item_title,
            pg.title::text AS purchase_group,
            sg.title::text AS sales_group,
            curr.title::text AS currency,
            (COALESCE(fi.price, 0) - COALESCE(fi.discount_per_item, 0))::double precision AS fee_after_discount
        FROM {t['fi']} fi
        JOIN {t['f']} f ON f.id = fi.factor_id
        LEFT JOIN {t['q']} q ON q.id = f.q_id
        LEFT JOIN {t['qi']} qitem ON qitem.id = fi.qi_id
        LEFT JOIN {t['c']} c
          ON c.sepidar_party_id = COALESCE(f.customer_party_id, q.customer_party_id)
        LEFT JOIN {t['i']} i ON i.id = fi.goods_code_id
        LEFT JOIN {t['pg']} pg ON pg.id = i.purchase_group_id
        LEFT JOIN {t['sg']} sg ON sg.id = i.sale_group_id
        LEFT JOIN {t['au']} au ON au.id = c.accounting_user_id
        LEFT JOIN {t['st']} st ON st.id = f.sale_type_id
        LEFT JOIN {t['curr']} curr ON curr.id = COALESCE(f.currency_ref_id, q.currency_ref_id)
        WHERE COALESCE(f.is_deleted, false) = false
          AND COALESCE(fi.is_deleted, false) = false
          AND COALESCE(f.cancel, false) = false
    )
    SELECT * FROM docs
    WHERE 1 = 1
    """

    params = []
    customer = _normalize_fa(filters.get('customer_code') or '')
    item_code = str(filters.get('item_code') or '').strip()
    part = _normalize_fa(filters.get('part') or '')
    gp = _normalize_fa(filters.get('g_p') or '')
    fiscal_ref = str(filters.get('fisicalyearref') or '').strip()
    doc_type = str(filters.get('doc_type') or '').strip()

    if customer:
        if _is_digits(customer):
            sql += '\nAND customer_code = %s'
            params.append(customer)
        else:
            sql += '\nAND customer_title ILIKE %s'
            params.append('%' + customer + '%')
    if item_code:
        sql += '\nAND item_code = %s'
        params.append(item_code)
    if part:
        sql += '\nAND item_title ILIKE %s'
        params.append('%' + part + '%')
    if gp:
        sql += '\nAND purchase_group ILIKE %s'
        params.append('%' + gp + '%')
    if fiscal_ref:
        if fiscal_ref not in FISCAL_YEAR_MAP:
            raise ValueError('سال مالی انتخاب‌شده نامعتبر است.')
        jy = FISCAL_YEAR_MAP[fiscal_ref]
        start = jdatetime.date(jy, 1, 1).togregorian()
        end = jdatetime.date(jy + 1, 1, 1).togregorian()
        sql += '\nAND "Date" >= %s AND "Date" < %s'
        params.extend([start, end])
    if doc_type:
        if doc_type not in ('invoice', 'quotation', 'returned_invoice'):
            raise ValueError('نوع سند انتخاب‌شده نامعتبر است.')
        sql += '\nAND doc_type = %s'
        params.append(doc_type)

    sql += f'\nORDER BY "Date" DESC, "itemId" DESC LIMIT {MAX_ROWS_PER_SOURCE}'
    result = [_normalize_result(rec, 'portal') for rec in _rows('default', sql, params)]
    return _apply_portal_finance(result)




def _money(value):
    """Convert model-produced numbers without importing floating point artifacts."""
    from decimal import Decimal

    if value is None or value == '':
        return Decimal('0')
    return Decimal(str(value))


def _line_values(item, doc_type):
    """Use existing business properties (including tax and discount rules)."""
    fee = _money(item.fee_())
    gross = _money(item.net_price)
    qty = _money(item.quantity)
    discount = _money(item.discount_value)

    if doc_type == 'quotation':
        # QuotationItem.price implements the Rial-specific round_rial rule.
        # Its computed value already includes discount_value and tax.
        price_without_addition = _money(item.price)
        fee_after_discount = fee - discount / qty if qty else _money(0)
    else:
        # FactorItem has no equivalent price property. Match the breakdown
        # used in Factor.payment: row_price - discount_value + tax.
        price_without_addition = (
            _money(item.row_price) - discount + _money(item.tax)
        )
        fee_after_discount = _money(item.fee_after_discount)

    return {
        'Fee': fee,
        'NetPrice': gross,
        'fee_after_discount': fee_after_discount,
        'price_before_addition': price_without_addition,
        'weight': max(gross, _money(0)),
        'discount': discount,
        'tax': _money(item.tax),
    }


def _addition_shares(items, addition):
    """Split header addition over ALL active lines, not filtered visible lines.

    If all weights are zero, share equally. Send rounding remainder to the
    final item to ensure allocated shares total the document's addition.
    """
    from decimal import Decimal

    items = sorted(items, key=lambda obj: obj.pk)
    if not items:
        return {}

    amount = _money(addition)
    if not amount:
        return {}

    weights = [max(_money(obj.net_price), Decimal('0')) for obj in items]
    denom = sum(weights)
    if denom == 0:
        weights = [Decimal('1')] * len(items)
        denom = Decimal(len(items))

    shares = {}
    allocated = Decimal('0')
    for idx, (obj, weight) in enumerate(zip(items, weights)):
        share = amount - allocated if idx == len(items) - 1 else amount * weight / denom
        shares[obj.pk] = share
        allocated += share
    return shares


def _apply_portal_finance(rows):
    """Enrich Portal-only rows without changing Sepidar query or Dl API.

    The initial SQL may use stored final_amount to select rows, but those
    fields are replaced here with values calculated by real model properties.
    Document additions are allocated across all active lines of the document.
    """
    if not rows:
        return rows

    from collections import defaultdict
    from inquiry.models import CurrencyAmount

    quotation_ids = [int(r['itemId']) for r in rows if r['doc_type'] == 'quotation']
    invoice_ids = [int(r['itemId']) for r in rows if r['doc_type'] == 'invoice']

    qs_quotation = QuotationItem.objects.using('default').filter(
        pk__in=quotation_ids, is_deleted=False,
    ).select_related('quotation', 'quotation__currency_ref')
    qs_factor = FactorItem.objects.using('default').filter(
        pk__in=invoice_ids, is_deleted=False,
    ).select_related('factor', 'factor__q', 'factor__currency_ref',
                     'factor__q__currency_ref')

    quotation_items = {obj.pk: obj for obj in qs_quotation}
    factor_items = {obj.pk: obj for obj in qs_factor}

    # For an invoice, Factor.payment takes additions from factor.q.addition.
    # If there is no linked quotation, use Factor.addition as a fallback.
    def factor_addition(factor):
        quotation = factor.q
        if quotation is not None:
            return _money(quotation.addition)
        return _money(factor.addition)

    quotation_additions = {
        item.quotation_id: _money(item.quotation.addition)
        for item in quotation_items.values()
    }
    factor_additions = {
        item.factor_id: factor_addition(item.factor)
        for item in factor_items.values()
    }

    # Calculate shares using ALL active items per document. Using only the
    # currently filtered 3000 report rows would overallocate additions.
    q_docs_needing_shares = [
        pk for pk, amount in quotation_additions.items() if amount
    ]
    f_docs_needing_shares = [
        pk for pk, amount in factor_additions.items() if amount
    ]
    q_groups = defaultdict(list)
    f_groups = defaultdict(list)

    if q_docs_needing_shares:
        qs = QuotationItem.objects.using('default').filter(
            quotation_id__in=q_docs_needing_shares,
            is_deleted=False,
        ).select_related('quotation', 'quotation__currency_ref')
        for obj in qs:
            q_groups[obj.quotation_id].append(obj)

    if f_docs_needing_shares:
        qs = FactorItem.objects.using('default').filter(
            factor_id__in=f_docs_needing_shares,
            is_deleted=False,
        ).select_related('factor', 'factor__q', 'factor__currency_ref')
        for obj in qs:
            f_groups[obj.factor_id].append(obj)

    q_shares = {
        doc_id: _addition_shares(q_groups[doc_id], addition)
        for doc_id, addition in quotation_additions.items() if addition
    }
    f_shares = {
        doc_id: _addition_shares(f_groups[doc_id], addition)
        for doc_id, addition in factor_additions.items() if addition
    }

    def factor_currency_id(factor):
        if factor.currency_ref_id is not None:
            return factor.currency_ref_id
        return factor.q.currency_ref_id if factor.q is not None else None

    missing_rate_currency_ids = {
        factor_currency_id(fi.factor)
        for fi in factor_items.values()
        if not fi.factor.rate and factor_currency_id(fi.factor) is not None
    }
    latest_rates = {}
    if missing_rate_currency_ids:
        rates = CurrencyAmount.objects.using('default').filter(
            currency_id__in=missing_rate_currency_ids,
            is_deleted=False,
        ).order_by('currency_id', '-created_date', '-pk').values_list(
            'currency_id', 'open_rate'
        )
        for currency_id, open_rate in rates:
            if currency_id not in latest_rates:
                latest_rates[currency_id] = open_rate

    for row in rows:
        item_id = int(row['itemId'])
        if row['doc_type'] == 'quotation':
            item = quotation_items.get(item_id)
            if item is None:
                raise ValueError(f'Portal QuotationItem {item_id} not found.')
            values = _line_values(item, 'quotation')
            addition = q_shares.get(item.quotation_id, {}).get(item.pk, _money(0))
            # Quotation has no rate in this report even if inherited SLSDoc
            # defines a nullable rate column.
            row['Rate'] = None
        elif row['doc_type'] == 'invoice':
            item = factor_items.get(item_id)
            if item is None:
                raise ValueError(f'Portal FactorItem {item_id} not found.')
            values = _line_values(item, 'invoice')
            addition = f_shares.get(item.factor_id, {}).get(item.pk, _money(0))
            rate = item.factor.rate
            if not rate:
                rate = latest_rates.get(factor_currency_id(item.factor))
            row['Rate'] = float(rate) if rate is not None else None
        else:
            continue

        # Values remain compatible with current Django template and DataTable.
        row['Fee'] = float(values['Fee'])
        row['NetPrice'] = float(values['NetPrice'])
        row['fee_after_discount'] = float(values['fee_after_discount'])
        row['Price'] = float(values['price_before_addition'] + addition)
        # Diagnostic fields: no template changes required.
        row['addition_allocated'] = float(addition)
        row['discount_included'] = float(values['discount'])
        row['tax_included'] = float(values['tax'])
        qty = _money(item.quantity)
        row['fee_final'] = float(
            _money(row['Price']) / qty
        ) if qty else 0.0

    return rows


def get_sales_history_list(filters):
    """Return (merged_rows, potentially_truncated).

    Both sources are always read even if the other has no matching rows.
    Documents that exist in both databases remain as two separate source rows.
    """
    if not any((filters.get(name) or '').strip() for name in
               ('customer_code', 'item_code', 'g_p', 'part')):
        return [], False

    sepidar = _sepidar_history(filters)
    portal = _portal_history(filters)

    results = sepidar + portal
    results.sort(key=lambda x: (x['Date'] or date.min, x['row_key']), reverse=True)

    truncated = (len(sepidar) >= MAX_ROWS_PER_SOURCE or
                 len(portal) >= MAX_ROWS_PER_SOURCE)
    return results, truncated
