"""Role-scoped operational metrics for the portal landing page.

Counts use creation timestamps for new documents and ChangeLog transitions for
actions. Never substitute a document's last_update_date for an action date.
"""
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db.models import BigIntegerField, Count, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from changelog.models import ChangeLog
from factor.models import Factor
from inquiry.models import PriceInquiryResult
from micmod_base.models import Quotation
from order.models import Order, OrderBazar
from payment.models import PaymentOrder
from pcba.models import Contract
from workflow.models import FlowAdminGroup


EXECUTIVE_GROUPS = frozenset(('total_admin', 'senior_manager', 'executive_admin'))
METRICS = (
    'invoice_count', 'quotation_count', 'inquiry_count', 'purchase_count',
    'dispatch_count', 'receipt_count', 'finance_approval_count', 'paid_count',
    'contract_count',
)
ROLE_PREFIXES = {
    'sales': ('sales_', 'sale_'),
    'trade': ('trade_',),
    'bazar': ('bazar_',),
    'warehouse': ('wh_', 'warehouse_', 'factor_collector', 'factor_send_or_delivery',
                  'factor_delivery_approve', 'factor_final_check'),
    'finance': ('accounting_', 'Accounting_', 'finance_', 'payment_'),
    'technical': ('pcba', 'technical', 'tech_', 'engineer_'),
}


def clamp_days(value):
    try:
        return max(1, min(int(value), 365))
    except (ValueError, TypeError):
        return 30


def visible_users(viewer):
    """Return an explicitly bounded user scope, never trusting the requested id."""
    User = get_user_model()
    group_rows = list(viewer.groups.values_list('id', 'name'))
    own_group_ids = [row[0] for row in group_rows]
    names = {row[1] for row in group_rows}
    if viewer.is_superuser or names.intersection(EXECUTIVE_GROUPS):
        return User.objects.filter(is_active=True).order_by('username'), 'executive'

    direct_ids = set(User.objects.filter(head_id=viewer.pk, is_active=True)
                     .values_list('pk', flat=True))
    child_group_ids = list(
        FlowAdminGroup.objects.filter(group_rel_id__in=own_group_ids)
        .values_list('group_child__id', flat=True)
        .exclude(group_child__id__isnull=True)
    )
    if child_group_ids:
        direct_ids.update(
            User.objects.filter(groups__id__in=child_group_ids, is_active=True)
            .values_list('pk', flat=True)
        )

    is_manager = bool(direct_ids) or any(
        name.endswith('_admin') for name in names
    ) or bool(child_group_ids)
    if is_manager:
        direct_ids.add(viewer.pk)
        return (User.objects.filter(pk__in=direct_ids, is_active=True)
                .distinct().order_by('username')), 'manager'

    return User.objects.filter(pk=viewer.pk), 'user'


def _new_row(user):
    name = user.get_full_name().strip() or user.username
    groups = {g.name for g in user.groups.all()}
    roles = {
        role for role, prefixes in ROLE_PREFIXES.items()
        if any(any(group.startswith(prefix) for prefix in prefixes) for group in groups)
    }
    row = {'id': user.pk, 'name': name, 'roles': roles,
           'invoice_amounts': [], 'quotation_amounts': [], 'customers': 0,
           'contract_amount': Decimal('0')}
    row.update({metric: 0 for metric in METRICS})
    return row


def _sales_metrics(rows, since, until):
    customers = defaultdict(set)
    for model, count_key, amount_key in (
        (Factor, 'invoice_count', 'invoice_amounts'),
        (Quotation, 'quotation_count', 'quotation_amounts'),
    ):
        qs = model.objects.filter(
            is_deleted=False, cancel=False,
            creator_user_id__in=rows.keys(),
            created_date__gte=since, created_date__lte=until,
        )
        for item in qs.values(
            'creator_user_id', 'currency_ref__title_en', 'currency_ref__title'
        ).annotate(count=Count('pk'), amount=Sum('final_price')):
            row = rows[item['creator_user_id']]
            row[count_key] += item['count']
            row[amount_key].append({
                'currency': item['currency_ref__title_en'] or
                            item['currency_ref__title'] or 'ارز نامشخص',
                'amount': item['amount'] or 0,
            })

        for uid, customer_id in (
            qs.exclude(customer_party_id__isnull=True)
            .values_list('creator_user_id', 'customer_party_id').distinct()
        ):
            customers[uid].add(customer_id)

    for uid, values in customers.items():
        rows[uid]['customers'] = len(values)


def _inquiry_metrics(rows, since, until):
    # Multiple supplier offers in one inquiry file count as one answered inquiry per user.
    for item in (
        PriceInquiryResult.objects.filter(
            is_deleted=False, creator_user_id__in=rows.keys(),
            created_date__gte=since, created_date__lte=until,
            price_inquiry_file_id__isnull=False,
        ).values('creator_user_id')
        .annotate(count=Count('price_inquiry_file_id', distinct=True))
    ):
        rows[item['creator_user_id']]['inquiry_count'] = item['count']


