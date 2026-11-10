"""Packing volume calculation and input validation.

Dimensions are entered in centimetres as Length x Width x Height. Their
product divided by 1,000,000 is the volume in cubic metres (CBM).
"""
import re
from decimal import Decimal, InvalidOperation


MAX_VOLUME = Decimal('1000000000000')
MAX_DIMENSION = Decimal('1000000')
VOLUME_STEP = Decimal('0.000001')
SIZE_FORMAT_ERROR = (
    'سایز باید شامل سه عدد مثبت با جداکننده *، x یا × باشد '
    '(مثلاً 40*30*20).'
)
_SIZE_SEPARATOR = re.compile(r'[xX×*]')


def parse_packing_size(value):
    """Return three positive Decimal dimensions, or None for an empty size."""
    if value is None or str(value).strip() == '':
        return None

    parts = _SIZE_SEPARATOR.split(str(value).strip())
    if len(parts) != 3:
        raise ValueError(SIZE_FORMAT_ERROR)

    dimensions = []
    for part in parts:
        try:
            dimension = Decimal(part.strip())
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError(SIZE_FORMAT_ERROR)
        if (
            not dimension.is_finite()
            or dimension <= 0
            or dimension > MAX_DIMENSION
        ):
            raise ValueError(SIZE_FORMAT_ERROR)
        dimensions.append(dimension)
    return tuple(dimensions)


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


def calculate_packing_volume(
    *, size=None, quantity=None, carton_quantity=None, order_id=None,
):
    """Calculate CBM from L x W x H; unrelated row fields are ignored."""
    dimensions = parse_packing_size(size)
    if dimensions is None:
        return None

    volume = dimensions[0] * dimensions[1] * dimensions[2] / Decimal('1000000')
    if not volume.is_finite() or volume < 0 or volume >= MAX_VOLUME:
        raise ValueError('حجم محاسبه‌شده خارج از محدوده مجاز است.')
    quantized = volume.quantize(VOLUME_STEP)
    if quantized >= MAX_VOLUME:
        raise ValueError('حجم محاسبه‌شده خارج از محدوده مجاز است.')
    return quantized


def resolve_packing_volume(
    entered, *, size=None, is_confirmed=False,
    quantity=None, carton_quantity=None, order_id=None,
):
    """Preserve a confirmed manual override; otherwise use the size formula."""
    calculated = calculate_packing_volume(
        size=size, quantity=quantity,
        carton_quantity=carton_quantity, order_id=order_id,
    )
    if is_confirmed and entered is not None:
        return parse_packing_volume(entered)
    return calculated
