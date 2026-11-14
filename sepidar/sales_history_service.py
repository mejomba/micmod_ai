"""Read-only unified sales history from Sepidar (SQL Server) and Portal (PostgreSQL).

Copy this file to: sepidar/sales_history_service.py
The implementation is not executed here against live databases.
"""
from datetime import date, datetime, timedelta

import jdatetime
from django.db import connections

from extra_data.models import (
    AccountingUser, Customer, Item, PurchaseGroup, SaleGroup,
)
from factor.models import Factor, FactorItem
from micmod_base.base import Currency
from micmod_base.models import Quotation, QuotationItem, SaleType


MAX_ROWS_PER_SOURCE = 3000
SALES_HISTORY_PAGE_SIZE = 60
# From this day forward Portal is the authoritative source for invoice lines.
PORTAL_INVOICE_START = jdatetime.date(1405, 2, 10).togregorian()
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


# The column search boxes query both databases BEFORE each source's row cap.
# Keep these indexes synchronized with sales_history.html.
COLUMN_LABELS = (
    'منبع', 'شماره سند', 'مشتری', 'کد مشتری', 'کد کالا', 'عنوان کالا',
    'نوع سند', 'تاریخ', 'کارشناس', 'گروه خرید', 'گروه فروش', 'نوع فروش',
    'تعداد', 'فی', 'فی خالص', 'مبلغ نهایی', 'ارز', 'نرخ ارز',
)

_SEPIDAR_COLUMN_EXPRESSIONS = (
    None, 'docs.Number', 'dl.Title', 'dl.Code', 'Item.Code',
    'Item.Title', 'docs.doc_type', 'docs.Date', 'g1.Title', 'g_p.Title',
    'g_s.Title', 'st.Title', 'docs.Quantity', 'docs.Fee',
    '(docs.Fee * docs.Quantity - docs.Discount) / NULLIF(docs.Quantity, 0)',
    'docs.Price', 'curr.Title', 'docs.Rate',
)
_PORTAL_COLUMN_EXPRESSIONS = (
    None, '"Number"', 'customer_title', 'customer_code', 'item_code',
    'item_title', 'doc_type', '"Date"', 'sales_user_group', 'purchase_group',
    'sales_group', 'sales_type', '"Quantity"', '"Fee"',
    'fee_after_discount', '"Price"', 'currency', '"Rate"',
)
_ALLOWED_DOCUMENT_TYPES = {'invoice', 'quotation', 'returned_invoice'}


def _latin_digits(value):
    return str(value or '').translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789'))


def _history_date(value):
    """Read an ISO Gregorian date or a Jalali date entered by a user."""
    from datetime import date as date_type
    import re

    value = _latin_digits(value).strip()
    if not value:
        return None
    try:
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            return date_type.fromisoformat(value)
        parts = re.fullmatch(r'(\d{4})/(\d{1,2})/(\d{1,2})', value)
        if parts:
            return jdatetime.date(*map(int, parts.groups())).togregorian()
    except (ValueError, OverflowError):
        pass
    raise ValueError('تاریخ نامعتبر است؛ از قالب شمسی ۱۴۰۵/۰۸/۱۳ استفاده کنید.')


def _column_date_bounds(value):
    """Allow YYYY, YYYY/MM or YYYY/MM/DD for the date-column search."""
    from datetime import timedelta
    import re

    text = _latin_digits(value).strip()
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', text):
        start = _history_date(text)
        return start, start + timedelta(days=1)
    match = re.fullmatch(r'(\d{4})(?:/(\d{1,2})(?:/(\d{1,2}))?)?', text)
    if not match:
        raise ValueError('فیلتر ستون تاریخ باید به شکل ۱۴۰۵، ۱۴۰۵/۰۸ یا ۱۴۰۵/۰۸/۱۳ باشد.')
    year, month, day = [int(v) if v is not None else None for v in match.groups()]
    try:
        if month is None:
            return (jdatetime.date(year, 1, 1).togregorian(),
                    jdatetime.date(year + 1, 1, 1).togregorian())
        if day is None:
            next_year = year + 1 if month == 12 else year
            next_month = 1 if month == 12 else month + 1
            return (jdatetime.date(year, month, 1).togregorian(),
                    jdatetime.date(next_year, next_month, 1).togregorian())
        start = jdatetime.date(year, month, day).togregorian()
        return start, start + timedelta(days=1)
    except (ValueError, OverflowError):
        raise ValueError('تاریخ جست‌وجوشده معتبر نیست.')


