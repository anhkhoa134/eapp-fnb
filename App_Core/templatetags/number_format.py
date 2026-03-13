from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django import template

register = template.Library()


@register.filter
def thousand_sep(value):
    """Format number with dot thousands separator and 0 decimals."""
    if value in (None, ''):
        return '0'

    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return value

    rounded = amount.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    number = int(rounded)
    sign = '-' if number < 0 else ''
    return f"{sign}{abs(number):,}".replace(',', '.')
