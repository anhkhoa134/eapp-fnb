"""Request lifecycle and trusted payment boundary; no public payment webhook is enabled."""
import calendar
import uuid
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from . import adapter
from .models import PaymentAttempt, SubscriptionRequest


def add_months(value, months):
    year, month = divmod(value.year * 12 + value.month - 1 + months, 12)
    return value.replace(year=year, month=month + 1, day=min(value.day, calendar.monthrange(year, month + 1)[1]))


def money(amount):
    return 'Liên hệ báo giá' if amount is None else f'{int(amount):,}đ'.replace(',', '.')


def account_for(request):
    if not request.user.is_authenticated or not request.user.is_active:
        raise PermissionDenied('Vui lòng đăng nhập để gửi yêu cầu.')
    return adapter.account_for(request)


def lock_account(account_id):
    model = SubscriptionRequest._meta.get_field('account').remote_field.model
    return model.objects.select_for_update().get(pk=account_id)


@transaction.atomic
def submit_request(request, *, plan_key, billing_cycle, customer_note, client_token):
    account = lock_account(account_for(request).pk)
    plan = next((p for p in adapter.plans() if p['key'] == plan_key), None)
    if plan is None or billing_cycle not in SubscriptionRequest.Cycle.values:
        raise ValidationError('Gói hoặc kỳ hạn không hợp lệ.')
    existing = SubscriptionRequest.objects.filter(account=account, client_token=client_token).first()
    if existing:
        if existing.plan_key != plan_key or existing.billing_cycle != billing_cycle:
            raise ValidationError('Mã gửi yêu cầu đã được sử dụng. Vui lòng tải lại trang.')
        return existing
    pending = SubscriptionRequest.objects.filter(account=account, status='pending').first()
    if pending:
        if pending.plan_key == plan_key and pending.billing_cycle == billing_cycle:
            return pending
        raise ValidationError('Bạn đã có yêu cầu chờ xử lý. Hãy hủy yêu cầu cũ trước khi chọn gói khác.')
    item = SubscriptionRequest.objects.create(
        account=account, requested_by=request.user, client_token=client_token,
        reference=f'{settings.BILLING_REFERENCE_PREFIX}{uuid.uuid4().hex[:16].upper()}',
        plan_key=plan['key'], plan_name=plan['name'], billing_cycle=billing_cycle,
        kind='renewal' if adapter.current_plan_key(account) == plan_key else 'change',
        amount_vnd=plan[billing_cycle], customer_note=customer_note,
    )
    PaymentAttempt.objects.create(request=item, expected_amount_vnd=item.amount_vnd)
    return item


def _locked_request(request_id):
    account_id = SubscriptionRequest.objects.values_list('account_id', flat=True).get(pk=request_id)
    account = lock_account(account_id)
    item = SubscriptionRequest.objects.select_for_update().get(pk=request_id)
    return item, account


def _activate(item, account, *, reviewer, note, amount):
    if item.status != SubscriptionRequest.Status.PENDING:
        raise ValidationError('Yêu cầu đã được xử lý.')
    item.approved_amount_vnd = amount
    adapter.activate(account, item)
    item.status = SubscriptionRequest.Status.APPROVED
    item.review_note = note
    item.reviewed_by = reviewer
    item.reviewed_at = item.activated_at = timezone.now()
    item.save(update_fields=['status', 'approved_amount_vnd', 'review_note', 'reviewed_by', 'reviewed_at', 'activated_at'])
    return item


@transaction.atomic
def review_request(request_id, reviewer, *, decision, note='', confirmed_amount=None):
    if not reviewer.is_active or not reviewer.is_superuser:
        raise PermissionDenied('Chỉ quản trị viên hệ thống được xử lý yêu cầu.')
    item, account = _locked_request(request_id)
    if item.status != SubscriptionRequest.Status.PENDING:
        raise ValidationError('Yêu cầu đã được xử lý.')
    if decision == 'approved':
        amount = item.amount_vnd if confirmed_amount is None else confirmed_amount
        if amount is None or isinstance(amount, bool) or int(amount) != amount or amount < 0:
            raise ValidationError('Cần xác nhận số tiền cho yêu cầu báo giá.')
        if item.amount_vnd is not None and amount != item.amount_vnd:
            raise ValidationError('Số tiền xác nhận phải khớp giá đã lưu trong yêu cầu.')
        _activate(item, account, reviewer=reviewer, note=note, amount=amount)
        payment = item.payments.select_for_update().filter(status='pending', provider='manual').first()
        if payment is None:
            payment = PaymentAttempt.objects.create(request=item, provider='manual', expected_amount_vnd=amount)
        payment.expected_amount_vnd = amount
        payment.received_amount_vnd = amount
        payment.provider_reference = f'manual:{item.id}'
        payment.confirmed_at = timezone.now()
        payment.status = PaymentAttempt.Status.SUCCEEDED
        payment.save()
        item.payments.filter(status='pending').exclude(pk=payment.pk).update(status='cancelled')
    elif decision in ('rejected', 'cancelled'):
        item.status = decision
        item.review_note = note
        item.reviewed_by = reviewer
        item.reviewed_at = timezone.now()
        item.save(update_fields=['status', 'review_note', 'reviewed_by', 'reviewed_at'])
        item.payments.filter(status='pending').update(status='cancelled')
    else:
        raise ValidationError('Trạng thái xử lý không hợp lệ.')
    return item