def _column_constraints(filters, source):
    """Return (SQL conditions, bound parameters, skip_source).

    Search is applied to the entire source in SQL, before TOP/LIMIT. Never
    interpolate untrusted values into SQL expressions.
    """
    from datetime import timedelta
    from decimal import Decimal, InvalidOperation

    raw_source = str(filters.get('col_0') or '').strip()
    if raw_source and raw_source not in ('portal', 'sepidar'):
        raise ValueError('منبع گزارش نامعتبر است.')
    if raw_source and raw_source != source:
        return [], [], True

    expressions = (_SEPIDAR_COLUMN_EXPRESSIONS if source == 'sepidar'
                   else _PORTAL_COLUMN_EXPRESSIONS)
    conditions, params = [], []
    date_expr = expressions[7]

    start = _history_date(filters.get('date_from'))
    end = _history_date(filters.get('date_to'))
    if start and end and start > end:
        raise ValueError('تاریخ شروع نباید بعد از تاریخ پایان باشد.')
    if start:
        conditions.append(date_expr + ' >= %s')
        params.append(start)
    if end:
        conditions.append(date_expr + ' < %s')
        params.append(end + timedelta(days=1))

    for idx in range(1, len(COLUMN_LABELS)):
        value = _normalize_fa(_latin_digits(filters.get('col_' + str(idx)))).strip()[:120]
        if not value:
            continue
        expr = expressions[idx]
        if idx == 7:
            lower, upper = _column_date_bounds(value)
            conditions.extend((date_expr + ' >= %s', date_expr + ' < %s'))
            params.extend((lower, upper))
        elif idx == 6:
            if value not in _ALLOWED_DOCUMENT_TYPES:
                raise ValueError('نوع سند جست‌وجوشده نامعتبر است.')
            conditions.append(expr + ' = %s')
            params.append(value)
        elif idx in (12, 13, 14, 15, 17):
            try:
                number = Decimal(value.replace(',', '').replace('٬', ''))
            except InvalidOperation:
                raise ValueError('برای جست‌وجوی ستون‌های عددی، مقدار عددی وارد کنید.')
            if not number.is_finite():
                raise ValueError('مقدار عددی معتبر نیست.')
            conditions.append(expr + ' = %s')
            params.append(number)
        elif source == 'sepidar':
            # Normalize Arabic/Persian letter variants without mutating data.
            normalized = normalize_persian_sql(expr)
            conditions.append(normalized + ' LIKE %s')
            params.append('%' + value + '%')
        else:
            normalized = "REPLACE(REPLACE(COALESCE(" + expr + "::text,''),'ي','ی'),'ك','ک')"
            conditions.append(normalized + ' ILIKE %s')
            params.append('%' + value + '%')
    return conditions, params, False

def _document_types(filters):
    """Intersect valid document filters; conflicting choices match no documents.

    Each input is validated against the complete supported set, not the
    progressively narrowed intersection. Otherwise two individually valid but
    contradictory filters incorrectly raise a validation error.
    """
    allowed = set(_ALLOWED_DOCUMENT_TYPES)
    for key in ('doc_type', 'col_6'):
        value = str(filters.get(key) or '').strip()
        if value:
            if value not in _ALLOWED_DOCUMENT_TYPES:
                raise ValueError('نوع سند انتخاب‌شده نامعتبر است.')
            allowed.intersection_update((value,))
    return allowed


