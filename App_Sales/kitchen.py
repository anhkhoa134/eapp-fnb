"""Nghiệp vụ màn hình bếp: tạo phiếu bếp, báo bếp giỏ bàn, huỷ/đổi trạng thái món."""

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from App_Sales.models import KitchenTicket, KitchenTicketItem, TableCartItem
from App_Sales.realtime import notify_kitchen_changed

OPEN_STATUSES = KitchenTicketItem.OPEN_STATUSES


def kitchen_enabled(tenant) -> bool:
    return bool(tenant and tenant.show_kitchen_feature)


def toppings_text(names) -> str:
    return ', '.join(name for name in names if name)[:500]


def _notify_on_commit(*, store_id, reason, ticket_id=None, message=''):
    transaction.on_commit(
        lambda: notify_kitchen_changed(store_id=store_id, reason=reason, ticket_id=ticket_id, message=message)
    )


def create_kitchen_ticket(
    *,
    tenant,
    store,
    source,
    rows,
    table=None,
    table_name='',
    order=None,
    qr_order=None,
    created_by=None,
):
    """
    rows: list dict {name, unit_name, quantity, note, toppings_text, product_id, table_cart_item}.
    Trả về KitchenTicket hoặc None nếu không có món nào.
    """
    rows = [row for row in rows if int(row.get('quantity') or 0) > 0]
    if not rows:
        return None

    ticket = KitchenTicket.objects.create(
        tenant=tenant,
        store=store,
        table=table,
        table_name=(table_name or (table.name if table else ''))[:120],
        source=source,
        order=order,
        qr_order=qr_order,
        created_by=created_by,
    )
    KitchenTicketItem.objects.bulk_create(
        [
            KitchenTicketItem(
                ticket=ticket,
                table_cart_item=row.get('table_cart_item'),
                product_id=row.get('product_id'),
                snapshot_product_name=(row.get('name') or '')[:180],
                snapshot_unit_name=(row.get('unit_name') or '')[:120],
                toppings_text=(row.get('toppings_text') or '')[:500],
                quantity=int(row['quantity']),
                note=(row.get('note') or '')[:255],
            )
            for row in rows
        ]
    )
    _notify_on_commit(
        store_id=store.id,
        reason='created',
        ticket_id=ticket.id,
        message=f'{ticket.table_name}: có phiếu bếp mới',
    )
    return ticket


def _cart_item_row(item: TableCartItem, quantity: int):
    return {
        'table_cart_item': item,
        'product_id': item.product_id,
        'name': item.snapshot_product_name,
        'unit_name': item.snapshot_unit_name,
        'toppings_text': toppings_text(row.snapshot_topping_name for row in item.toppings.all()),
        'quantity': quantity,
        'note': item.note,
    }


def unsent_kitchen_quantity(table) -> int:
    return sum(
        max(quantity - sent, 0)
        for quantity, sent in TableCartItem.objects.filter(table=table).values_list('quantity', 'kitchen_sent_quantity')
    )


def send_table_cart_to_kitchen(*, table, user=None, order=None):
    """Báo bếp phần số lượng chưa gửi của giỏ bàn. Phải gọi trong transaction.atomic."""
    items = list(
        TableCartItem.objects.select_for_update()
        .filter(table=table)
        .prefetch_related('toppings')
        .order_by('created_at', 'id')
    )
    rows = []
    sent_ids = []
    for item in items:
        pending = item.quantity - item.kitchen_sent_quantity
        if pending <= 0:
            continue
        rows.append(_cart_item_row(item, pending))
        sent_ids.append(item.id)

    if not rows:
        return None

    TableCartItem.objects.filter(id__in=sent_ids).update(kitchen_sent_quantity=F('quantity'), updated_at=timezone.now())
    return create_kitchen_ticket(
        tenant=table.tenant,
        store=table.store,
        source=KitchenTicket.Source.TABLE,
        rows=rows,
        table=table,
        order=order,
        created_by=user,
    )


def refresh_ticket_completion(ticket: KitchenTicket):
    has_open = ticket.items.filter(status__in=OPEN_STATUSES).exists()
    completed_at = None if has_open else (ticket.completed_at or timezone.now())
    if completed_at != ticket.completed_at:
        ticket.completed_at = completed_at
        ticket.save(update_fields=['completed_at', 'updated_at'])


def cancel_kitchen_quantity(item: TableCartItem, quantity: int) -> int:
    """
    Huỷ tối đa `quantity` phần chưa xong trong bếp của một món giỏ bàn
    (ưu tiên phần chờ làm mới nhất). Trả về số phần đã huỷ; phần đã xong giữ nguyên.
    """
    remaining = int(quantity)
    if remaining <= 0:
        return 0

    open_items = sorted(
        KitchenTicketItem.objects.select_related('ticket').filter(table_cart_item=item, status__in=OPEN_STATUSES),
        key=lambda row: (row.status != KitchenTicketItem.Status.PENDING, -row.id),
    )
    cancelled = 0
    touched_tickets = {}
    for kitchen_item in open_items:
        if remaining <= 0:
            break
        if kitchen_item.quantity <= remaining:
            remaining -= kitchen_item.quantity
            cancelled += kitchen_item.quantity
            kitchen_item.status = KitchenTicketItem.Status.CANCELLED
            kitchen_item.save(update_fields=['status', 'updated_at'])
        else:
            # Tách phần bị huỷ thành dòng riêng để bếp thấy rõ "Đã huỷ xN".
            kitchen_item.quantity -= remaining
            kitchen_item.save(update_fields=['quantity', 'updated_at'])
            KitchenTicketItem.objects.create(
                ticket=kitchen_item.ticket,
                table_cart_item=item,
                product_id=kitchen_item.product_id,
                snapshot_product_name=kitchen_item.snapshot_product_name,
                snapshot_unit_name=kitchen_item.snapshot_unit_name,
                toppings_text=kitchen_item.toppings_text,
                quantity=remaining,
                note=kitchen_item.note,
                status=KitchenTicketItem.Status.CANCELLED,
            )
            cancelled += remaining
            remaining = 0
        touched_tickets[kitchen_item.ticket_id] = kitchen_item.ticket

    for ticket in touched_tickets.values():
        refresh_ticket_completion(ticket)

    if cancelled:
        ticket = next(iter(touched_tickets.values()))
        _notify_on_commit(
            store_id=item.store_id,
            reason='cancelled',
            ticket_id=ticket.id,
            message=f'{ticket.table_name}: huỷ {item.snapshot_product_name} x{cancelled}',
        )
    return cancelled


