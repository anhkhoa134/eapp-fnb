import logging
import time

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone

logger = logging.getLogger(__name__)
_CHANNEL_LAYER_BACKOFF_SECONDS = 5
_channel_layer_retry_after = 0.0


def pos_store_group_name(store_id):
    return f'pos_store_{int(store_id)}'


def public_qr_order_group_name(order_id):
    return f'public_qr_order_{int(order_id)}'


def _safe_group_send(group_name, event):
    global _channel_layer_retry_after

    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    using_inmemory = channel_layer.__class__.__name__ == 'InMemoryChannelLayer'
    if using_inmemory:
        _channel_layer_retry_after = 0.0
    elif time.monotonic() < _channel_layer_retry_after:
        return

    try:
        async_to_sync(channel_layer.group_send)(group_name, event)
    except Exception:
        _channel_layer_retry_after = time.monotonic() + _CHANNEL_LAYER_BACKOFF_SECONDS
        logger.warning('WebSocket notify failed for group=%s', group_name, exc_info=True)


def notify_pos_qr_changed(*, store_id, order_id, reason):
    payload = {
        'type': 'qr.changed',
        'store_id': int(store_id),
        'order_id': int(order_id),
        'reason': str(reason),
        'ts': timezone.now().isoformat(),
    }
    _safe_group_send(
        pos_store_group_name(store_id),
        {
            'type': 'qr.changed',
            'data': payload,
        },
    )


def notify_public_qr_order_changed(*, order_id, status, reason):
    payload = {
        'type': 'qr.order.changed',
        'order_id': int(order_id),
        'status': str(status),
        'reason': str(reason),
        'ts': timezone.now().isoformat(),
    }
    _safe_group_send(
        public_qr_order_group_name(order_id),
        {
            'type': 'qr.order.changed',
            'data': payload,
        },
    )


def notify_qr_order_changed(*, store_id, order_id, status, reason):
    notify_pos_qr_changed(store_id=store_id, order_id=order_id, reason=reason)
    notify_public_qr_order_changed(order_id=order_id, status=status, reason=reason)
