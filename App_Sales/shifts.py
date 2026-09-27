"""Ca làm việc: mở ca, tổng hợp số liệu trong ca, chốt ca đối soát tiền mặt."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from App_Core.audit import Action, log_action
from App_Core.templatetags.number_format import thousand_sep
from App_Sales.models import Order, OrderItem, Refund, Shift

ZERO = Decimal('0')


def shift_enabled(tenant) -> bool:
    return bool(tenant and tenant.show_shift_feature)


def get_open_shift(store):
    if store is None:
        return None
    return Shift.objects.filter(store=store, status=Shift.Status.OPEN).select_related('opened_by').first()


def _shift_orders(shift, end):
    return Order.objects.filter(
        store_id=shift.store_id,
        created_at__gte=shift.opened_at,
        created_at__lte=end,
    ).exclude(status=Order.Status.CANCELLED)


def compute_shift_summary(shift, *, until=None):
    """Số liệu trong khoảng [opened_at, closed_at hoặc until/now] của cửa hàng."""
    end = shift.closed_at or until or timezone.now()
    orders = _shift_orders(shift, end)
    order_stats = orders.aggregate(
        order_count=Count('id'),
        gross_sales=Coalesce(Sum('total_amount'), ZERO),
        cash_sales=Coalesce(Sum('total_amount', filter=Q(payment_method=Order.PaymentMethod.CASH)), ZERO),
        card_sales=Coalesce(Sum('total_amount', filter=Q(payment_method=Order.PaymentMethod.CARD)), ZERO),
        discount_total=Coalesce(Sum('discount_amount'), ZERO),
    )
    refund_stats = Refund.objects.filter(
        store_id=shift.store_id,
        created_at__gte=shift.opened_at,
        created_at__lte=end,
    ).aggregate(
        refund_total=Coalesce(Sum('amount'), ZERO),
        cash_refunds=Coalesce(Sum('amount', filter=Q(method=Order.PaymentMethod.CASH)), ZERO),
        refund_count=Count('id'),
    )
    summary = {**order_stats, **refund_stats}
    summary['net_sales'] = summary['gross_sales'] - summary['refund_total']
    summary['expected_cash'] = shift.opening_cash + summary['cash_sales'] - summary['cash_refunds']
    summary['end'] = end
    return summary


def shift_item_breakdown(shift, *, until=None):
    """Món bán ra trong ca, gộp theo tên + đơn vị, nhiều nhất trước."""
    end = shift.closed_at or until or timezone.now()
    return list(
        OrderItem.objects.filter(order__in=_shift_orders(shift, end))
        .values('snapshot_product_name', 'snapshot_unit_name')
        .annotate(quantity=Sum('quantity'), amount=Sum('line_total'))
        .order_by('-quantity', 'snapshot_product_name')
    )


def open_shift(*, store, user, opening_cash, note=''):
    if opening_cash < 0:
        raise ValidationError('Tiền đầu ca không được âm.')
    try:
        with transaction.atomic():
            shift = Shift.objects.create(
                tenant_id=store.tenant_id,
                store=store,
                opened_by=user,
                opened_at=timezone.now(),
                opening_cash=opening_cash,
                note=(note or '').strip()[:500],
            )
    except IntegrityError:
        raise ValidationError(f'Cửa hàng "{store.name}" đang có ca mở, hãy chốt ca đó trước.')
    log_action(
        Action.SHIFT_OPEN,
        user=user,
        tenant_id=store.tenant_id,
        store=store,
        obj=shift,
        message=f'Mở ca #{shift.id} tại {store.name}, tiền đầu ca {thousand_sep(opening_cash)} đ',
        extra={'opening_cash': str(opening_cash)},
    )
    return shift


def close_shift(*, shift, user, counted_cash, note=''):
    if counted_cash < 0:
        raise ValidationError('Tiền mặt thực đếm không được âm.')
    with transaction.atomic():
        shift = Shift.objects.select_for_update().select_related('store').get(pk=shift.pk)
        if shift.status != Shift.Status.OPEN:
            raise ValidationError('Ca này đã được chốt.')
        closed_at = timezone.now()
        summary = compute_shift_summary(shift, until=closed_at)
        shift.status = Shift.Status.CLOSED
        shift.closed_at = closed_at
        shift.closed_by = user
        shift.order_count = summary['order_count']
        shift.gross_sales = summary['gross_sales']
        shift.cash_sales = summary['cash_sales']
        shift.card_sales = summary['card_sales']
        shift.discount_total = summary['discount_total']
        shift.refund_total = summary['refund_total']
        shift.cash_refunds = summary['cash_refunds']
        shift.expected_cash = summary['expected_cash']
        shift.counted_cash = counted_cash
        shift.cash_difference = counted_cash - summary['expected_cash']
        note = (note or '').strip()
        if note:
            shift.note = f'{shift.note}\n{note}'.strip()[:500]
        shift.save()
    diff = shift.cash_difference
    log_action(
        Action.SHIFT_CLOSE,
        user=user,
        tenant_id=shift.tenant_id,
        store=shift.store,
        obj=shift,
        message=(
            f'Chốt ca #{shift.id} tại {shift.store.name}: dự kiến {thousand_sep(shift.expected_cash)} đ, '
            f'thực đếm {thousand_sep(counted_cash)} đ, chênh lệch {"+" if diff > 0 else ""}{thousand_sep(diff)} đ'
        ),
        extra={
            'expected_cash': str(shift.expected_cash),
            'counted_cash': str(counted_cash),
            'cash_difference': str(diff),
        },
    )
    return shift