def sync_kitchen_on_quantity_decrease(item: TableCartItem, new_quantity: int):
    """Gọi trước khi giảm số lượng / xoá món giỏ bàn (new_quantity=0). Không tự save item."""
    new_quantity = max(int(new_quantity), 0)
    over = item.kitchen_sent_quantity - new_quantity
    if over <= 0:
        return
    cancel_kitchen_quantity(item, over)
    item.kitchen_sent_quantity = new_quantity


def sync_kitchen_on_item_modified(item: TableCartItem):
    """Món đã báo bếp bị đổi topping/ghi chú: huỷ phần chưa xong để báo bếp lại. Không tự save item."""
    if item.kitchen_sent_quantity <= 0:
        return
    cancelled = cancel_kitchen_quantity(item, item.kitchen_sent_quantity)
    item.kitchen_sent_quantity -= cancelled


def move_kitchen_links(*, source_item: TableCartItem, target_item: TableCartItem):
    KitchenTicketItem.objects.filter(table_cart_item=source_item).update(table_cart_item=target_item)


def move_open_tickets_to_table(*, from_table, to_table):
    moved = KitchenTicket.objects.filter(table=from_table, completed_at__isnull=True).update(
        table=to_table,
        table_name=to_table.name[:120],
        updated_at=timezone.now(),
    )
    if moved:
        _notify_on_commit(
            store_id=to_table.store_id,
            reason='moved',
            message=f'Chuyển {from_table.name} sang {to_table.name}',
        )
    return moved


def set_kitchen_item_status(kitchen_item: KitchenTicketItem, status: str):
    now = timezone.now()
    kitchen_item.status = status
    if status == KitchenTicketItem.Status.PENDING:
        kitchen_item.started_at = None
        kitchen_item.done_at = None
    elif status == KitchenTicketItem.Status.PREPARING:
        kitchen_item.started_at = kitchen_item.started_at or now
        kitchen_item.done_at = None
    elif status == KitchenTicketItem.Status.DONE:
        kitchen_item.started_at = kitchen_item.started_at or now
        kitchen_item.done_at = now
    kitchen_item.save(update_fields=['status', 'started_at', 'done_at', 'updated_at'])

    ticket = kitchen_item.ticket
    refresh_ticket_completion(ticket)
    is_done = status == KitchenTicketItem.Status.DONE
    _notify_on_commit(
        store_id=ticket.store_id,
        reason='done' if is_done else 'status',
        ticket_id=ticket.id,
        message=(
            f'{ticket.table_name}: {kitchen_item.snapshot_product_name} x{kitchen_item.quantity} đã xong'
            if is_done
            else ''
        ),
    )


def complete_kitchen_ticket(ticket: KitchenTicket) -> int:
    now = timezone.now()
    open_items = ticket.items.filter(status__in=OPEN_STATUSES)
    updated = 0
    for kitchen_item in open_items:
        kitchen_item.status = KitchenTicketItem.Status.DONE
        kitchen_item.started_at = kitchen_item.started_at or now
        kitchen_item.done_at = now
        kitchen_item.save(update_fields=['status', 'started_at', 'done_at', 'updated_at'])
        updated += 1
    refresh_ticket_completion(ticket)
    if updated:
        _notify_on_commit(
            store_id=ticket.store_id,
            reason='done',
            ticket_id=ticket.id,
            message=f'{ticket.table_name}: đã xong cả phiếu',
        )
    return updated


def _iso(value):
    return timezone.localtime(value).isoformat() if value else None


def serialize_kitchen_ticket(ticket: KitchenTicket):
    items = list(ticket.items.all())
    return {
        'id': ticket.id,
        'table_id': ticket.table_id,
        'table_name': ticket.table_name,
        'source': ticket.source,
        'source_label': ticket.get_source_display(),
        'order_code': ticket.order.order_code if ticket.order_id else '',
        'created_by': ticket.created_by.username if ticket.created_by_id else '',
        'created_at': _iso(ticket.created_at),
        'completed_at': _iso(ticket.completed_at),
        'print_count': ticket.print_count,
        'items': [
            {
                'id': row.id,
                'name': row.snapshot_product_name,
                'unit': row.snapshot_unit_name,
                'toppings': row.toppings_text,
                'quantity': row.quantity,
                'note': row.note,
                'status': row.status,
                'status_label': row.get_status_display(),
                'started_at': _iso(row.started_at),
                'done_at': _iso(row.done_at),
            }
            for row in items
        ],
    }