def _sepidar_invoice_needed(filters):
    """Avoid Sepidar entirely for recent invoice-only searches."""
    if 'invoice' not in _document_types(filters):
        return False
    bounds = []
    start = _history_date(filters.get('date_from'))
    if start:
        bounds.append(start)
    column_date = str(filters.get('col_7') or '').strip()
    if column_date:
        bounds.append(_column_date_bounds(column_date)[0])
    fiscal_ref = str(filters.get('fisicalyearref') or '').strip()
    if fiscal_ref:
        if fiscal_ref not in FISCAL_YEAR_MAP:
            raise ValueError('سال مالی انتخاب‌شده نامعتبر است.')
        bounds.append(jdatetime.date(FISCAL_YEAR_MAP[fiscal_ref], 1, 1).togregorian())
    return not bounds or max(bounds) < PORTAL_INVOICE_START


def _portal_sepidar_quotation_ids():
    """Get the local IDs of Sepidar quotations already represented in Portal.

    Portal Quotation.sepidar_number must be matched against SQL Server
    SLS.Quotation.QuotationId (NOT SLS.Quotation.Number). The separate
    sepidar_quotation_id is retained as an exact-ID fallback for older records.
    No fiscal-year inference is needed for a unique QuotationId.
    """
    references = Quotation.objects.using('default').filter(
        is_deleted=False, cancel=False,
    ).exclude(
        sepidar_number__isnull=True, sepidar_quotation_id__isnull=True,
    ).values_list('sepidar_number', 'sepidar_quotation_id')

    linked_ids = set()
    for sepidar_number, sepidar_quotation_id in references:
        for value in (sepidar_number, sepidar_quotation_id):
            if value is not None and int(value) > 0:
                linked_ids.add(int(value))
    return linked_ids


def _matches_portal_quotation(record, linked_ids):
    """Do not confuse the displayed Sepidar Number with its QuotationId."""
    doc_id = record.get('sepidar_doc_id')
    return (record.get('doc_type') == 'quotation'
            and doc_id is not None and int(doc_id) in linked_ids)


def _read_sepidar_unique_rows(sql, params, linked_ids):
    """Use one SQL Server cursor; fetch until 3000 unique lines are found.

    Filtering after TOP 3000 would silently hide unrelated older quotations.
    Streaming the ordered result avoids that problem without issuing another
    Sepidar query for each duplicate batch.
    """
    result = []
    with connections['sepidar'].cursor() as cursor:
        cursor.execute(sql, params)
        columns = [desc[0].lower() for desc in cursor.description]
        while len(result) <= MAX_ROWS_PER_SOURCE:
            batch = cursor.fetchmany(256)
            if not batch:
                break
            for values in batch:
                record = dict(zip(columns, values))
                if _matches_portal_quotation(record, linked_ids):
                    continue
                result.append(_normalize_result(record, 'sepidar'))
                if len(result) > MAX_ROWS_PER_SOURCE:
                    break
    return result


