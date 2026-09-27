from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AuditLog(models.Model):
    """Nhật ký thao tác của người dùng trong một doanh nghiệp (chỉ ghi thêm, không sửa)."""

    class Action(models.TextChoices):
        LOGIN = 'auth.login', 'Đăng nhập'
        LOGOUT = 'auth.logout', 'Đăng xuất'
        LOGIN_FAILED = 'auth.login_failed', 'Đăng nhập thất bại'
        ORDER_REFUND = 'order.refund', 'Hoàn tiền'
        ORDER_DELETE = 'order.delete', 'Xoá đơn'
        ORDER_REPRINT = 'order.reprint', 'In lại hoá đơn'
        SHIFT_OPEN = 'shift.open', 'Mở ca'
        SHIFT_CLOSE = 'shift.close', 'Chốt ca'
        CART_VOID = 'cart.void', 'Huỷ món'
        TABLE_MOVE = 'table.move', 'Chuyển bàn'
        QR_REJECT = 'qr.reject', 'Từ chối đơn QR'
        KITCHEN_REPRINT = 'kitchen.reprint', 'In lại phiếu bếp'
        CATALOG_IMPORT = 'catalog.import', 'Nhập Excel'
        OBJECT_CREATE = 'object.create', 'Tạo mới'
        OBJECT_UPDATE = 'object.update', 'Cập nhật'
        OBJECT_DELETE = 'object.delete', 'Xoá'

    tenant = models.ForeignKey('App_Tenant.Tenant', on_delete=models.CASCADE, related_name='audit_logs')
    store = models.ForeignKey(
        'App_Tenant.Store',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    username = models.CharField('Người thao tác', max_length=150, blank=True)
    action = models.CharField('Thao tác', max_length=40, choices=Action.choices)
    object_type = models.CharField('Loại đối tượng', max_length=60, blank=True)
    object_id = models.CharField(max_length=64, blank=True)
    object_repr = models.CharField('Đối tượng', max_length=200, blank=True)
    message = models.CharField('Nội dung', max_length=500, blank=True)
    extra = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['tenant', 'action', 'created_at']),
            models.Index(fields=['tenant', 'user', 'created_at']),
        ]
        ordering = ['-created_at', '-id']
        verbose_name = 'Nhật ký thao tác'
        verbose_name_plural = 'Nhật ký thao tác'

    def __str__(self):
        return f'{self.created_at:%d/%m/%Y %H:%M} {self.username} {self.get_action_display()}'
