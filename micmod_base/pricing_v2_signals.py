"""Keep v2 BI materialized values in sync with quotation-wide financial settings.

Only new pricing-version-2 rows are ever processed. Legacy rows, pricing
snapshots, and historical totals are intentionally left untouched.
"""
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Quotation, QuotationItem
from .pricing_v2 import apply_materialized_values


@receiver(pre_save, sender=Quotation, dispatch_uid="quotation_v2_reject_currency_reinterpretation")
def protect_v2_currency(sender, instance, **kwargs):
    if not instance.pk:
        return
    old = sender.objects.filter(pk=instance.pk).values_list("currency_ref_id", flat=True).first()
    if old is None or old == instance.currency_ref_id:
        return
    if QuotationItem.objects.filter(
        quotation_id=instance.pk, pricing_version=2, system_price__isnull=False,
        is_deleted=False,
    ).exists():
        raise ValidationError(
            "در پیش‌فاکتور دارای ردیف قیمت‌گذاری نسخه ۲، تغییر ارز بدون انتخاب مجدد "
            "قیمت مرجع مجاز نیست."
        )


@receiver(post_save, sender=Quotation, dispatch_uid="quotation_v2_sync_materialized_bi")
def sync_financial_pricing_v2(sender, instance, created, update_fields=None, **kwargs):
    if created:
        return
    finance_fields = {"self_discount", "is_official", "official_value"}
    if update_fields is not None and not finance_fields.intersection(update_fields):
        return

    updated = []
    keys = (
        "effective_unit_price", "calculated_row_discount",
        "manager_price_difference", "manager_positive_difference", "final_price",
    )
    rows = QuotationItem.objects.filter(
        quotation_id=instance.pk, pricing_version=2,
        system_price__isnull=False, is_deleted=False,
    ).select_related("quotation")
    for row in rows:
        before = tuple(getattr(row, key) for key in keys)
        apply_materialized_values(row)
        after = tuple(getattr(row, key) for key in keys)
        if before != after:
            updated.append(row)
    if updated:
        QuotationItem.objects.bulk_update(updated, list(keys), batch_size=200)


@receiver(post_save, sender=QuotationItem, dispatch_uid="quotation_item_v2_sync_bi_on_save")
def sync_quotation_item_v2(sender, instance, created, update_fields=None, **kwargs):
    """Legacy item forms can edit quantity; BI values must never become stale."""
    if instance.pricing_version != 2 or instance.system_price is None:
        return
    watched = {"quantity", "discount_per_item", "system_price", "manager_approved_price"}
    if update_fields is not None and not watched.intersection(update_fields):
        return

    columns = (
        "effective_unit_price", "calculated_row_discount",
        "manager_price_difference", "manager_positive_difference", "final_price",
    )
    previous = tuple(getattr(instance, field) for field in columns)
    apply_materialized_values(instance)
    if tuple(getattr(instance, field) for field in columns) != previous:
        # QuerySet.update avoids recursive post_save and touches only new v2 data.
        sender.objects.filter(pk=instance.pk).update(
            **{field: getattr(instance, field) for field in columns}
        )