def _sepidar_history(filters, *, offset=0, page_size=None):
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

    more_conditions, more_params, skip_source = _column_constraints(filters, 'sepidar')
    types = _document_types(filters)
    if skip_source or not types:
        return []
    if not _sepidar_invoice_needed(filters):
        types.discard('invoice')
    if not types:
        return []
    if types != {'invoice', 'quotation', 'returned_invoice'}:
        placeholders = ', '.join(['%s'] * len(types))
        conditions.append(f'AND docs.doc_type IN ({placeholders})')
        params.extend(sorted(types))
    # The Sepidar invoice cutoff is pushed into the source invoice table, so
    # the index on Invoice.Date can be used before joining invoice items.
    conditions.extend('AND ' + condition for condition in more_conditions)
    params.extend(more_params)
    where_sql = '\n'.join(conditions)
    linked_ids = _portal_sepidar_quotation_ids() if 'quotation' in types else set()
    # Exclude existing Portal quotations in SQL BEFORE TOP, with one Sepidar
    # query and bound parameters. For large lists, filter using that same
    # remote cursor instead of issuing additional SQL Server requests.
    use_sql_exclusion = bool(linked_ids) and len(linked_ids) <= 900
    if use_sql_exclusion:
        placeholders = ', '.join(['%s'] * len(linked_ids))
        where_sql += (
            f"\nAND (docs.doc_type <> 'quotation' OR "
            f"docs.sepidar_doc_id NOT IN ({placeholders}))"
        )
        params.extend(sorted(linked_ids))
    paged = page_size is not None
    if paged and (offset < 0 or page_size < 1 or page_size > SALES_HISTORY_PAGE_SIZE
                  or offset > MAX_ROWS_PER_SOURCE):
        raise ValueError('درخواست صفحه فروش معتبر نیست.')
    sql_top = (f'TOP ({MAX_ROWS_PER_SOURCE + 1})'
               if not paged and (not linked_ids or use_sql_exclusion) else '')
    query = f"""
    SELECT {sql_top}
        docs.Date,
        docs.sepidar_doc_id,
        docs.FiscalYearRef,
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
            NULL AS sepidar_doc_id,
            1 AS coef,
            'invoice' AS doc_type
        FROM [SLS].[Invoice] I
        JOIN [SLS].[InvoiceItem] II
            ON II.InvoiceRef = I.InvoiceId
        WHERE I.Date < %s
          AND {'1 = 1' if 'invoice' in types else '1 = 0'}

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
            I.QuotationId AS sepidar_doc_id,
            0 AS coef,
            'quotation' AS doc_type
        FROM [SLS].[Quotation] I
        JOIN [SLS].[QuotationItem] II
            ON II.QuotationRef = I.QuotationId
        WHERE {'1 = 1' if 'quotation' in types else '1 = 0'}

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
            NULL AS sepidar_doc_id,
            -1 AS coef,
            'returned_invoice' AS doc_type
        FROM [SLS].[ReturnedInvoice] I
        JOIN [SLS].[ReturnedInvoiceItem] II
            ON II.ReturnedInvoiceRef = I.ReturnedInvoiceId
        WHERE {'1 = 1' if 'returned_invoice' in types else '1 = 0'}

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

    ORDER BY docs.Date DESC, docs.itemId DESC, docs.doc_type DESC
    """
    # SQL Server pages are applied inside the database, before transferring
    # rows to Django. The extra row detects whether another page exists.
    if paged:
        fetch_size = min(page_size + 1, MAX_ROWS_PER_SOURCE + 1 - offset)
        if linked_ids and not use_sql_exclusion:
            # SQL Server's parameter limit prevents an IN list of these IDs.
            # Keep the proven deduplicating cursor fallback; only requested
            # rows are sent to the client, even in this uncommon case.
            return _read_sepidar_unique_rows(
                query, [PORTAL_INVOICE_START] + params, linked_ids
            )[offset:offset + fetch_size]
        query += "\nOFFSET %s ROWS FETCH NEXT %s ROWS ONLY"
        page = _rows('sepidar', query, [PORTAL_INVOICE_START] + params
                     + [offset, fetch_size])
        return [_normalize_result(record, 'sepidar') for record in page]
    # Legacy bulk contract retained for full backend summary/export and tests.
    return _read_sepidar_unique_rows(
        query, [PORTAL_INVOICE_START] + params, linked_ids
    )[:MAX_ROWS_PER_SOURCE + 1]


