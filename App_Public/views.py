import json
from decimal import Decimal

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Min, Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from App_Catalog.models import Product, ProductTopping, ProductUnit
from App_Catalog.services import calc_toppings_total, resolve_product_topping_links
from App_Sales.models import DiningTable, QROrder, QROrderItem, QROrderItemTopping
from App_Sales.realtime import notify_qr_order_changed
from App_Sales.services import get_effective_unit_price
from App_Tenant.models import Store, Tenant


def _json_error(detail, status=400):
    return JsonResponse({'detail': detail}, status=status)


def _parse_json_request(request):
    try:
        return json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return None


def _qr_product_image_url(request, product):
    raw = product.get_catalog_image_url()
    if not raw:
        return 'https://placehold.co/600x600/png?text=Product'
    if raw.startswith('http'):
        return raw
    return request.build_absolute_uri(raw)


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
        'is_pending': order.status == QROrder.Status.PENDING,
        'can_edit': order.status == QROrder.Status.PENDING,
        'can_cancel': order.status == QROrder.Status.PENDING,
        'customer_note': order.customer_note,
        'created_at': order.created_at.isoformat(),
        'resolved_at': order.resolved_at.isoformat() if order.resolved_at else None,
        'time': timezone.localtime(order.created_at).strftime('%H:%M'),
        'table': {'id': order.table_id, 'name': order.table.name, 'code': order.table.code},
        'store': {'id': order.store_id, 'name': order.store.name},
        'total': float(total),
        'items': items_payload,
    }


def _prepare_qr_items_for_table(*, table, raw_items):
    if not raw_items:
        raise ValueError('Giỏ hàng QR trống.')

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
            product__tenant=table.tenant,
            product__is_active=True,
            is_active=True,
            product__store_links__store=table.store,
            product__store_links__is_available=True,
        ).first()
        if not unit:
            raise ValueError(f'Sản phẩm hoặc đơn vị không hợp lệ: {product_id}/{unit_id}')

        if unit.product.category_id:
            visible = unit.product.category.store_links.filter(store=table.store, is_visible=True).exists()
            if not visible:
                raise ValueError(f'Sản phẩm không hiển thị cho bàn này: {unit.product.name}')

        note = (raw.get('note') or '').strip()[:255]
        topping_links = resolve_product_topping_links(
            product=unit.product,
            topping_ids=raw.get('topping_ids'),
        )

        base_unit_price = get_effective_unit_price(unit=unit, store_id=table.store_id)
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


def _build_qr_products_payload(*, table, request):
    queryset = (
        Product.objects.filter(
            tenant=table.tenant,
            is_active=True,
            store_links__store=table.store,
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
        | Q(category__store_links__store=table.store, category__store_links__is_visible=True)
    )

    categories = [{'id': 'all', 'name': 'Tất cả'}]
    category_seen = set()
    products = []

    for product in queryset:
        if product.category_id and product.category_id not in category_seen:
            category_seen.add(product.category_id)
            categories.append({'id': str(product.category_id), 'name': product.category.name})

        units_payload = []
        for unit in product.units.all():
            unit_price = get_effective_unit_price(unit=unit, store_id=table.store_id)
            units_payload.append({'id': unit.id, 'name': unit.name, 'price': float(unit_price)})

        if not units_payload:
            continue

        toppings_payload = []
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
                'image': _qr_product_image_url(request, product),
                'category_id': str(product.category_id or ''),
                'category_name': product.category.name if product.category else 'Khác',
                'units': units_payload,
                'base_price': units_payload[0]['price'],
                'toppings': toppings_payload,
            }
        )

    return categories, products


