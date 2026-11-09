"""Temporary stable pseudo-random proposal for editable Packing row volume.

IMPORTANT: THIS IS TEST DATA, NOT A VOLUME CALCULATION.
Replace calculate_packing_volume when the business formula is supplied.
The same inputs always return the same proposed volume, so the inline
manual-override warning doesn't change unpredictably on each request.
"""
from decimal import Decimal, InvalidOperation
from hashlib import sha256


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


def _normalize_numeric_seed(value):
    if value is None or str(value).strip() == '':
        return ''
    try:
        return format(Decimal(str(value)).normalize(), 'f')
    except (InvalidOperation, TypeError, ValueError):
        return str(value).strip()


def calculate_packing_volume(
    *, quantity=None, size=None, carton_quantity=None, order_id=None,
):
    """TEST ONLY: deterministic random-looking Decimal, not a real formula.

    The order identifier differentiates rows with otherwise identical inputs.
    Using a stable hash (rather than random.random) keeps the proposed value
    reproducible across refresh, edit, preview and save. Range: 0.1 to 1.0.
    """
    seed = '|'.join((
        'temporary-packing-volume-v1',
        str(order_id or ''),
        _normalize_numeric_seed(quantity),
        str(size or '').strip(),
        _normalize_numeric_seed(carton_quantity),
    ))
    digest = sha256(seed.encode('utf-8')).digest()
    scaled = 100000 + int.from_bytes(digest[:8], 'big') % 900001
    return Decimal(scaled).scaleb(-6)


def resolve_packing_volume(
    entered, *, quantity=None, size=None, carton_quantity=None, order_id=None,
):
    """Preserve a manual override, otherwise use the temporary proposal."""
    if entered is not None:
        return entered
    return calculate_packing_volume(
        quantity=quantity, size=size, carton_quantity=carton_quantity,
        order_id=order_id,
    )


def is_confirmed_packing_volume(value, checked, *, generated=None):
    """Only a positive, explicitly confirmed *manual* value is reportable.

    This is independent of the temporary value returned by
    resolve_packing_volume(). Unconfirmed legacy rows remain untrusted until
    the user checks the confirmation control and saves the Packing again.
    """
    if not checked:
        return False
    try:
        parsed = parse_packing_volume(value)
    except ValueError:
        return False
    if parsed is None or parsed <= 0:
        return False
    # A generated test suggestion must never be marked as real volume even
    # when an unmodified preview checkbox is submitted.
    if generated is not None and parsed == generated:
        return False
    return True
