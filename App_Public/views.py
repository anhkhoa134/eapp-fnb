import json
import re
import secrets
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from App_Accounts import rate_limit
from App_Accounts.login_throttle import get_client_ip
from App_Catalog.models import Product, ProductTopping, ProductUnit
from App_Catalog.services import calc_toppings_total, resolve_product_topping_links
from App_Sales.models import DiningTable, QROrder, QROrderItem, QROrderItemTopping
from App_Sales.realtime import notify_qr_order_changed
from App_Sales.services import get_effective_unit_price
from App_Tenant.models import Store, Tenant

PLACEHOLDER_PRODUCT_IMAGE = 'https://placehold.co/600x600/png?text=Product'
TAKEAWAY_ORDER_LIMIT_PER_IP = 10
TAKEAWAY_ORDER_WINDOW = timedelta(minutes=30)
PHONE_RE = re.compile(r'^(\+?84|0)\d{8,10}$')


def _json_error(detail, status=400):
    return JsonResponse({'detail': detail}, status=status)


def _parse_json_request(request):
    try:
        return json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return None


def _has_requested_toppings(raw_topping_ids) -> bool:
    if raw_topping_ids in (None, '', []):
        return False
    if isinstance(raw_topping_ids, (list, tuple, set)):
        return any(str(item).strip() for item in raw_topping_ids)
    return bool(str(raw_topping_ids).strip())


def _normalize_phone(raw) -> str:
    return re.sub(r'[\s.\-()]', '', (raw or '').strip())


def _product_image_url(request, product):
    raw = product.get_catalog_image_url()
    if not raw:
        return PLACEHOLDER_PRODUCT_IMAGE
    if raw.startswith('http'):
        return raw
    return request.build_absolute_uri(raw)


def _takeaway_ordering_enabled(tenant) -> bool:
    return tenant.show_qr_order_feature and not tenant.is_subscription_expired()


def _get_table_by_credentials(*, table_code, token, tenant=None):
    filters = {
        'code': (table_code or '').strip().upper(),
        'qr_token': (token or '').strip(),
        'is_active': True,
        'store__is_active': True,
        'tenant__is_active': True,
    }
    if tenant is not None:
        filters['tenant'] = tenant
    return DiningTable.objects.select_related('store', 'tenant').filter(**filters).first()


def _resolve_order_access(params):
    """Khách xem/sửa/huỷ đơn của mình: đơn tại bàn dùng table_code + token, đơn mang đi dùng access_key.

    Trả về (bộ lọc QROrder, tenant, lỗi JsonResponse | None).
    """
    access_key = (params.get('access_key') or '').strip()
    if access_key:
        return (
            {
                'access_key': access_key,
                'order_type': QROrder.OrderType.TAKEAWAY,
                'tenant__is_active': True,
                'store__is_active': True,
            },
            None,
            None,
        )

    table_code = (params.get('table_code') or '').strip().upper()
    token = (params.get('token') or '').strip()
    if not table_code or not token:
        return None, None, _json_error('Thiếu table_code hoặc token.', 400)

    table = _get_table_by_credentials(table_code=table_code, token=token)
    if not table:
        return None, None, _json_error('QR không hợp lệ hoặc đã hết hiệu lực.', 403)
    return {'tenant': table.tenant, 'table': table}, table.tenant, None


def _serialize_qr_order(order):
    items_payload = []
    total = Decimal('0')

    for item in order.items.all().order_by('id'):
        line_total = item.unit_price_snapshot * item.quantity
        total += line_total
        toppings_payload = []
        topping_ids = []

        for topping in item.toppings.all().order_by('id'):
            topping_ids.append(topping.topping_id)
            toppings_payload.append(
                {
                    'id': topping.topping_id,
                    'name': topping.snapshot_topping_name,
                    'price': float(topping.snapshot_price),
                }
            )

        items_payload.append(
            {
                'product_id': item.product_id,
                'unit_id': item.unit_id,
                'name': item.snapshot_product_name,
                'size': item.snapshot_unit_name,
                'price': float(item.unit_price_snapshot),
                'qty': item.quantity,
                'note': item.note,
                'line_total': float(line_total),
                'toppings': toppings_payload,
                'topping_ids': [top_id for top_id in topping_ids if top_id],
            }
        )

    return {
        'id': order.id,
        'status': order.status,
        'order_type': order.order_type,
        'is_pending': order.status == QROrder.Status.PENDING,
        'can_edit': order.status == QROrder.Status.PENDING,
        'can_cancel': order.status == QROrder.Status.PENDING,
        'customer_note': order.customer_note,
        'customer_name': order.customer_name,
        'customer_phone': order.customer_phone,
        'rejection_reason': order.rejection_reason if order.status == QROrder.Status.REJECTED else '',
        'is_paid': bool(order.sale_order_id),
        'created_at': order.created_at.isoformat(),
        'resolved_at': order.resolved_at.isoformat() if order.resolved_at else None,
        'time': timezone.localtime(order.created_at).strftime('%H:%M'),
        'table': (
            {'id': order.table_id, 'name': order.table.name, 'code': order.table.code}
            if order.table_id
            else None
        ),
        'store': {'id': order.store_id, 'name': order.store.name},
        'total': float(total),
        'items': items_payload,
    }