def tenant_catalog(request, public_slug):
    tenant = get_object_or_404(Tenant, public_slug=public_slug, is_active=True)
    stores = Store.objects.filter(tenant=tenant, is_active=True).order_by('name')

    selected_store_id = (request.GET.get('store') or '').strip()
    selected_store = None
    if selected_store_id and selected_store_id.isdigit():
        selected_store = stores.filter(id=selected_store_id).first()
    if not selected_store:
        selected_store = stores.filter(is_default=True).first() or stores.first()

    products = []
    page_obj = None
    selected_query = (request.GET.get('q') or '').strip()

    if selected_store:
        base_qs = (
            Product.objects.filter(
                tenant=tenant,
                is_active=True,
                store_links__store=selected_store,
                store_links__is_available=True,
                units__is_active=True,
            )
            .select_related('category')
            .prefetch_related(
                Prefetch(
                    'units',
                    queryset=ProductUnit.objects.filter(is_active=True).order_by('display_order', 'id'),
                )
            )
            .annotate(min_price=Min('units__price'))
            .distinct()
            .order_by('name')
        )

        visible_category_ids = set(
            selected_store.category_links.filter(is_visible=True).values_list('category_id', flat=True)
        )
        if visible_category_ids:
            base_qs = base_qs.filter(category_id__in=visible_category_ids)

        if selected_query:
            base_qs = base_qs.filter(name__icontains=selected_query)

        paginator = Paginator(base_qs, 20)
        page_obj = paginator.get_page(request.GET.get('page'))
        products = list(page_obj.object_list)

    return render(
        request,
        'App_Public/catalog.html',
        {
            'tenant': tenant,
            'stores': stores,
            'selected_store': selected_store,
            'products': products,
            'page_obj': page_obj,
            'selected_query': selected_query,
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
            qr_error = 'QR không hợp lệ hoặc đã hết hiệu lực.'
        else:
            categories, products = _build_qr_products_payload(table=table, request=request)

    qr_bootstrap_data = {
        'tenant_slug': tenant.public_slug,
        'tenant_name': tenant.name,
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
            'qr_bootstrap_data': qr_bootstrap_data,
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

    raw_items = payload.get('items') or []
    try:
        prepared_items = _prepare_qr_items_for_table(table=table, raw_items=raw_items)
    except ValueError as exc:
        return _json_error(str(exc), 400)

    with transaction.atomic():
        qr_order = QROrder.objects.create(
            tenant=table.tenant,
            store=table.store,
            table=table,
            status=QROrder.Status.PENDING,
            customer_note=customer_note,
            created_by_ip=request.META.get('REMOTE_ADDR') or None,
        )
        _replace_qr_order_items(qr_order=qr_order, prepared_items=prepared_items)

    qr_order = (
        QROrder.objects.select_related('table', 'store')
        .prefetch_related('items', 'items__toppings')
        .get(pk=qr_order.pk)
    )
    notify_qr_order_changed(
        store_id=qr_order.store_id,
        order_id=qr_order.id,
        status=qr_order.status,
        reason='created',
    )

    return JsonResponse(
        {
            'detail': 'Đã ghi nhận đơn QR. Vui lòng chờ nhân viên duyệt.',
            'qr_order_id': qr_order.id,
            'status': qr_order.status,
            'table': {'id': qr_order.table_id, 'name': qr_order.table.name, 'code': qr_order.table.code},
            'order': _serialize_qr_order(qr_order),
        },
        status=201,
    )


@csrf_exempt
@require_http_methods(['GET', 'PATCH'])
def api_public_qr_order_detail(request, order_id):
    if request.method == 'GET':
        table_code = (request.GET.get('table_code') or '').strip().upper()
        token = (request.GET.get('token') or '').strip()
        payload = None
    else:
        payload = _parse_json_request(request)
        if payload is None:
            return _json_error('Payload JSON không hợp lệ.', 400)
        table_code = (payload.get('table_code') or '').strip().upper()
        token = (payload.get('token') or '').strip()

    if not table_code or not token:
        return _json_error('Thiếu table_code hoặc token.', 400)

    table = _get_table_by_credentials(table_code=table_code, token=token)
    if not table:
        return _json_error('QR không hợp lệ hoặc đã hết hiệu lực.', 403)

    if request.method == 'GET':
        qr_order = get_object_or_404(
            QROrder.objects.select_related('table', 'store').prefetch_related('items', 'items__toppings'),
            id=order_id,
            tenant=table.tenant,
            table=table,
        )
        return JsonResponse({'order': _serialize_qr_order(qr_order)})

    customer_note = (payload.get('note') or '').strip()[:255]
    raw_items = payload.get('items') or []

    try:
        prepared_items = _prepare_qr_items_for_table(table=table, raw_items=raw_items)
    except ValueError as exc:
        return _json_error(str(exc), 400)

    with transaction.atomic():
        qr_order = get_object_or_404(
            QROrder.objects.select_for_update().select_related('table', 'store').prefetch_related('items', 'items__toppings'),
            id=order_id,
            tenant=table.tenant,
            table=table,
        )

        if qr_order.status != QROrder.Status.PENDING:
            return _json_error('Chỉ có thể chỉnh sửa đơn đang chờ duyệt.', 400)

        qr_order.customer_note = customer_note
        qr_order.save(update_fields=['customer_note', 'updated_at'])
        _replace_qr_order_items(qr_order=qr_order, prepared_items=prepared_items)

    qr_order = (
        QROrder.objects.select_related('table', 'store')
        .prefetch_related('items', 'items__toppings')
        .get(pk=qr_order.pk)
    )
    notify_qr_order_changed(
        store_id=qr_order.store_id,
        order_id=qr_order.id,
        status=qr_order.status,
        reason='updated',
    )
    return JsonResponse({'detail': 'Đã cập nhật đơn QR.', 'order': _serialize_qr_order(qr_order)})


@csrf_exempt
@require_POST
def api_public_qr_order_cancel(request, order_id):
    payload = _parse_json_request(request)
    if payload is None:
        return _json_error('Payload JSON không hợp lệ.', 400)

    table_code = (payload.get('table_code') or '').strip().upper()
    token = (payload.get('token') or '').strip()

    if not table_code or not token:
        return _json_error('Thiếu table_code hoặc token.', 400)

    table = _get_table_by_credentials(table_code=table_code, token=token)
    if not table:
        return _json_error('QR không hợp lệ hoặc đã hết hiệu lực.', 403)

    with transaction.atomic():
        qr_order = get_object_or_404(
            QROrder.objects.select_for_update().select_related('table', 'store').prefetch_related('items', 'items__toppings'),
            id=order_id,
            tenant=table.tenant,
            table=table,
        )

        if qr_order.status == QROrder.Status.CANCELLED:
            return JsonResponse({'detail': 'Đơn đã được hủy trước đó.', 'order': _serialize_qr_order(qr_order)})

        if qr_order.status != QROrder.Status.PENDING:
            return _json_error('Đơn đã được xử lý nên không thể hủy.', 400)

        qr_order.status = QROrder.Status.CANCELLED
        qr_order.resolved_at = timezone.now()
        qr_order.save(update_fields=['status', 'resolved_at', 'updated_at'])

    qr_order = (
        QROrder.objects.select_related('table', 'store')
        .prefetch_related('items', 'items__toppings')
        .get(pk=qr_order.pk)
    )
    notify_qr_order_changed(
        store_id=qr_order.store_id,
        order_id=qr_order.id,
        status=qr_order.status,
        reason='cancelled',
    )

    return JsonResponse({'detail': 'Đã hủy đơn QR.', 'order': _serialize_qr_order(qr_order)})
