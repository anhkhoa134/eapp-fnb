"""Giá bán điều chỉnh và chứng thực người chỉnh cho giỏ mang về ở trình duyệt."""
from decimal import Decimal, InvalidOperation

from django.core import signing
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from App_Accounts.models import User
from App_Core.audit import Action, log_action
from App_Core.templatetags.number_format import thousand_sep
from App_Sales.services import MAX_MONEY_AMOUNT

SALT = 'fnb.cart-price-override.v1'
SNAPSHOT_FIELDS = (
    'original_unit_price', 'price_override_reason', 'price_overridden_by_id',
    'price_overridden_by_name', 'price_overridden_at',
)


class PriceOverrideError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def require_enabled(tenant):
    if not tenant.feature_price_override_enabled:
        raise PriceOverrideError('Tính năng chỉnh giá đang tắt. Vui lòng khôi phục giá gốc trước khi thanh toán.', 403)


def parse_price(raw):
    try:
        value = Decimal(str(raw))
        if not value.is_finite() or value < 0 or value > MAX_MONEY_AMOUNT or value != value.quantize(Decimal('.01')):
            raise ValueError
    except (ValueError, InvalidOperation, TypeError):
        raise PriceOverrideError('Giá bán phải từ 0 đến 999.999.999.999 đ, tối đa 2 chữ số thập phân.')
    return value


def new_snapshot(*, tenant, user, original_price, reason):
    require_enabled(tenant)
    if not isinstance(reason, str) or len(reason) > 255:
        raise PriceOverrideError('Lý do chỉnh giá tối đa 255 ký tự.')
    reason = reason.strip()
    if tenant.price_override_reason_required and not reason:
        raise PriceOverrideError('Vui lòng nhập lý do chỉnh giá.')
    return {
        'original_unit_price': original_price,
        'price_override_reason': reason,
        'price_overridden_by_id': user.pk,
        'price_overridden_by_name': user.username,
        'price_overridden_at': timezone.now(),
    }


def snapshot(item):
    return {field: getattr(item, field) for field in SNAPSHOT_FIELDS}


def clear_snapshot():
    return dict(original_unit_price=None, price_override_reason='', price_overridden_by_id=None,
                price_overridden_by_name='', price_overridden_at=None)


def sign_override(*, tenant_id, store_id, unit_id, topping_ids, price, metadata):
    if metadata['original_unit_price'] is None:
        return None
    return signing.dumps({
        'tenant': tenant_id, 'store': store_id, 'unit': unit_id, 'toppings': sorted(topping_ids),
        'price': str(price), **{
            key: str(value) if isinstance(value, Decimal) else value.isoformat() if key == 'price_overridden_at' and value else value
            for key, value in metadata.items()
        },
    }, salt=SALT, compress=True)


def resolve_override(payload, *, tenant, store_id, unit_id, topping_ids, check_enabled=True):
    token = payload.get('price_override_token')
    if not token:
        if payload.get('override_price') is not None:
            raise PriceOverrideError('Vui lòng lưu lại giá điều chỉnh trước khi tiếp tục.')
        return None, clear_snapshot()
    if check_enabled:
        require_enabled(tenant)
    try:
        data = signing.loads(token, salt=SALT, max_age=7 * 24 * 60 * 60)
        if (data['tenant'], data['store'], data['unit'], data['toppings']) != (
            tenant.pk, store_id, unit_id, sorted(topping_ids),
        ):
            raise ValueError
        metadata = {field: data[field] for field in SNAPSHOT_FIELDS}
        metadata['original_unit_price'] = parse_price(metadata['original_unit_price'])
        metadata['price_overridden_at'] = parse_datetime(metadata['price_overridden_at'])
        if not metadata['price_overridden_at']:
            raise ValueError
        # Tài khoản bị xoá vẫn giữ tên người chỉnh trong snapshot và nhật ký.
        if not User.objects.filter(pk=metadata['price_overridden_by_id'], tenant=tenant).exists():
            metadata['price_overridden_by_id'] = None
        return parse_price(data['price']), metadata
    except (signing.BadSignature, ValueError, TypeError, KeyError):
        raise PriceOverrideError('Giá điều chỉnh không hợp lệ hoặc đã hết hạn. Vui lòng chỉnh giá lại.')


def log_price_change(request, *, store_id, obj, before, after, metadata, restored=False, extra=None):
    name = getattr(obj, 'snapshot_product_name', str(obj))
    context = f' · {(extra or {}).get("table_name")}' if (extra or {}).get('table_name') else ''
    entry = log_action(
        Action.CART_PRICE_OVERRIDE, request=request, store_id=store_id, obj=obj,
        message=f'{"Khôi phục" if restored else "Chỉnh"} giá {name}{context}: {thousand_sep(before)} → {thousand_sep(after)} đ. '
                f'Lý do: {metadata.get("price_override_reason") or "Không nhập"}',
        extra={'before': str(before), 'after': str(after), 'restored': restored,
               'reason': metadata.get('price_override_reason', ''), **(extra or {})},
    )
    if entry is None:
        # Giá và nhật ký phải cùng thành công trong transaction của endpoint.
        raise RuntimeError('Không thể ghi nhật ký chỉnh giá.')
    return entry