def _prepare_order_items(*, tenant, store, raw_items):
    if not raw_items:
        raise ValueError('Giỏ hàng đang trống.')

    prepared_items = []
    for raw in raw_items:
        product_id = raw.get('product_id')
        unit_id = raw.get('unit_id')
        try:
            quantity = int(raw.get('quantity', 0))
        except (TypeError, ValueError):
            raise ValueError('Số lượng không hợp lệ.')

        if quantity <= 0:
            raise ValueError('Số lượng phải lớn hơn 0.')

        unit = ProductUnit.objects.select_related('product').filter(
            id=unit_id,
            product_id=product_id,
            product__tenant=tenant,
            product__is_active=True,
            is_active=True,
            product__store_links__store=store,
            product__store_links__is_available=True,
        ).first()
        if not unit:
            raise ValueError(f'Sản phẩm hoặc đơn vị không hợp lệ: {product_id}/{unit_id}')

        if unit.product.category_id:
            visible = unit.product.category.store_links.filter(store=store, is_visible=True).exists()
            if not visible:
                raise ValueError(f'Món hiện không phục vụ: {unit.product.name}')

        note = (raw.get('note') or '').strip()[:255]
        raw_topping_ids = raw.get('topping_ids')
        if not tenant.show_topping_feature and _has_requested_toppings(raw_topping_ids):
            raise ValueError('Tính năng topping đang tắt.')
        topping_links = resolve_product_topping_links(
            product=unit.product,
            topping_ids=raw_topping_ids,
        )

        base_unit_price = get_effective_unit_price(unit=unit, store_id=store.id)
        topping_total = calc_toppings_total(topping_links)
        unit_price = base_unit_price + topping_total

        prepared_items.append(
            {
                'product': unit.product,
                'unit': unit,
                'quantity': quantity,
                'note': note,
                'unit_price': unit_price,
                'snapshot_toppings': [
                    {
                        'topping_id': link.topping_id,
                        'name': link.topping.name,
                        'price': (getattr(link.topping, 'price', None) or link.price),
                    }
                    for link in topping_links
                ],
            }
        )

    return prepared_items


def _replace_qr_order_items(*, qr_order, prepared_items):
    qr_order.items.all().delete()

    for item in prepared_items:
        qr_item = QROrderItem.objects.create(
            qr_order=qr_order,
            product=item['product'],
            unit=item['unit'],
            snapshot_product_name=item['product'].name,
            snapshot_unit_name=item['unit'].name,
            unit_price_snapshot=item['unit_price'],
            quantity=item['quantity'],
            note=item['note'],
            line_total=Decimal('0'),
        )

        QROrderItemTopping.objects.bulk_create(
            [
                QROrderItemTopping(
                    qr_order_item=qr_item,
                    topping_id=topping['topping_id'],
                    snapshot_topping_name=topping['name'],
                    snapshot_price=topping['price'],
                )
                for topping in item['snapshot_toppings']
            ]
        )


