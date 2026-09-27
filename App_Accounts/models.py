from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q


class User(AbstractUser):
    class Role(models.TextChoices):
        MANAGER = 'MANAGER', 'Manager'
        STAFF = 'STAFF', 'Staff'

    is_active = models.BooleanField('Đang hoạt động', default=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STAFF)
    tenant = models.ForeignKey(
        'App_Tenant.Tenant',
        on_delete=models.PROTECT,
        related_name='users',
        null=True,
        blank=True,
        verbose_name='doanh nghiệp',
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=Q(role='STAFF') | Q(tenant__isnull=False),
                name='chk_manager_requires_tenant',
            ),
            models.UniqueConstraint(
                fields=['tenant'],
                condition=Q(role='MANAGER') & Q(tenant__isnull=False),
                name='uq_manager_per_tenant',
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'role']),
        ]

    @property
    def is_manager(self):
        return self.role == self.Role.MANAGER

    @property
    def is_staff_user(self):
        return self.role == self.Role.STAFF


class LoginAttempt(models.Model):
    """Đếm số lần đăng nhập sai theo username + IP để khoá tạm (chống brute-force)."""

    username = models.CharField('Tên đăng nhập', max_length=150)
    ip_address = models.CharField('Địa chỉ IP', max_length=45, blank=True)
    failure_count = models.PositiveIntegerField('Số lần sai', default=0)
    last_failure_at = models.DateTimeField('Lần sai gần nhất', null=True, blank=True)
    locked_until = models.DateTimeField('Khoá đến', null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['username', 'ip_address'], name='uq_login_attempt_username_ip'),
        ]
        ordering = ['-last_failure_at']
        verbose_name = 'Đăng nhập sai'
        verbose_name_plural = 'Đăng nhập sai'

    def __str__(self):
        return f'{self.username} @ {self.ip_address or "?"}'
