import re
from django.core.exceptions import ValidationError


def normalize_phone(phone):
    """
    Normalizes a phone string to only digits, prepending '+' if originally present.
    """
    if not phone:
        return ''
    phone = str(phone).strip()
    has_plus = phone.startswith('+')
    digits = re.sub(r'\D+', '', phone)
    if has_plus:
        return f"+{digits}"
    return digits


def extract_local_phone(phone):
    """
    Extracts the local 10-digit phone number by stripping country code.
    If phone starts with '+91' or '91' and has more than 10 digits, strips 91.
    """
    if not phone:
        return ''
    cleaned = str(phone).strip()
    digits = re.sub(r'\D+', '', cleaned)
    if not digits:
        return ''

    if cleaned.startswith('+'):
        if digits.startswith('91'):
            return digits[2:]
        elif len(digits) > 10:
            return digits[-10:]
        return digits
    elif len(digits) == 12 and digits.startswith('91'):
        return digits[2:]
    return digits


def validate_phone(phone):
    """
    Validates that the subscriber/local part of the phone number is exactly 10 digits.
    Raises ValidationError if invalid.
    """
    if not phone:
        raise ValidationError('Phone number is required.')

    cleaned = str(phone).strip()
    digits = re.sub(r'\D+', '', cleaned)

    if not digits:
        raise ValidationError('Phone number must contain numeric digits.')

    # Check for country code and isolate local digits
    if cleaned.startswith('+'):
        if digits.startswith('91'):
            local_digits = digits[2:]
        elif len(digits) > 10:
            local_digits = digits[2:] if digits.startswith('91') else digits[-10:]
        else:
            local_digits = digits
    elif len(digits) == 12 and digits.startswith('91'):
        local_digits = digits[2:]
    else:
        local_digits = digits

    if len(local_digits) != 10:
        raise ValidationError(
            f'Phone number must be exactly 10 digits (got {len(local_digits)} digits).'
        )

    return True