def _build_products_payload(*, tenant, store, request):
    queryset = (
        Product.objects.filter(
            tenant=tenant,
            is_active=True,
            store_links__store=store,
            store_links__is_available=True,
        )
        .select_related('category')
        .prefetch_related(
            Prefetch(
                'units',
                queryset=ProductUnit.objects.filter(is_active=True).order_by('display_order', 'id'),
            ),
            Prefetch(
                'topping_links',
                queryset=ProductTopping.objects.select_related('topping').filter(
                    is_active=True,
                    topping__is_active=True,
                ).order_by('display_order', 'id'),
            ),
        )
        .distinct()
        .order_by('name')
    )

    queryset = queryset.filter(
        Q(category__isnull=True)
        | Q(category__store_links__store=store, category__store_links__is_visible=True)
    )

    categories = [{'id': 'all', 'name': 'Tất cả'}]
    category_seen = set()
    products = []

    for product in queryset:
        units_payload = []
        for unit in product.units.all():
            unit_price = get_effective_unit_price(unit=unit, store_id=store.id)
            units_payload.append({'id': unit.id, 'name': unit.name, 'price': float(unit_price)})

        if not units_payload:
            continue

        if product.category_id and product.category_id not in category_seen:
            category_seen.add(product.category_id)
            categories.append({'id': str(product.category_id), 'name': product.category.name})

        toppings_payload = []
        if tenant.show_topping_feature:
            for link in product.topping_links.all():
                toppings_payload.append(
                    {
                        'id': link.topping_id,
                        'name': link.topping.name,
                        'price': float((getattr(link.topping, 'price', None) or link.price)),
                    }
                )

        products.append(
            {
                'id': product.id,
                'name': product.name,
                'description': (product.description or '').strip(),
                'image': _product_image_url(request, product),
                'category_id': str(product.category_id or ''),
                'category_name': product.category.name if product.category else 'Khác',
                'units': units_payload,
                'base_price': min(unit['price'] for unit in units_payload),
                'toppings': toppings_payload,
            }
        )

    return categories, products


def _reload_order(order_id):
    return (
        QROrder.objects.select_related('table', 'store')
        .prefetch_related('items', 'items__toppings')
        .get(pk=order_id)
    )


@require_GET
def tenant_catalog(request, public_slug):
    tenant = get_object_or_404(Tenant, public_slug=public_slug, is_active=True)
    stores = list(Store.objects.filter(tenant=tenant, is_active=True).order_by('name'))

    selected_store_id = (request.GET.get('store') or '').strip()
    selected_store = None
    if selected_store_id.isdigit():
        selected_store = next((row for row in stores if row.id == int(selected_store_id)), None)
    if not selected_store:
        selected_store = next((row for row in stores if row.is_default), None) or (stores[0] if stores else None)

    categories, products = [], []
    if selected_store:
        categories, products = _build_products_payload(tenant=tenant, store=selected_store, request=request)

    ordering_enabled = bool(selected_store) and _takeaway_ordering_enabled(tenant)
    bootstrap_data = {
        'mode': 'takeaway',
        'tenant_slug': tenant.public_slug,
        'tenant_name': tenant.name,
        'ordering_enabled': ordering_enabled,
        'store': (
            {
                'id': selected_store.id,
                'name': selected_store.name,
                'address': selected_store.address,
                'phone': selected_store.phone,
            }
            if selected_store
            else None
        ),
        'categories': categories,
        'products': products,
    }

    return render(
        request,
        'App_Public/catalog.html',
        {
            'tenant': tenant,
            'stores': stores,
            'selected_store': selected_store,
            'ordering_enabled': ordering_enabled,
            'order_bootstrap_data': bootstrap_data,
        },
    )


@require_GET
def tenant_qr_ordering(request, public_slug):
    tenant = get_object_or_404(Tenant, public_slug=public_slug, is_active=True)

    table_code = (request.GET.get('table_code') or '').strip().upper()
    token = (request.GET.get('token') or '').strip()

    qr_error = ''
    table = None
    categories = []
    products = []

    if not table_code or not token:
        qr_error = 'Thiếu thông tin bàn. Vui lòng quét lại mã QR tại bàn.'
    else:
        table = _get_table_by_credentials(tenant=tenant, table_code=table_code, token=token)
        if not table:
            qr_error = 'Mã QR không đúng hoặc đã được đổi. Vui lòng quét lại mã tại bàn hoặc gọi nhân viên.'
        elif not tenant.show_qr_order_feature:
            qr_error = 'Quán tạm ngưng gọi món qua mã QR. Vui lòng gọi nhân viên để đặt món.'
        else:
            categories, products = _build_products_payload(tenant=tenant, store=table.store, request=request)

    bootstrap_data = {
        'mode': 'dine_in',
        'tenant_slug': tenant.public_slug,
        'tenant_name': tenant.name,
        'ordering_enabled': not qr_error,
        'table_code': table.code if table else table_code,
        'token': token,
        'store': {'id': table.store_id, 'name': table.store.name} if table else None,
        'table': {'id': table.id, 'name': table.name, 'code': table.code} if table else None,
        'categories': categories,
        'products': products,
    }

    return render(
        request,
        'App_Public/qr_ordering.html',
        {
            'tenant': tenant,
            'qr_error': qr_error,
            'table': table,
            'order_bootstrap_data': bootstrap_data,
        },
    )


