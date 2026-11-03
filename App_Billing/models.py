import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q


class SubscriptionRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Chờ xử lý'
        APPROVED = 'approved', 'Đã kích hoạt'
        REJECTED = 'rejected', 'Từ chối'
        CANCELLED = 'cancelled', 'Đã hủy'

    class Cycle(models.TextChoices):
        MONTH = 'month', 'Theo tháng (1 tháng)'
        YEAR = 'year', 'Theo năm (12 tháng)'
        NONE = 'none', 'Không thời hạn'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(settings.BILLING_ACCOUNT_MODEL, on_delete=models.PROTECT, related_name='billing_requests', verbose_name='Tài khoản / Doanh nghiệp')
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='submitted_billing_requests', verbose_name='Người yêu cầu')
    client_token = models.UUIDField(default=uuid.uuid4, editable=False)
    reference = models.CharField('Mã yêu cầu', max_length=40, unique=True)
    plan_key = models.CharField('Mã gói', max_length=64)
    plan_name = models.CharField('Gói yêu cầu', max_length=120)
    billing_cycle = models.CharField('Kỳ hạn', max_length=8, choices=Cycle.choices)
    kind = models.CharField('Loại yêu cầu', max_length=12, choices=[('change', 'Đổi gói'), ('renewal', 'Gia hạn'), ('cycle_change', 'Đổi kỳ hạn')])
    amount_vnd = models.PositiveBigIntegerField('Giá tại lúc yêu cầu (VND)', null=True, blank=True)
    approved_amount_vnd = models.PositiveBigIntegerField('Giá đã xác nhận (VND)', null=True, blank=True)
    currency = models.CharField(max_length=3, default='VND', editable=False)
    customer_note = models.TextField('Ghi chú khách hàng', max_length=2000, blank=True)
    status = models.CharField('Trạng thái', max_length=12, choices=Status.choices, default=Status.PENDING)
    review_note = models.TextField('Phản hồi', max_length=2000, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_billing_requests', verbose_name='Người xử lý')
    created_at = models.DateTimeField('Ngày yêu cầu', auto_now_add=True)
    reviewed_at = models.DateTimeField('Ngày xử lý', null=True, blank=True)
    activation_snapshot = models.JSONField(default=dict, blank=True, editable=False)
    activated_at = models.DateTimeField('Ngày kích hoạt', null=True, blank=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'Yêu cầu gói dịch vụ'
        verbose_name_plural = 'Yêu cầu gói dịch vụ'
        constraints = [
            models.UniqueConstraint(fields=['account'], condition=Q(status='pending'), name='billing_one_pending_account'),
            models.UniqueConstraint(fields=['account', 'client_token'], name='billing_account_client_token'),
            models.CheckConstraint(condition=Q(billing_cycle__in=['month', 'year', 'none']), name='billing_valid_cycle'),
        ]

    @property
    def months(self):
        return {'year': 12, 'month': 1, 'none': 0}[self.billing_cycle]

    def __str__(self):
        return f'{self.reference} · {self.plan_name}'


class PaymentAttempt(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Chờ xác nhận'
        SUCCEEDED = 'succeeded', 'Đã xác nhận'
        CANCELLED = 'cancelled', 'Đã hủy'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(SubscriptionRequest, on_delete=models.PROTECT, related_name='payments', verbose_name='Yêu cầu')
    provider = models.CharField('Kênh thanh toán', max_length=24, default='manual')
    provider_reference = models.CharField('Mã giao dịch bên cung cấp', max_length=128, blank=True, default='')
    expected_amount_vnd = models.PositiveBigIntegerField('Số tiền cần trả (VND)', null=True, blank=True)
    received_amount_vnd = models.PositiveBigIntegerField('Số tiền đã xác nhận (VND)', null=True, blank=True)
    currency = models.CharField(max_length=3, default='VND')
    status = models.CharField('Trạng thái', max_length=12, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Lần thanh toán'
        verbose_name_plural = 'Lần thanh toán'
        constraints = [models.UniqueConstraint(fields=['provider', 'provider_reference'], condition=~Q(provider_reference=''), name='billing_unique_provider_receipt')]

    def __str__(self):
        return f'{self.request.reference} · {self.provider}'
