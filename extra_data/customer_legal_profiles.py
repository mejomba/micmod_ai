"""Validation of legal-profile entries stored on Customer as a JSON list."""

import re

from django.core.exceptions import ValidationError


PROFILE_FIELDS = (
    ('name', 'نام', 255),
    ('national_id', 'شناسه ملی', 11),
    ('type', 'نوع', 100),
    ('postal_code', 'کد پستی', 10),
    ('address', 'آدرس', 1000),
)
PERSIAN_ARABIC_DIGITS = str.maketrans(
    '۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩',
    '01234567890123456789',
)


def normalize_customer_legal_profiles(value):
    """Return a validated, normalized JSON-serializable list of profiles.

    Entirely blank rows are ignored. A partially completed row raises a
    ValidationError, preventing accidental loss of previously saved profiles.
    """
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError('پروفایل‌های حقوقی باید به صورت لیست ارسال شوند.')
    if len(value) > 100:
        raise ValidationError('حداکثر ۱۰۰ پروفایل حقوقی قابل ثبت است.')

    normalized = []
    for row_number, profile in enumerate(value, start=1):
        if not isinstance(profile, dict):
            raise ValidationError(f'پروفایل {row_number}: ساختار ردیف نامعتبر است.')
        if not any(
            profile.get(key) is not None and str(profile.get(key)).strip()
            for key, _, _ in PROFILE_FIELDS
        ):
            continue

        cleaned = {}
        for key, label, max_length in PROFILE_FIELDS:
            raw = profile.get(key, '')
            if not isinstance(raw, str):
                raise ValidationError(
                    f'پروفایل {row_number}: {label} باید متن باشد.'
                )
            text = raw.strip()
            if not text:
                raise ValidationError(f'پروفایل {row_number}: {label} الزامی است.')
            if key in ('national_id', 'postal_code'):
                text = text.translate(PERSIAN_ARABIC_DIGITS)
                required_length = 11 if key == 'national_id' else 10
                if not re.fullmatch(r'[0-9]{%d}' % required_length, text):
                    raise ValidationError(
                        f'پروفایل {row_number}: {label} باید {required_length} رقم باشد.'
                    )
            if len(text) > max_length:
                raise ValidationError(
                    f'پروفایل {row_number}: {label} حداکثر {max_length} کاراکتر است.'
                )
            cleaned[key] = text
        normalized.append(cleaned)
    return normalized