@csrf_exempt
@require_POST
def api_public_qr_orders(request):
    payload = _parse_json_request(request)
    if payload is None:
        return _json_error('Payload JSON không hợp lệ.', 400)

    table_code = (payload.get('table_code') or '').strip().upper()
    token = (payload.get('token') or '').strip()
    customer_note = (payload.get('note') or '').strip()[:255]

    if not table_code or not token:
        return _json_error('Thiếu table_code hoặc token.', 400)

    table = _get_table_by_credentials(table_code=table_code, token=token)
    if not table:
        return _json_error('QR không hợp lệ hoặc đã hết hiệu lực.', 403)
    if not table.tenant.show_qr_order_feature:
        return _json_error('Tính năng gọi món QR đang tắt.', 403)

    raw_items = payload.get('items') or []
    try:
        prepared_items = _prepare_order_items(tenant=table.tenant, store=table.store, raw_items=raw_items)
    except ValueError as exc:
        return _json_error(str(exc), 400)

    with transaction.atomic():
        qr_order = QROrder.objects.create(
            tenant=table.tenant,
            store=table.store,
            table=table,
            order_type=QROrder.OrderType.DINE_IN,
            status=QROrder.Status.PENDING,
            customer_note=customer_note,
            created_by_ip=request.META.get('REMOTE_ADDR') or None,
        )
        _replace_qr_order_items(qr_order=qr_order, prepared_items=prepared_items)

    qr_order = _reload_order(qr_order.pk)
    notify_qr_order_changed(
        store_id=qr_order.store_id,
        order_id=qr_order.id,
        status=qr_order.status,
        reason='created',
    )

    return JsonResponse(
        {
            'detail': 'Đã gửi đơn. Vui lòng chờ quán xác nhận.',
            'qr_order_id': qr_order.id,
            'status': qr_order.status,
            'table': {'id': qr_order.table_id, 'name': qr_order.table.name, 'code': qr_order.table.code},
            'order': _serialize_qr_order(qr_order),
        },
        status=201,
    )


@csrf_exempt
@require_POST
def api_public_takeaway_orders(request):
    payload = _parse_json_request(request)
    if payload is None:
        return _json_error('Payload JSON không hợp lệ.', 400)

    tenant = Tenant.objects.filter(
        public_slug=(payload.get('tenant_slug') or '').strip().lower(),
        is_active=True,
    ).first()
    if not tenant:
        return _json_error('Không tìm thấy quán.', 404)
    if not _takeaway_ordering_enabled(tenant):
        return _json_error('Quán tạm ngưng nhận đặt món online.', 403)

    store_id = payload.get('store_id')
    store = None
    if str(store_id or '').isdigit():
        store = Store.objects.filter(id=int(store_id), tenant=tenant, is_active=True).first()
    if not store:
        return _json_error('Cửa hàng không hợp lệ.', 400)

    customer_name = (payload.get('customer_name') or '').strip()[:120]
    customer_phone = _normalize_phone(payload.get('customer_phone'))
    customer_note = (payload.get('note') or '').strip()[:255]
    if not customer_name:
        return _json_error('Vui lòng nhập tên người nhận.', 400)
    if not PHONE_RE.match(customer_phone):
        return _json_error('Số điện thoại không hợp lệ.', 400)

    client_ip = get_client_ip(request)
    rate_key = f'{tenant.id}:{client_ip}'
    if rate_limit.limited_until(
        rate_limit.SCOPE_TAKEAWAY_ORDER_IP,
        rate_key,
        limit=TAKEAWAY_ORDER_LIMIT_PER_IP,
        window=TAKEAWAY_ORDER_WINDOW,
    ):
        return _json_error('Bạn đặt quá nhiều đơn trong thời gian ngắn. Vui lòng thử lại sau ít phút.', 429)

    try:
        prepared_items = _prepare_order_items(tenant=tenant, store=store, raw_items=payload.get('items') or [])
    except ValueError as exc:
        return _json_error(str(exc), 400)

    with transaction.atomic():
        qr_order = QROrder.objects.create(
            tenant=tenant,
            store=store,
            table=None,
            order_type=QROrder.OrderType.TAKEAWAY,
            status=QROrder.Status.PENDING,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_note=customer_note,
            access_key=secrets.token_urlsafe(24),
            created_by_ip=client_ip or None,
        )
        _replace_qr_order_items(qr_order=qr_order, prepared_items=prepared_items)
    rate_limit.hit(rate_limit.SCOPE_TAKEAWAY_ORDER_IP, rate_key, window=TAKEAWAY_ORDER_WINDOW)

    qr_order = _reload_order(qr_order.pk)
    notify_qr_order_changed(
        store_id=qr_order.store_id,
        order_id=qr_order.id,
        status=qr_order.status,
        reason='created',
    )

    return JsonResponse(
        {
            'detail': 'Đã gửi đơn mang đi. Vui lòng chờ quán xác nhận.',
            'qr_order_id': qr_order.id,
            'access_key': qr_order.access_key,
            'status': qr_order.status,
            'order': _serialize_qr_order(qr_order),
        },
        status=201,
    )


