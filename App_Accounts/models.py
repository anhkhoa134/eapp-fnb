from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q


class User(AbstractUser):
    class Role(models.TextChoices):
        MANAGER = 'MANAGER', 'Manager'
        STAFF = 'STAFF', 'Staff'

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STAFF)
    tenant = models.ForeignKey(
        'App_Tenant.Tenant',
        on_delete=models.PROTECT,
        related_name='users',
        null=True,
        blank=True,
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
