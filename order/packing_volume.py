"""Central calculation hook for the editable Packing row volume.

The business formula has not been provided. Return None, not zero.
When the formula is supplied, implement it once here for both the AJAX
preview and the persisted default. A manually entered value takes priority.
"""
from decimal import Decimal, InvalidOperation


MAX_VOLUME = Decimal('1000000000000')
VOLUME_STEP = Decimal('0.000001')


def parse_packing_volume(value):
    """Parse optional Decimal(18,6) without silently rounding user input."""
    if value is None or str(value).strip() == '':
        return None
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('حجم باید یک عدد اعشاری معتبر باشد.')
    if not parsed.is_finite() or parsed < 0 or parsed >= MAX_VOLUME:
        raise ValueError('حجم باید عددی غیرمنفی و در محدوده مجاز باشد.')
    quantized = parsed.quantize(VOLUME_STEP)
    if quantized != parsed:
        raise ValueError('حجم نمی‌تواند بیشتر از ۶ رقم اعشار داشته باشد.')
    return quantized


def calculate_packing_volume(*, quantity=None, size=None, carton_quantity=None):
    """Future calculation rule. None signals that no formula exists yet."""
    return None


def resolve_packing_volume(entered, *, quantity=None, size=None, carton_quantity=None):
    """Preserve a manual override, otherwise use the computed proposal."""
    if entered is not None:
        return entered
    return calculate_packing_volume(
        quantity=quantity, size=size, carton_quantity=carton_quantity,
    )
