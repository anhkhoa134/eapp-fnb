"""FNB-11 (quyết định 28/11/2026): đơn QR chờ duyệt tự huỷ sau 30 phút, tối đa 3 đơn chờ mỗi bàn.

Không có hàng đợi tác vụ nền: đơn quá hạn được huỷ "lười" mỗi khi POS / khách xem đơn, khi duyệt và
khi khách đặt đơn mới. Có thể chạy thêm `python manage.py expire_qr_orders` theo cron để dọn định kỳ.
Đơn quá hạn chuyển sang "Đã từ chối" (không có người từ chối) kèm lý do, không cần thêm trạng thái mới.
"""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from App_Sales.models import QROrder
from App_Sales.realtime import notify_qr_order_changed

QR_ORDER_PENDING_MINUTES = getattr(settings, 'QR_ORDER_PENDING_MINUTES', 30)
QR_ORDER_MAX_PENDING_PER_TABLE = getattr(settings, 'QR_ORDER_MAX_PENDING_PER_TABLE', 3)
QR_ORDER_EXPIRED_REASON = f'Tự huỷ: quán chưa duyệt trong {QR_ORDER_PENDING_MINUTES} phút.'
QR_ORDER_TABLE_LIMIT_MESSAGE = (
    f'Bàn đang có {QR_ORDER_MAX_PENDING_PER_TABLE} đơn chờ quán duyệt. '
    'Vui lòng chờ quán xác nhận hoặc gọi nhân viên.'
)


def pending_cutoff(now=None):
    return (now or timezone.now()) - timedelta(minutes=QR_ORDER_PENDING_MINUTES)


def is_expired(order, now=None) -> bool:
    return order.status == QROrder.Status.PENDING and order.created_at < pending_cutoff(now)


def expire_stale_qr_orders(now=None, **filters) -> int:
    """Huỷ các đơn chờ duyệt quá hạn (lọc thêm theo filters, VD store_id=, table_id=, id=)."""
    now = now or timezone.now()
    stale = list(
        QROrder.objects.filter(status=QROrder.Status.PENDING, created_at__lt=pending_cutoff(now), **filters)
        .values_list('id', 'store_id')
    )
    if not stale:
        return 0
    updated = QROrder.objects.filter(id__in=[row[0] for row in stale], status=QROrder.Status.PENDING).update(
        status=QROrder.Status.REJECTED,
        rejection_reason=QR_ORDER_EXPIRED_REASON,
        resolved_at=now,
        updated_at=now,
    )

    def _notify():
        for order_id, store_id in stale:
            notify_qr_order_changed(
                store_id=store_id, order_id=order_id, status=QROrder.Status.REJECTED, reason='expired'
            )

    transaction.on_commit(_notify)
    return updated


def table_pending_limit_reached(table) -> bool:
    return (
        QROrder.objects.filter(table=table, status=QROrder.Status.PENDING).count()
        >= QR_ORDER_MAX_PENDING_PER_TABLE
    )
