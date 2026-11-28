"""Render payment schedules from already-loaded order payment rows."""
from html import escape


def payment_currency(item, order_currency):
    header = item.payment if item.payment_id else None
    currency = (header.currency if header else None) or item.currency or order_currency
    return currency.title_en if currency and currency.title_en else 'ارز نامشخص'


def payment_amount(item):
    # Keep fractional amounts, with grouping and no unnecessary trailing zeroes.
    from decimal import Decimal
    amount = Decimal(str(item.total_amount))
    return format(amount, ',f').rstrip('0').rstrip('.') if amount.as_tuple().exponent < 0 else format(amount, ',f')


def payment_label(item, order_currency):
    return escape(f'{payment_amount(item)} {payment_currency(item, order_currency)}')


def render_payment_schedule(items, order_currency, today):
    """Return (upcoming HTML, past HTML); include each dated active row once."""
    upcoming, past = [], []
    for item in items:
        if item.is_deleted or item.pay_date is None:
            continue
        if item.pay_date > today or (item.pay_date == today and not item.is_pay):
            upcoming.append(item)
        else:
            past.append(item)

    upcoming.sort(key=lambda item: (item.pay_date, item.pk))
    past.sort(key=lambda item: (item.is_pay, item.pay_date, item.pk))

    def render(item):
        if item.is_pay:
            color, symbol, status = 'success', '✓', 'پرداخت شده'
        elif item.pay_date < today:
            color, symbol, status = 'danger', '⚠', 'سررسید گذشته و پرداخت نشده'
        elif item.pay_date == today:
            color, symbol, status = 'warning', '◷', 'سررسید امروز'
        else:
            color, symbol, status = 'info', '◷', 'برنامه‌ریزی شده'
        label = f'{payment_label(item, order_currency)} {item.pay_date:%Y/%m/%d}'
        return (
            f'<div class="text-{color} text-nowrap py-1" dir="ltr" '
            f'title="{status}"><span role="img" aria-label="{status}">{symbol}</span> {label}</div>'
        )

    def render_column(rows):
        return ''.join(map(render, rows)) or '<span class="text-muted">—</span>'

    return render_column(upcoming), render_column(past)


def render_payment_links(items, order_currency, payment_url):
    """Keep existing header links; unlinked rows remain visible as plain text."""
    rows = []
    for item in items:
        if item.is_deleted:
            continue
        label = payment_label(item, order_currency)
        if item.payment_id:
            url = escape(str(payment_url(item.payment_id)), quote=True)
            rows.append(f'<a target="_blank" rel="noopener" href="{url}" dir="ltr">{label}</a>')
        else:
            rows.append(f'<span class="text-muted text-nowrap" dir="ltr" title="بدون سربرگ پرداخت">{label}</span>')
    return '<hr>'.join(rows)