@transaction.atomic
def cancel_request(request, request_id):
    account = lock_account(account_for(request).pk)
    item = SubscriptionRequest.objects.select_for_update().get(pk=request_id, account=account)
    if item.status != 'pending':
        raise ValidationError('Chỉ có thể hủy yêu cầu đang chờ xử lý.')
    item.status = 'cancelled'
    item.reviewed_at = timezone.now()
    item.review_note = 'Khách hàng đã hủy yêu cầu.'
    item.save(update_fields=['status', 'reviewed_at', 'review_note'])
    item.payments.filter(status='pending').update(status='cancelled')
    return item


@transaction.atomic
def create_payment_attempt(request_id, *, provider):
    """Internal provider boundary. Only priced, pending requests can start checkout."""
    if provider not in getattr(settings, 'BILLING_PAYMENT_PROVIDERS', ()):
        raise ValidationError('Kênh thanh toán chưa được bật.')
    item, _ = _locked_request(request_id)
    if item.status != 'pending' or item.amount_vnd is None or item.amount_vnd <= 0:
        raise ValidationError('Yêu cầu chưa đủ điều kiện thanh toán tự động.')
    payment = item.payments.filter(provider=provider, status='pending').first()
    return payment or PaymentAttempt.objects.create(
        request=item, provider=provider, expected_amount_vnd=item.amount_vnd, currency=item.currency,
    )


@transaction.atomic
def record_verified_payment(payment_id, *, transaction_id, amount_vnd, currency='VND'):
    """Trusted provider adapter ONLY: authenticate and validate the bank event before calling.

    The eventual SePay webhook must check signature, recipient account, inbound direction
    and payment reference first. This function enforces amount, uniqueness and activation.
    """
    seed = PaymentAttempt.objects.get(pk=payment_id)
    item, account = _locked_request(seed.request_id)
    payment = PaymentAttempt.objects.select_for_update().get(pk=payment_id)
    if payment.provider == 'manual':
        raise ValidationError('Giao dịch thủ công phải được quản trị viên xác nhận.')
    if not isinstance(transaction_id, str) or not transaction_id.strip() or len(transaction_id) > 128:
        raise ValidationError('Mã giao dịch không hợp lệ.')
    if currency != payment.currency or currency != item.currency or payment.expected_amount_vnd is None or payment.expected_amount_vnd != item.amount_vnd:
        raise ValidationError('Chưa có báo giá hoặc sai đơn vị tiền tệ.')
    if isinstance(amount_vnd, bool) or not isinstance(amount_vnd, int) or amount_vnd < payment.expected_amount_vnd:
        raise ValidationError('Số tiền chưa đủ hoặc không hợp lệ.')
    if payment.status == 'succeeded':
        if payment.provider_reference == transaction_id:
            return item  # Repeated callback: never extend a subscription twice.
        raise ValidationError('Lần thanh toán này đã được xác nhận bằng giao dịch khác.')
    if payment.status != 'pending' or item.status != 'pending':
        raise ValidationError('Yêu cầu đã được xử lý hoặc hủy.')
    if PaymentAttempt.objects.filter(provider=payment.provider, provider_reference=transaction_id).exclude(pk=payment.pk).exists():
        raise ValidationError('Giao dịch đã được sử dụng cho yêu cầu khác.')
    payment.provider_reference = transaction_id
    payment.received_amount_vnd = amount_vnd
    payment.confirmed_at = timezone.now()
    payment.status = 'succeeded'
    payment.save()
    _activate(item, account, reviewer=None, note='Đã xác nhận thanh toán.', amount=payment.expected_amount_vnd)
    item.payments.filter(status='pending').exclude(pk=payment.pk).update(status='cancelled')
    return item