def _portal_history(filters, *, offset=0, page_size=None):
    """Portal DB uses PostgreSQL (as configured through PG_ENGIN).

    Important financial mapping:
      * Raw SQL performs lookup/filtering only; financial fields of Portal
        rows are overwritten from actual QuotationItem/FactorItem properties.
      * Price includes line discounts and tax plus an allocated document
        addition. Quotation Rate is empty; Factor Rate falls back to
        the latest CurrencyAmount.open_rate for its currency.
      * Currency-converted fields remain NULL until conversion rules are agreed.
    """
    # Avoid PostgreSQL entirely for Sepidar-only, returned-invoice-only or
    # contradictory document filters. The other CTE arm is then pruned by the
    # PostgreSQL planner using an explicit FALSE condition.
    more_conditions, more_params, skip_source = _column_constraints(filters, 'portal')
    types = _document_types(filters).intersection({'quotation', 'invoice'})
    if skip_source or not types:
        return []
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
          AND {'TRUE' if 'quotation' in types else 'FALSE'}

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
          AND f.created_date >= %s
          AND {'TRUE' if 'invoice' in types else 'FALSE'}
    )
    SELECT * FROM docs
    WHERE 1 = 1
    """

    # The source-level invoice date predicate precedes all outer filters.
    params = [PORTAL_INVOICE_START]
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

    sql += ''.join('\nAND ' + condition for condition in more_conditions)
    params.extend(more_params)

    # Invoice cutoff was applied directly to Factor.created_date before JOINs.
    # Pagination runs in PostgreSQL rather than slicing a fetched result set.
    if page_size is None:
        sql += f'\nORDER BY "Date" DESC, "itemId" DESC, doc_type DESC LIMIT {MAX_ROWS_PER_SOURCE}'
    else:
        if offset < 0 or offset > MAX_ROWS_PER_SOURCE or not 1 <= page_size <= SALES_HISTORY_PAGE_SIZE:
            raise ValueError('درخواست صفحه فروش معتبر نیست.')
        sql += '\nORDER BY "Date" DESC, "itemId" DESC, doc_type DESC LIMIT %s OFFSET %s'
        params.extend([min(page_size + 1, MAX_ROWS_PER_SOURCE + 1 - offset), offset])
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

    Invoices before the cutoff come from Sepidar, newer ones from Portal.
    Portal-linked quotations are not repeated from Sepidar.
    """
    # When explicitly filtering to recent invoices, skip SQL Server entirely.
    # _sepidar_history also skips its connection when source=Portal.
    sepidar = _sepidar_history(filters)
    portal = _portal_history(filters)

    results = sepidar[:MAX_ROWS_PER_SOURCE] + portal
    results.sort(key=lambda x: (x['Date'] or date.min, x['row_key']), reverse=True)

    truncated = (len(sepidar) > MAX_ROWS_PER_SOURCE or
                 len(portal) >= MAX_ROWS_PER_SOURCE)
    return results, truncated


def get_sales_history_page(filters, *, sepidar_offset=0, portal_offset=0,
                           sepidar_done=False, portal_done=False,
                           page_size=SALES_HISTORY_PAGE_SIZE):
    """Fetch one globally sorted page, with independent offsets per database.

    Each source loads at most page_size+1 rows from SQL, and only consumed
    rows advance that source's cursor. Unconsumed source rows are fetched by
    the next scroll request, so interleaved dates never skip or repeat rows.
    The 3000-per-source safety cap remains explicit and detectable.
    """
    if (not isinstance(page_size, int) or not 1 <= page_size <= SALES_HISTORY_PAGE_SIZE
            or any(not isinstance(n, int) or n < 0 or n > MAX_ROWS_PER_SOURCE
                   for n in (sepidar_offset, portal_offset))
            or not isinstance(sepidar_done, bool) or not isinstance(portal_done, bool)):
        raise ValueError('درخواست صفحه فروش معتبر نیست.')

    # A consumed source need not be queried again for every subsequent scroll.
    sepidar = ([] if sepidar_done else _sepidar_history(
        filters, offset=sepidar_offset, page_size=page_size))
    portal = ([] if portal_done else _portal_history(
        filters, offset=portal_offset, page_size=page_size))

    def order_key(row):
        return (row.get('Date') or date.min, int(row.get('itemId') or 0),
                row.get('doc_type') or '', row.get('source') or '')

    combined = sorted(sepidar + portal, key=order_key, reverse=True)
    page = combined[:page_size]
    sep_used = sum(row['source'] == 'sepidar' for row in page)
    portal_used = len(page) - sep_used
    next_sep = sepidar_offset + sep_used
    next_portal = portal_offset + portal_used
    truncated = (
        (next_sep >= MAX_ROWS_PER_SOURCE and len(sepidar) > sep_used)
        or (next_portal >= MAX_ROWS_PER_SOURCE and len(portal) > portal_used)
    )
    done = {
        'sepidar': sepidar_done or next_sep >= MAX_ROWS_PER_SOURCE
                   or len(sepidar) <= sep_used,
        'portal': portal_done or next_portal >= MAX_ROWS_PER_SOURCE
                  or len(portal) <= portal_used,
    }
    return {
        'rows': page,
        'row_count': len(page),
        'offsets': {'sepidar': next_sep, 'portal': next_portal},
        'done': done,
        'has_more': not all(done.values()),
        'truncated': truncated,
    }
