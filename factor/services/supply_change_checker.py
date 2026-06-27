# services/supply_change_checker.py

class SupplyChangeChecker:
    """رجیستری بررسی‌های مجاز بودن تغییر کد کالای یک ردیف فاکتور.

    استفاده:
        @SupplyChangeChecker.register
        def my_check(factor_item, new_sku, user):
            if not_allowed:
                return False, "پیام خطای فارسی"
            return True, None
    """
    _checks = []

    @classmethod
    def register(cls, func):
        cls._checks.append(func)
        return func

    @classmethod
    def run_all(cls, factor_item, new_sku, user):
        for check in cls._checks:
            allowed, msg = check(factor_item, new_sku, user)
            if not allowed:
                return False, msg
        return True, None

# مثال‌های ثبت چک — این‌ها را در فایل‌های مناسب پروژه‌تان قرار دهید
# و فقط هر زمان لازم بود اضافه کنید:
#
# @SupplyChangeChecker.register
# def check_order_state(factor_item, new_sku, user):
#     if factor_item is None:
#         return True, None  # ردیف جدید — همیشه مجاز
#     bad = factor_item.factoritemsupplylocation_set.filter(
#         order__some_state="locked",
#     )
#     if bad.exists():
#         return False, "این ردیف سفارش در وضعیتی است که تغییر کالا مجاز نیست"
#     return True, None