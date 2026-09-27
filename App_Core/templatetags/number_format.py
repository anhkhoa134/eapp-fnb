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


@register.filter
def decimal_sep(value, places=3):
    """Số có phần lẻ kiểu VN: dấu chấm phần nghìn, dấu phẩy thập phân, bỏ số 0 thừa (1250.500 -> 1.250,5)."""
    if value in (None, ''):
        return '0'

    try:
        amount = Decimal(str(value)).quantize(Decimal(1).scaleb(-int(places)), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return value

    sign = '-' if amount < 0 else ''
    integer_part, _, fraction = f'{abs(amount):f}'.partition('.')
    fraction = fraction.rstrip('0')
    text = f'{int(integer_part):,}'.replace(',', '.')
    return f'{sign}{text},{fraction}' if fraction else f'{sign}{text}'
