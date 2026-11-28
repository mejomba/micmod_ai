"""Trade order payment filters and unpaginated, currency-separated totals."""
from datetime import date

from django.db.models import Case, CharField, Count, DecimalField, Exists, F, OuterRef, Q, Sum, Value, When
from django.db.models.functions import Cast, Coalesce, NullIf

from .models import OrderPaymentItem


PAYMENT_FILTERS = {
    'scheduled': 'پرداخت برنامه‌ریزی شده',
    'overdue': 'پرداخت منقضی شده',
    'today': 'پرداخت سررسید امروز',
    'due_until': 'پرداخت تا سررسید تاریخ انتخابی',
    'date_range': 'پرداخت در بازه زمانی',
}
SUMMARY_TYPES = ('paid', 'overdue', 'today', 'scheduled')


def parse_payment_date(value):
    try:
        result = date.fromisoformat(value or '')
        if result.isoformat() != value:
            raise ValueError
        return result
    except (ValueError, TypeError):
        raise ValueError('تاریخ معتبر میلادی را انتخاب کنید.') from None


def apply_payment_filter(queryset, mode, start, end, today):
    """Filter orders by existence of a single matching active payment row."""
    if not mode:
        return queryset
    items = OrderPaymentItem.objects.filter(order_id=OuterRef('pk'), is_deleted=False)
    if mode == 'scheduled':
        items = items.filter(pay_date__gt=today)
    elif mode == 'overdue':
        items = items.filter(pay_date__lt=today, is_pay=False)
    elif mode == 'today':
        items = items.filter(pay_date=today)
    elif mode == 'due_until':
        items = items.filter(pay_date__lte=parse_payment_date(end), is_pay=False)
    elif mode == 'date_range':
        start_date, end_date = parse_payment_date(start), parse_payment_date(end)
        if start_date > end_date:
            raise ValueError('تاریخ شروع نباید بعد از تاریخ پایان باشد.')
        items = items.filter(pay_date__range=(start_date, end_date))
    else:
        raise ValueError('فیلتر پرداخت نامعتبر است.')
    return queryset.filter(Exists(items))


def format_total(value):
    label = format(value or 0, ',f') if value is not None else '0'
    return label.rstrip('0').rstrip('.') if '.' in label else label


def payment_totals(queryset, today):
    """Aggregate all payment rows of matching orders, not only matching rows or page."""
    # Clear sorting before selecting IDs: related-field ordering must not multiply rows.
    order_ids = queryset.order_by().values('pk').distinct()
    items = OrderPaymentItem.objects.filter(order_id__in=order_ids, is_deleted=False)
    # Mirror the list's currency precedence. Blank selected labels are unknown.
    currency = Coalesce(
        NullIf(Case(
            When(payment__currency_id__isnull=False, then=F('payment__currency__title_en')),
            When(currency_id__isnull=False, then=F('currency__title_en')),
            default=F('order__currency__title_en'),
            output_field=CharField(),
        ), Value('')),
        Value('ارز نامشخص'),
        output_field=CharField(),
    )
    categories = {
        'paid': Q(is_pay=True),
        'overdue': Q(is_pay=False, pay_date__lt=today),
        'today': Q(is_pay=False, pay_date=today),
        'scheduled': Q(is_pay=False, pay_date__gt=today),
        'undated': Q(is_pay=False, pay_date__isnull=True),
    }
    # Convert the legacy FloatField to numeric for decimal summation.
    amount = Cast('total_amount', DecimalField(max_digits=38, decimal_places=12))
    grouped = items.annotate(summary_currency=currency).order_by().values('summary_currency').annotate(
        **{name: Sum(amount, filter=condition) for name, condition in categories.items()},
        **{name + '_count': Count('pk', filter=condition) for name, condition in categories.items()},
    ).order_by('summary_currency')
    totals = {name: [] for name in (*SUMMARY_TYPES, 'undated')}
    for row in grouped:
        for name in totals:
            if row[name + '_count']:
                totals[name].append({
                    'currency': row['summary_currency'],
                    'amount': format_total(row[name]),
                    'count': row[name + '_count'],
                })
    return {'order_count': order_ids.count(), 'totals': totals, 'as_of': today.isoformat()}