def _contract_metrics(rows, since, until):
    # Same formula as Contract.contract_cost used on the contracts list.
    cost = ExpressionWrapper(
        F('customer_total_board_count') * F('pad_count') * F('pad_cost') +
        Coalesce(F('first_setup_cost'), Value(0), output_field=BigIntegerField()),
        output_field=BigIntegerField(),
    )
    for item in (
        Contract.objects.filter(
            is_deleted=False, creator_user_id__in=rows.keys(),
            created_date__gte=since, created_date__lte=until,
        ).values('creator_user_id')
        .annotate(count=Count('pk'), amount=Sum(cost))
    ):
        row = rows[item['creator_user_id']]
        row['contract_count'] = item['count']
        row['contract_amount'] = item['amount'] or 0


def _truthy(value):
    return value is True or value == 1 or (
        isinstance(value, str) and value.lower() in ('true', '1')
    )


def _list_value(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        import json
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except (ValueError, TypeError):
            return []
    return []


def _became_true(fields, key):
    pair = fields.get(key)
    return (isinstance(pair, (tuple, list)) and len(pair) == 2
            and not _truthy(pair[0]) and _truthy(pair[1]))


def _purchase_created(fields):
    pair = fields.get('buy_factors')
    return (isinstance(pair, (tuple, list)) and len(pair) == 2
            and not _list_value(pair[0]) and bool(_list_value(pair[1])))


def _transition_metrics(rows, since, until):
    """Only count actual transitions with a known actor, once per document."""
    types = ContentType.objects.get_for_models(Factor, Order, OrderBazar, PaymentOrder)
    kinds = {ct.pk: model for model, ct in types.items()}
    seen = set()
    qs = (
        ChangeLog.objects.filter(
            Q(creator_user_id__in=rows.keys()) | Q(editor_user_id__in=rows.keys()),
            is_deleted=False, action=2, content_type_id__in=kinds,
            created_date__gte=since, created_date__lte=until,
        ).only('content_type_id', 'object_id', 'diff_json',
               'creator_user_id', 'editor_user_id')
        .order_by('created_date', 'pk')
    )
    for log in qs.iterator(chunk_size=1000):
        fields = (log.diff_json or {}).get('fields') or {}
        if not isinstance(fields, dict):
            continue
        actor_id = log.creator_user_id or log.editor_user_id
        # Legacy order conversions sometimes wrote the editor onto the order
        # without passing request into its ChangeLog. Attribute only if that
        # editor changed in the same atomic diff; never use today's editor.
        if not actor_id:
            editor_change = fields.get('editor_user_id')
            if isinstance(editor_change, (list, tuple)) and len(editor_change) == 2:
                actor_id = editor_change[1]
        if actor_id not in rows:
            continue
        model = kinds[log.content_type_id]
        metrics = []
        if model is Factor:
            if _became_true(fields, 'deliver_to_customer'):
                metrics.append('dispatch_count')
            if _became_true(fields, 'accounting_confirm'):
                metrics.append('finance_approval_count')
        elif model in (Order, OrderBazar):
            if _became_true(fields, 'receipt_in_wh'):
                metrics.append('receipt_count')
            if _purchase_created(fields):
                metrics.append('purchase_count')
        elif model is PaymentOrder and _became_true(fields, 'is_paid'):
            metrics.append('paid_count')

        for metric in metrics:
            key = (log.content_type_id, log.object_id, metric)
            if key not in seen:
                rows[actor_id][metric] += 1
                seen.add(key)


def build_report(viewer, days=30, selected_user_id=None):
    days = clamp_days(days)
    user_qs, scope = visible_users(viewer)
    permitted_ids = set(user_qs.values_list('pk', flat=True))

    if selected_user_id not in (None, ''):
        try:
            selected_user_id = int(selected_user_id)
        except (ValueError, TypeError):
            selected_user_id = -1
        if selected_user_id not in permitted_ids:
            from django.http import Http404
            raise Http404('User not in your reporting scope')
    else:
        selected_user_id = None

    selector_users = list(user_qs.only('id', 'username', 'first_name', 'last_name'))
    selected_users = [
        user for user in selector_users
        if selected_user_id is None or user.pk == selected_user_id
    ]
    # Prefetch groups for the selected users only.
    selected_users = list(
        get_user_model().objects.filter(pk__in=[u.pk for u in selected_users])
        .prefetch_related('groups').order_by('username')
    )
    rows = {user.pk: _new_row(user) for user in selected_users}

    until = timezone.now()
    since = until - timedelta(days=days)
    if rows:
        _sales_metrics(rows, since, until)
        _inquiry_metrics(rows, since, until)
        _transition_metrics(rows, since, until)
        _contract_metrics(rows, since, until)

    sections = [
        {'key': 'sales', 'title': 'فروش',
         'rows': [r for r in rows.values() if 'sales' in r['roles']
                  or r['invoice_count'] or r['quotation_count']]},
        {'key': 'sourcing', 'title': 'بازرگانی و بازار',
         'rows': [r for r in rows.values() if {'trade', 'bazar'} & r['roles']
                  or r['inquiry_count'] or r['purchase_count']]},
        {'key': 'warehouse', 'title': 'انبار',
         'rows': [r for r in rows.values() if 'warehouse' in r['roles']
                  or r['dispatch_count'] or r['receipt_count']]},
        {'key': 'finance', 'title': 'مالی',
         'rows': [r for r in rows.values() if 'finance' in r['roles']
                  or r['finance_approval_count'] or r['paid_count']]},
        {'key': 'technical', 'title': 'فنی',
         'rows': [r for r in rows.values() if 'technical' in r['roles']
                  or r['contract_count']]},
    ]
    # Presentation metadata keeps the page focused on the selected department,
    # rather than putting unrelated KPIs in front of every employee.
    section_specs = {
        'sales': {
            'description': 'فاکتورها، پیش‌فاکتورها و مشتریانی که هر کارشناس فروش با آن‌ها کار کرده است.',
            'primary_fields': ('invoice_count', 'quotation_count'),
            'primary_unit': 'سند فروش',
            'metrics': (
                ('invoice_count', 'فاکتور ثبت‌شده', 'بر اساس تاریخ ایجاد سند'),
                ('quotation_count', 'پیش‌فاکتور ثبت‌شده', 'بر اساس تاریخ ایجاد سند'),
            ),
        },
        'sourcing': {
            'description': 'پاسخ استعلام‌های قیمت و سفارش‌هایی که به فاکتور خرید تبدیل شده‌اند.',
            'primary_fields': ('inquiry_count', 'purchase_count'),
            'primary_unit': 'اقدام',
            'metrics': (
                ('inquiry_count', 'استعلام پاسخ‌داده‌شده', 'هر استعلام برای هر کاربر یک‌بار'),
                ('purchase_count', 'تبدیل به فاکتور خرید', 'تغییر ثبت‌شده در تاریخچه سفارش'),
            ),
        },
        'warehouse': {
            'description': 'فاکتورهای ارسال‌شده برای مشتری و سفارش‌های رسیدشده در انبار.',
            'primary_fields': ('dispatch_count', 'receipt_count'),
            'primary_unit': 'اقدام انبار',
            'metrics': (
                ('dispatch_count', 'ارسال به مشتری', 'ثبت تغییر وضعیت فاکتور'),
                ('receipt_count', 'رسید در انبار', 'ثبت تغییر وضعیت سفارش'),
            ),
        },
        'finance': {
            'description': 'فاکتورهای تأیید مالی‌شده و دستورهای پرداختی که پرداختشان ثبت شده است.',
            'primary_fields': ('finance_approval_count', 'paid_count'),
            'primary_unit': 'اقدام مالی',
            'metrics': (
                ('finance_approval_count', 'تأیید مالی فاکتور', 'تغییر وضعیت تأیید مالی'),
                ('paid_count', 'دستور پرداخت پرداخت‌شده', 'ثبت وضعیت پرداخت‌شده'),
            ),
        },
        'technical': {
            'description': 'قراردادهای ثبت‌شده توسط هر کارشناس و ارزش محاسباتی آن‌ها.',
            'primary_fields': ('contract_count',),
            'primary_unit': 'قرارداد',
            'metrics': (
                ('contract_count', 'قرارداد ثبت‌شده', 'بر اساس تاریخ ایجاد قرارداد'),
                ('contract_amount', 'ارزش محاسباتی قراردادها', 'بدون تبدیل واحد مبلغ'),
            ),
        },
    }
    for section in sections:
        spec = section_specs[section['key']]
        section['description'] = spec['description']
        section['primary_unit'] = spec['primary_unit']
        section['nav_total'] = sum(
            sum(row[field] for field in spec['primary_fields'])
            for row in section['rows']
        )
        section['metrics'] = [
            {
                'label': label,
                'value': sum(row[field] for row in section['rows']),
                'hint': hint,
            }
            for field, label, hint in spec['metrics']
        ]

    return {
        'days': days, 'scope': scope, 'selected_user_id': selected_user_id,
        'user_options': selector_users, 'sections': sections,
        'visible_sections': [section for section in sections if section['rows']],
        'users_count': len(rows),
        'total_documents': sum(r['invoice_count'] + r['quotation_count']
                               for r in rows.values()),
        'total_inquiries': sum(r['inquiry_count'] for r in rows.values()),
        'total_operations': sum(
            r['purchase_count'] + r['dispatch_count'] + r['receipt_count'] +
            r['finance_approval_count'] + r['paid_count'] for r in rows.values()
        ),
        'total_contracts': sum(r['contract_count'] for r in rows.values()),
    }
