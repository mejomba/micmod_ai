"""GIO weight arithmetic, in kg (same unit as PackingItem.net_weight_kg)."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


MAX_WEIGHT = Decimal('999999999999.999999')


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number.is_finite() and number >= 0 else None


def parse_manual_weight(value):
    """Match DecimalField(18, 6); zero is a valid explicit override."""
    number = _number(value)
    if number is None or number > MAX_WEIGHT:
        raise ValueError('invalid_weight')
    try:
        if number != number.quantize(Decimal('0.000001')):
            raise ValueError('invalid_weight')
    except InvalidOperation as exc:
        raise ValueError('invalid_weight') from exc
    return number.quantize(Decimal('0.000001'))


@dataclass(frozen=True)
class WeightSummary:
    known_weight_kg: Decimal
    missing_row_ids: tuple
    row_count: int
    manual_weight_kg: Decimal = None

    @property
    def calculated_weight_kg(self):
        return self.known_weight_kg if self.row_count and not self.missing_row_ids else None

    @property
    def effective_weight_kg(self):
        return self.manual_weight_kg if self.manual_weight_kg is not None else self.calculated_weight_kg

    @property
    def is_overridden(self):
        return self.manual_weight_kg is not None


def summarize_weights(rows, manual=None):
    """Rows are (identifier, quantity, unit kg). Unknown is never silently zero."""
    total, missing, count = Decimal(0), [], 0
    for identifier, quantity, unit_weight in rows:
        count += 1
        quantity, unit_weight = _number(quantity), _number(unit_weight)
        if quantity is None or unit_weight is None or quantity <= 0:
            missing.append(identifier)
            continue
        total += quantity * unit_weight
    return WeightSummary(total, tuple(missing), count, manual)