@csrf_exempt
@require_http_methods(['GET', 'PATCH'])
def api_public_qr_order_detail(request, order_id):
    if request.method == 'GET':
        payload = request.GET
    else:
        payload = _parse_json_request(request)
        if payload is None:
            return _json_error('Payload JSON không hợp lệ.', 400)

    order_filters, _, error = _resolve_order_access(payload)
    if error:
        return error

    if request.method == 'GET':
        qr_order = get_object_or_404(
            QROrder.objects.select_related('table', 'store').prefetch_related('items', 'items__toppings'),
            id=order_id,
            **order_filters,
        )
        return JsonResponse({'order': _serialize_qr_order(qr_order)})

    customer_note = (payload.get('note') or '').strip()[:255]
    raw_items = payload.get('items') or []

    with transaction.atomic():
        qr_order = get_object_or_404(
            QROrder.objects.select_for_update().select_related('table', 'store', 'tenant'),
            id=order_id,
            **order_filters,
        )
        tenant = qr_order.tenant
        if not tenant.show_qr_order_feature:
            return _json_error('Tính năng gọi món QR đang tắt.', 403)
        if not tenant.show_topping_feature:
            for raw in raw_items:
                if 'topping_ids' in raw:
                    return _json_error('Tính năng topping đang tắt.', 400)

        if qr_order.status != QROrder.Status.PENDING:
            return _json_error('Quán đã xử lý đơn nên không thể sửa nữa.', 400)

        try:
            prepared_items = _prepare_order_items(tenant=tenant, store=qr_order.store, raw_items=raw_items)
        except ValueError as exc:
            return _json_error(str(exc), 400)

        qr_order.customer_note = customer_note
        qr_order.save(update_fields=['customer_note', 'updated_at'])
        _replace_qr_order_items(qr_order=qr_order, prepared_items=prepared_items)

    qr_order = _reload_order(qr_order.pk)
    notify_qr_order_changed(
        store_id=qr_order.store_id,
        order_id=qr_order.id,
        status=qr_order.status,
        reason='updated',
    )
    return JsonResponse({'detail': 'Đã cập nhật đơn.', 'order': _serialize_qr_order(qr_order)})


@csrf_exempt
@require_POST
def api_public_qr_order_cancel(request, order_id):
    payload = _parse_json_request(request)
    if payload is None:
        return _json_error('Payload JSON không hợp lệ.', 400)

    order_filters, _, error = _resolve_order_access(payload)
    if error:
        return error

    with transaction.atomic():
        qr_order = get_object_or_404(
            QROrder.objects.select_for_update().select_related('table', 'store'),
            id=order_id,
            **order_filters,
        )

        if qr_order.status == QROrder.Status.CANCELLED:
            return JsonResponse(
                {'detail': 'Đơn đã được hủy trước đó.', 'order': _serialize_qr_order(_reload_order(qr_order.pk))}
            )

        if qr_order.status != QROrder.Status.PENDING:
            return _json_error('Quán đã xử lý đơn nên không thể hủy.', 400)

        qr_order.status = QROrder.Status.CANCELLED
        qr_order.resolved_at = timezone.now()
        qr_order.save(update_fields=['status', 'resolved_at', 'updated_at'])

    qr_order = _reload_order(qr_order.pk)
    notify_qr_order_changed(
        store_id=qr_order.store_id,
        order_id=qr_order.id,
        status=qr_order.status,
        reason='cancelled',
    )

    return JsonResponse({'detail': 'Đã hủy đơn.', 'order': _serialize_qr_order(qr_order)})
