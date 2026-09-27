"""Nhật ký thao tác: ghi lại ai làm gì, lúc nào, trong doanh nghiệp nào.

- `log_action(...)`: gọi tường minh cho nghiệp vụ nhạy cảm (hoàn tiền, chốt ca, huỷ món...).
- Dữ liệu danh mục (món, giá, khuyến mãi, nhân viên, cấu hình...) được ghi tự động qua
  signal khi thay đổi đến từ một request của người dùng đã đăng nhập (seed/lệnh quản trị bỏ qua).
"""

import ipaddress
import logging
from contextvars import ContextVar
from decimal import Decimal

from django.apps import apps
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_delete, post_save, pre_save

from App_Core.models import AuditLog
from App_Core.templatetags.number_format import thousand_sep

logger = logging.getLogger(__name__)

_current_request = ContextVar('audit_current_request', default=None)

Action = AuditLog.Action


class AuditContextMiddleware:
    """Giữ request hiện tại để signal biết người thao tác. Đặt sau AuthenticationMiddleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _current_request.set(request)
        try:
            return self.get_response(request)
        finally:
            _current_request.reset(token)


def get_current_request():
    return _current_request.get()


def _client_ip(request):
    if request is None:
        return None
    from App_Accounts.login_throttle import get_client_ip

    raw = get_client_ip(request)
    try:
        ipaddress.ip_address(raw)
    except ValueError:
        return None
    return raw


def _request_user(request):
    user = getattr(request, 'user', None) if request is not None else None
    if user is None or not getattr(user, 'is_authenticated', False):
        return None
    return user


def log_action(
    action,
    *,
    request=None,
    user=None,
    tenant=None,
    tenant_id=None,
    store=None,
    store_id=None,
    obj=None,
    object_type='',
    message='',
    extra=None,
):
    """Ghi 1 dòng nhật ký. Không bao giờ làm hỏng nghiệp vụ chính nếu ghi lỗi."""
    request = request if request is not None else get_current_request()
    user = user or _request_user(request)
    if tenant_id is None:
        tenant_id = tenant.pk if tenant is not None else getattr(user, 'tenant_id', None)
    if not tenant_id:
        return None
    if store_id is None and store is not None:
        store_id = store.pk
    if obj is not None:
        object_type = object_type or obj._meta.verbose_name
    try:
        return AuditLog.objects.create(
            tenant_id=tenant_id,
            store_id=store_id,
            user=user,
            username=(getattr(user, 'username', '') or '')[:150],
            action=action,
            object_type=str(object_type or '')[:60],
            object_id=str(obj.pk if obj is not None and obj.pk is not None else '')[:64],
            object_repr=str(obj)[:200] if obj is not None else '',
            message=(message or '')[:500],
            extra=extra or {},
            ip_address=_client_ip(request),
        )
    except Exception:  # pragma: no cover - nhật ký không được chặn nghiệp vụ
        logger.exception('Không ghi được nhật ký thao tác %s', action)
        return None


# --- Ghi tự động thay đổi dữ liệu danh mục -------------------------------------------------

# model label -> cấu hình: label (tên hiển thị), exclude (bỏ qua), mask (chỉ ghi "đã thay đổi").
TRACKED_MODELS = {
    'App_Catalog.Category': {'label': 'Danh mục', 'exclude': {'slug'}},
    'App_Catalog.Product': {'label': 'Sản phẩm', 'exclude': {'slug', 'image_thumbnail'}},
    'App_Catalog.ProductUnit': {'label': 'Đơn vị bán', 'exclude': {'display_order'}},
    'App_Catalog.Topping': {'label': 'Topping', 'exclude': {'slug', 'display_order'}},
    'App_Catalog.ProductTopping': {'label': 'Topping của món', 'exclude': {'display_order'}},
    'App_Catalog.StoreProduct': {'label': 'Món theo cửa hàng'},
    'App_Catalog.Ingredient': {'label': 'Nguyên liệu', 'exclude': {'display_order'}},
    'App_Sales.Promotion': {'label': 'Khuyến mãi'},
    'App_Sales.Customer': {
        'label': 'Khách hàng',
        'exclude': {'points_balance', 'total_spent', 'tier', 'last_order_at'},
    },
    'App_Sales.CustomerTierSetting': {'label': 'Hạng khách hàng'},
    'App_Sales.DiningTable': {'label': 'Bàn', 'exclude': {'display_order'}, 'mask': {'qr_token'}},
    'App_Tenant.Store': {'label': 'Cửa hàng', 'exclude': {'slug'}},
    'App_Tenant.Tenant': {'label': 'Doanh nghiệp'},
    'App_Accounts.User': {'label': 'Tài khoản', 'exclude': {'last_login', 'date_joined'}, 'mask': {'password'}},
}
ALWAYS_EXCLUDED = {'id', 'created_at', 'updated_at'}

# Nhãn cho các field không khai báo verbose_name tiếng Việt.
FIELD_LABELS = {
    'name': 'Tên',
    'price': 'Giá',
    'sku': 'SKU',
    'code': 'Mã',
    'category': 'Danh mục',
    'description': 'Mô tả',
    'image_url': 'Ảnh (URL)',
    'image_file': 'Ảnh',
    'product': 'Món',
    'topping': 'Topping',
    'store': 'Cửa hàng',
    'tenant': 'Doanh nghiệp',
    'custom_price': 'Giá riêng',
    'is_available': 'Đang bán',
    'is_visible': 'Hiển thị',
    'is_default': 'Mặc định',
    'username': 'Tài khoản',
    'first_name': 'Tên',
    'last_name': 'Họ',
    'email': 'Email',
    'role': 'Vai trò',
    'password': 'Mật khẩu',
    'is_staff': 'Quyền admin',
    'is_superuser': 'Siêu quản trị',
    'phone': 'Số điện thoại',
    'note': 'Ghi chú',
    'address': 'Địa chỉ',
    'discount_type': 'Loại giảm',
    'discount_value': 'Giá trị giảm',
    'min_order_amount': 'Đơn tối thiểu',
    'max_discount_amount': 'Giảm tối đa',
    'valid_from': 'Bắt đầu',
    'valid_to': 'Kết thúc',
    'tier': 'Hạng',
    'min_total_spent': 'Ngưỡng chi tiêu',
    'discount_percent': '% ưu đãi',
    'qr_token': 'Mã QR',
    'payment_qr': 'Ảnh QR thanh toán',
    'payment_bank_name': 'Ngân hàng',
    'payment_account_name': 'Chủ tài khoản',
    'payment_account_number': 'Số tài khoản',
    'public_slug': 'Đường dẫn public',
}


def _model_label(model):
    return TRACKED_MODELS.get(model._meta.label, {}).get('label') or str(model._meta.verbose_name)


def _field_label(field):
    label = str(field.verbose_name)
    if label == field.name.replace('_', ' '):
        return FIELD_LABELS.get(field.name, label)
    return label


def _model_config(sender):
    return TRACKED_MODELS.get(sender._meta.label)


def _tracked_fields(sender, config):
    excluded = ALWAYS_EXCLUDED | set(config.get('exclude', ()))
    return [f for f in sender._meta.concrete_fields if f.name not in excluded]


def _display_value(instance, field):
    value = getattr(instance, field.attname)
    if value is None or value == '':
        return '—'
    if field.is_relation:
        related = getattr(instance, field.name, None)
        return str(related) if related is not None else str(value)
    if field.choices:
        return str(dict(field.flatchoices).get(value, value))
    if isinstance(value, bool):
        return 'Có' if value else 'Không'
    if isinstance(value, Decimal):
        return thousand_sep(value) if value == value.to_integral() else str(value)
    return str(value)[:120]


def _snapshot(instance, fields):
    return {f.name: getattr(instance, f.attname) for f in fields}


def _instance_tenant_id(instance):
    if instance._meta.label == 'App_Tenant.Tenant':
        return instance.pk
    tenant_id = getattr(instance, 'tenant_id', None)
    if tenant_id:
        return tenant_id
    for parent in ('product', 'store'):
        if getattr(instance, f'{parent}_id', None):
            related = getattr(instance, parent, None)
            if related is not None:
                return related.tenant_id
    return None


def _should_log(instance):
    return _request_user(get_current_request()) is not None


def _on_pre_save(sender, instance, raw=False, **kwargs):
    config = _model_config(sender)
    if config is None or raw or not instance.pk or not _should_log(instance):
        return
    fields = _tracked_fields(sender, config)
    old = sender._base_manager.filter(pk=instance.pk).first()
    if old is not None:
        instance._audit_old = old
        instance._audit_old_values = _snapshot(old, fields)


def _on_post_save(sender, instance, created=False, raw=False, update_fields=None, **kwargs):
    config = _model_config(sender)
    if config is None or raw or not _should_log(instance):
        return
    tenant_id = _instance_tenant_id(instance)
    if not tenant_id:
        return
    verbose = _model_label(sender)
    if created:
        log_action(
            Action.OBJECT_CREATE,
            tenant_id=tenant_id,
            store_id=getattr(instance, 'store_id', None),
            obj=instance,
            object_type=verbose,
            message=f'Tạo {verbose.lower()} "{instance}"',
        )
        return

    old = getattr(instance, '_audit_old', None)
    old_values = getattr(instance, '_audit_old_values', None)
    if old is None or old_values is None:
        return
    masked = set(config.get('mask', ()))
    changes = []
    for field in _tracked_fields(sender, config):
        if old_values.get(field.name) == getattr(instance, field.attname):
            continue
        label = _field_label(field)
        if field.name in masked:
            changes.append({'field': label, 'old': '', 'new': 'đã thay đổi'})
        else:
            changes.append({'field': label, 'old': _display_value(old, field), 'new': _display_value(instance, field)})
    del instance._audit_old, instance._audit_old_values
    if not changes:
        return
    summary = '; '.join(
        f"{row['field']}: {row['new']}" if not row['old'] else f"{row['field']}: {row['old']} → {row['new']}"
        for row in changes[:4]
    )
    log_action(
        Action.OBJECT_UPDATE,
        tenant_id=tenant_id,
        store_id=getattr(instance, 'store_id', None),
        obj=instance,
        object_type=verbose,
        message=f'Sửa {verbose.lower()} "{instance}": {summary}',
        extra={'changes': changes},
    )


def _on_post_delete(sender, instance, **kwargs):
    config = _model_config(sender)
    if config is None or not _should_log(instance):
        return
    try:
        tenant_id = _instance_tenant_id(instance)
    except Exception:
        # Đối tượng cha đã bị xoá theo dây chuyền.
        tenant_id = getattr(getattr(_request_user(get_current_request()), 'tenant', None), 'pk', None)
    if not tenant_id:
        return
    try:
        label = str(instance)
    except Exception:
        label = f'#{instance.pk}'
    verbose = _model_label(sender)
    log_action(
        Action.OBJECT_DELETE,
        tenant_id=tenant_id,
        object_type=verbose,
        message=f'Xoá {verbose.lower()} "{label}"',
        extra={'object_id': instance.pk, 'object_repr': label[:200]},
    )


# --- Đăng nhập / đăng xuất ---------------------------------------------------------------


def _on_logged_in(sender, request, user, **kwargs):
    log_action(Action.LOGIN, request=request, user=user, message='Đăng nhập')


def _on_logged_out(sender, request, user, **kwargs):
    if user is None:
        return
    log_action(Action.LOGOUT, request=request, user=user, message='Đăng xuất')


def _on_login_failed(sender, credentials, request=None, **kwargs):
    username = (credentials or {}).get('username') or ''
    if not username:
        return
    User = apps.get_model('App_Accounts', 'User')
    target = User.objects.filter(username__iexact=username).only('id', 'tenant_id').first()
    if target is None or not target.tenant_id:
        return
    log_action(
        Action.LOGIN_FAILED,
        request=request,
        user=None,
        tenant_id=target.tenant_id,
        message=f'Đăng nhập sai mật khẩu cho "{username[:60]}"',
        extra={'username': username[:150]},
    )


def connect_signals():
    for label in TRACKED_MODELS:
        model = apps.get_model(label)
        uid = f'audit:{label}'
        pre_save.connect(_on_pre_save, sender=model, dispatch_uid=f'{uid}:pre')
        post_save.connect(_on_post_save, sender=model, dispatch_uid=f'{uid}:post')
        post_delete.connect(_on_post_delete, sender=model, dispatch_uid=f'{uid}:delete')
    user_logged_in.connect(_on_logged_in, dispatch_uid='audit:login')
    user_logged_out.connect(_on_logged_out, dispatch_uid='audit:logout')
    user_login_failed.connect(_on_login_failed, dispatch_uid='audit:login_failed')
