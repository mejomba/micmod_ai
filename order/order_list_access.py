"""Shared visibility policy for the order list and its payment tools."""

def can_view_order_payments(user):
    return bool(getattr(user, 'is_superuser', False) or getattr(user, 'base_group', None) == 'trade')


# Ordered definitions from the original role-specific toolbar; superusers see their union.
ORDER_FILTER_LABELS = {
    'all': 'همه',
    'active': 'در جریان',
    'cancel_request': 'درخواست کنسلی',
    'gio_complete': 'gio کامل',
    'gio_incomplete': 'gio ناقص',
    'packing_complete': 'packing کامل',
    'packing_incomplete': 'packing ناقص',
    'payment_complete': 'payment کامل',
    'payment_incomplete': 'payment ناقص',
    'quantity_difference': 'تغییرات تعدادی',
    'need_sale_admin_confirmation': 'نیاز به تایید مدیر فروش',
    'has_error': 'خطا دارد',
    'pcb_item': 'pcb',
    'back': 'عودتی‌ها',
    'is_sample': 'نمونه‌ها',
    'is_force_order': 'سفارش فوری',
    'cancel_denied': 'رد کنسلی',
    'cancel': 'کنسل',
    'has_customer_prepaid': 'پیش‌پرداخت',
    'commitment_date_difference': 'اختلاف تاریخ تعهد',
    'duplicated_codes': 'کد مشابه',
    'my_orders': 'سفارشات من',
}
ROLE_FILTER_KEYS = {
    'trade': ('all', 'active', 'is_force_order', 'cancel_request', 'gio_complete', 'gio_incomplete', 'packing_complete', 'packing_incomplete', 'payment_complete', 'payment_incomplete', 'has_customer_prepaid',),
    'sales': ('all', 'quantity_difference', 'need_sale_admin_confirmation', 'has_error', 'pcb_item', 'back', 'is_sample', 'is_force_order', 'cancel_denied', 'cancel', 'has_customer_prepaid', 'duplicated_codes', 'my_orders',),
}


def visible_order_filters(user):
    keys = ORDER_FILTER_LABELS if getattr(user, 'is_superuser', False) else ROLE_FILTER_KEYS.get(getattr(user, 'base_group', None), ())
    return [(key, ORDER_FILTER_LABELS[key]) for key in keys]
