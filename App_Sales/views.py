import json
from datetime import datetime, time
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Prefetch, Q, Sum
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from App_Accounts.permissions import staff_or_manager_required
from App_Catalog.models import Product, ProductTopping, ProductUnit
from App_Catalog.services import calc_toppings_total, parse_topping_ids, resolve_product_topping_links
from App_Sales.models import (
    Customer,
    DiningTable,
    Order,
    OrderItem,
    OrderItemTopping,
    Promotion,
    QROrder,
    QROrderItemTopping,
    TableCartItem,
    TableCartItemTopping,
)
from App_Sales.realtime import notify_qr_order_changed
from App_Sales.services import (
    calculate_order_totals,
    calculate_points_for_amount,
    calculate_promotion_discount,
    get_customer_tier_setting,
    get_accessible_store_or_default,
    get_available_promotions,
    get_effective_unit_price,
    recompute_customer_stats,
    resolve_customer_for_checkout,
    resolve_promotion_for_checkout,
)
from App_Tenant.services import get_user_accessible_stores


def _json_error(detail, status=400):
    return JsonResponse({'detail': detail}, status=status)


ORDERS_TODAY_PER_PAGE = 20


def _orders_today_query_string(request):
    q = request.GET.copy()
    q.pop('page', None)
    return q.urlencode()


def _pos_product_image_url(request, product):
    raw = product.get_catalog_image_url()
    if not raw:
        return 'https://placehold.co/600x600/png?text=Product'
    if raw.startswith('http'):
        return raw
    return request.build_absolute_uri(raw)


def _parse_json_request(request):
    try:
        return json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return None


def _parse_decimal(raw_value, *, default='0', field='value'):
    try:
        return Decimal(str(raw_value if raw_value is not None else default))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f'{field} không hợp lệ.')


def _serialize_topping_rows(topping_rows):
    return [
        {
            'id': row.topping_id,
            'name': row.snapshot_topping_name,
            'price': float(row.snapshot_price),
        }
        for row in topping_rows
    ]


def _serialize_table_cart_item(item: TableCartItem):
    toppings = list(item.toppings.all().order_by('id'))
    return {
        'id': item.id,
        'cart_id': f'table-{item.id}',
        'table_item_id': item.id,
        'product_id': item.product_id,
        'unit_id': item.unit_id,
        'name': item.snapshot_product_name,
        'size': item.snapshot_unit_name,
        'price': float(item.unit_price_snapshot),
        'qty': item.quantity,
        'note': item.note,
        'source': item.source,
        'line_total': float(item.unit_price_snapshot * item.quantity),
        'toppings': _serialize_topping_rows(toppings),
        'topping_ids': [row.topping_id for row in toppings if row.topping_id],
    }


def _table_cart_summary(table: DiningTable):
    summary = TableCartItem.objects.filter(table=table).aggregate(
        item_count=Coalesce(Sum('quantity'), 0),
        total_amount=Coalesce(
            Sum(
                ExpressionWrapper(
                    F('quantity') * F('unit_price_snapshot'),
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                )
            ),
            Decimal('0'),
        ),
    )
    return {
        'item_count': int(summary['item_count'] or 0),
        'total_amount': float(summary['total_amount'] or Decimal('0')),
    }


def _get_accessible_table_or_403(user, table_id):
    table = get_object_or_404(
        DiningTable.objects.select_related('store', 'tenant').filter(tenant=user.tenant, is_active=True),
        id=table_id,
    )
    if not get_user_accessible_stores(user).filter(id=table.store_id).exists():
        return None
    return table


def _resolve_product_unit_for_store(*, tenant, store, product_id, unit_id):
    try:
        unit = ProductUnit.objects.select_related('product').get(
            id=unit_id,
            product_id=product_id,
            product__tenant=tenant,
            product__is_active=True,
            is_active=True,
            product__store_links__store=store,
            product__store_links__is_available=True,
        )
    except ProductUnit.DoesNotExist:
        return None

    if unit.product.category_id:
        visible = unit.product.category.store_links.filter(store=store, is_visible=True).exists()
        if not visible:
            return None
    return unit


def _resolve_topping_links_for_unit(*, unit, raw_topping_ids):
    try:
        topping_ids = parse_topping_ids(raw_topping_ids)
    except ValueError as exc:
        raise ValueError(str(exc))
    if not topping_ids:
        return []
    try:
        return resolve_product_topping_links(product=unit.product, topping_ids=topping_ids)
    except ValueError as exc:
        raise ValueError(str(exc))


def _snapshot_rows_from_product_toppings(links):
    rows = []
    for link in sorted(links, key=lambda row: (row.display_order, row.id)):
        rows.append(
            {
                'topping_id': link.topping_id,
                'name': link.topping.name,
                'price': (getattr(link.topping, 'price', None) or link.price),
            }
        )
    return rows


def _serialize_customer(customer: Customer):
    tier_setting = get_customer_tier_setting(tenant=customer.tenant, tier=customer.tier)
    return {
        'id': customer.id,
        'name': customer.name,
        'phone': customer.phone,
        'email': customer.email,
        'note': customer.note,
        'tier': customer.tier,
        'tier_label': customer.get_tier_display(),
        'tier_min_total_spent': float(tier_setting.min_total_spent),
        'tier_discount_percent': float(tier_setting.discount_percent),
        'points_balance': customer.points_balance,
        'total_spent': float(customer.total_spent),
        'last_order_at': timezone.localtime(customer.last_order_at).strftime('%d/%m/%Y %H:%M') if customer.last_order_at else '',
    }


def _serialize_promotion(promotion: Promotion, *, subtotal: Decimal):
    discount_amount = calculate_promotion_discount(promotion=promotion, subtotal=subtotal)
    return {
        'id': promotion.id,
        'name': promotion.name,
        'discount_type': promotion.discount_type,
        'discount_type_label': promotion.get_discount_type_display(),
        'discount_value': float(promotion.discount_value),
        'min_order_amount': float(promotion.min_order_amount),
        'max_discount_amount': float(promotion.max_discount_amount) if promotion.max_discount_amount is not None else None,
        'discount_amount': float(discount_amount),
    }


def _snapshot_promotion_fields(promotion: Promotion | None):
    if not promotion:
        return {
            'promotion_snapshot_name': '',
            'promotion_snapshot_type': '',
            'promotion_snapshot_value': Decimal('0'),
        }
    return {
        'promotion_snapshot_name': promotion.name,
        'promotion_snapshot_type': promotion.discount_type,
        'promotion_snapshot_value': promotion.discount_value,
    }


def _snapshot_tier_discount_fields(totals):
    return {
        'discount_source': totals['discount_source'],
        'tier_snapshot': totals.get('customer_tier') or '',
        'tier_discount_percent': totals.get('tier_discount_percent') or Decimal('0'),
        'tier_discount_amount': totals.get('tier_discount_amount') or Decimal('0'),
    }


def _snapshot_rows_from_qr_item_toppings(qr_item):
    rows = []
    for row in qr_item.toppings.all().order_by('id'):
        rows.append(
            {
                'topping_id': row.topping_id,
                'name': row.snapshot_topping_name,
                'price': row.snapshot_price,
            }
        )
    return rows


def _topping_signature(snapshot_rows):
    return tuple(sorted((row.get('topping_id') or 0, row['name'], str(row['price'])) for row in snapshot_rows))


def _table_item_topping_signature(table_item):
    return _topping_signature(
        [
            {
                'topping_id': row.topping_id,
                'name': row.snapshot_topping_name,
                'price': row.snapshot_price,
            }
            for row in table_item.toppings.all().order_by('id')
        ]
    )


def _replace_table_item_toppings(*, table_item, snapshot_rows):
    table_item.toppings.all().delete()
    TableCartItemTopping.objects.bulk_create(
        [
            TableCartItemTopping(
                table_cart_item=table_item,
                topping_id=row.get('topping_id'),
                snapshot_topping_name=row['name'],
                snapshot_price=row['price'],
            )
            for row in snapshot_rows
        ]
    )


def _upsert_table_cart_item(
    *,
    tenant,
    store,
    table,
    unit,
    quantity,
    base_unit_price,
    snapshot_toppings,
    note='',
    source=TableCartItem.Source.STAFF,
    qr_order=None,
):
    note = (note or '').strip()[:255]
    quantity = int(quantity)
    if quantity <= 0:
        raise ValueError('Số lượng phải lớn hơn 0.')

    topping_total = Decimal('0')
    for topping_row in snapshot_toppings:
        topping_total += topping_row['price']
    effective_unit_price = base_unit_price + topping_total

    candidates = (
        TableCartItem.objects.filter(
            tenant=tenant,
            store=store,
            table=table,
            unit=unit,
            note=note,
            source=source,
        )
        .prefetch_related('toppings')
        .order_by('id')
    )
    snapshot_signature = _topping_signature(snapshot_toppings)
    existing = None
    for candidate in candidates:
        if _table_item_topping_signature(candidate) == snapshot_signature:
            existing = candidate
            break

    if existing:
        existing.quantity += quantity
        if qr_order and not existing.qr_order_id:
            existing.qr_order = qr_order
        existing.unit_price_snapshot = effective_unit_price
        existing.save(update_fields=['quantity', 'qr_order', 'unit_price_snapshot', 'updated_at'])
        return existing

    created = TableCartItem.objects.create(
        tenant=tenant,
        store=store,
        table=table,
        unit=unit,
        product=unit.product,
        snapshot_product_name=unit.product.name,
        snapshot_unit_name=unit.name,
        unit_price_snapshot=effective_unit_price,
        quantity=quantity,
        note=note,
        source=source,
        qr_order=qr_order,
    )
    _replace_table_item_toppings(table_item=created, snapshot_rows=snapshot_toppings)
    return created


@login_required
@staff_or_manager_required
def pos_page(request):
    stores = list(get_user_accessible_stores(request.user))
    default_store = get_accessible_store_or_default(request.user)
    return render(
        request,
        'App_Sales/index.html',
        {
            'stores': stores,
            'default_store_id': default_store.id if default_store else None,
            'default_store_name': default_store.name if default_store else '',
        },
    )


@login_required
@staff_or_manager_required
@require_GET
def orders_today_page(request):
    user = request.user
    stores_qs = get_user_accessible_stores(user)
    stores = list(stores_qs)

    today = timezone.localdate()
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(today, time.min), tz)
    end_dt = timezone.make_aware(datetime.combine(today, time.max), tz)

    selected_store_id = (request.GET.get('store_id') or '').strip()
    orders = (
        Order.objects.filter(
            tenant=user.tenant,
            store__in=stores_qs,
            status=Order.Status.COMPLETED,
            created_at__gte=start_dt,
            created_at__lte=end_dt,
        )
        .select_related('store', 'cashier')
        .order_by('-created_at')
    )

    selected_store = None
    if selected_store_id.isdigit():
        selected_store = stores_qs.filter(id=int(selected_store_id)).first()
        if selected_store:
            orders = orders.filter(store=selected_store)

    total_orders = orders.count()
    total_revenue = orders.aggregate(total=Coalesce(Sum('total_amount'), Decimal('0')))['total'] or Decimal('0')
    avg_order = (total_revenue / total_orders) if total_orders else Decimal('0')
    orders_page = Paginator(orders, ORDERS_TODAY_PER_PAGE).get_page(request.GET.get('page'))

    return render(
        request,
        'App_Sales/orders_today.html',
        {
            'stores': stores,
            'selected_store_id': selected_store.id if selected_store else '',
            'today': today,
            'orders_page': orders_page,
            'orders_query_string': _orders_today_query_string(request),
            'total_orders': total_orders,
            'total_revenue': total_revenue,
            'avg_order': avg_order,
        },
    )


@login_required
@staff_or_manager_required
@require_GET
def api_products(request):
    user = request.user
    if not user.tenant_id:
        return _json_error('Tài khoản chưa được gán doanh nghiệp.', 400)

    store = get_accessible_store_or_default(user, request.GET.get('store_id'))
    if not store:
        return _json_error('Store không hợp lệ hoặc không có quyền truy cập.', 403)

    queryset = (
        Product.objects.filter(
            tenant=user.tenant,
            is_active=True,
            store_links__store=store,
            store_links__is_available=True,
        )
        .select_related('category')
        .prefetch_related(
            Prefetch('units', queryset=ProductUnit.objects.filter(is_active=True).order_by('display_order', 'id')),
            Prefetch(
                'topping_links',
                queryset=ProductTopping.objects.select_related('topping').filter(
                    is_active=True,
                    topping__is_active=True,
                ).order_by('display_order', 'id'),
            ),
        )
        .distinct()
    )

    queryset = queryset.filter(
        Q(category__isnull=True)
        | Q(category__store_links__store=store, category__store_links__is_visible=True)
    )

    q = (request.GET.get('q') or '').strip()
    if q:
        queryset = queryset.filter(name__icontains=q)

    category_id = request.GET.get('category')
    if category_id and category_id.isdigit():
        queryset = queryset.filter(category_id=category_id)

    products = []
    categories = [{'id': '', 'name': 'Tất cả'}]
    category_seen = set()

    for product in queryset.order_by('name'):
        if product.category_id and product.category_id not in category_seen:
            category_seen.add(product.category_id)
            categories.append({'id': str(product.category_id), 'name': product.category.name})

        units_payload = []
        for unit in product.units.all():
            unit_price = get_effective_unit_price(unit=unit, store_id=store.id)
            units_payload.append(
                {
                    'id': unit.id,
                    'name': unit.name,
                    'price': float(unit_price),
                }
            )

        if not units_payload:
            continue

        toppings_payload = []
        for topping_link in product.topping_links.all():
            toppings_payload.append(
                {
                    'id': topping_link.topping_id,
                    'name': topping_link.topping.name,
                    'price': float((getattr(topping_link.topping, 'price', None) or topping_link.price)),
                }
            )

        products.append(
            {
                'id': product.id,
                'name': product.name,
                'description': (product.description or '').strip(),
                'category': product.category.name if product.category else 'Khác',
                'category_id': str(product.category_id or ''),
                'image': _pos_product_image_url(request, product),
                'units': units_payload,
                'base_price': units_payload[0]['price'],
                'toppings': toppings_payload,
            }
        )

    payment_qr_url = None
    if store.payment_qr:
        payment_qr_url = request.build_absolute_uri(store.payment_qr.url)

    return JsonResponse(
        {
            'store': {
                'id': store.id,
                'name': store.name,
                'payment_qr_url': payment_qr_url,
                'payment_bank_name': store.payment_bank_name or '',
                'payment_account_name': store.payment_account_name or '',
                'payment_account_number': store.payment_account_number or '',
            },
            'categories': categories,
            'products': products,
        }
    )


@login_required
@staff_or_manager_required
@require_http_methods(['GET', 'POST'])
def api_customers(request):
    user = request.user
    if not user.tenant_id:
        return _json_error('Tài khoản chưa được gán doanh nghiệp.', 400)

    if request.method == 'GET':
        q = (request.GET.get('q') or '').strip()
        has_customers = Customer.objects.filter(tenant=user.tenant).exists()
        customers = Customer.objects.filter(tenant=user.tenant, is_active=True)
        if q:
            customers = customers.filter(Q(name__icontains=q) | Q(phone__icontains=q))
        rows = [_serialize_customer(row) for row in customers.order_by('name', 'id')[:12]]
        return JsonResponse({'customers': rows, 'has_customers': has_customers})

    payload = _parse_json_request(request)
    if payload is None:
        return _json_error('Payload JSON không hợp lệ.', 400)

    name = (payload.get('name') or '').strip()
    phone = (payload.get('phone') or '').strip()
    if not name:
        return _json_error('Vui lòng nhập tên khách hàng.', 400)
    if not phone:
        return _json_error('Vui lòng nhập số điện thoại khách hàng.', 400)

    existing = Customer.objects.filter(tenant=user.tenant, phone=phone).first()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            existing.save(update_fields=['is_active', 'updated_at'])
        return JsonResponse({'customer': _serialize_customer(existing), 'detail': 'Khách hàng đã tồn tại.'})

    customer = Customer(
        tenant=user.tenant,
        name=name,
        phone=phone,
        email=(payload.get('email') or '').strip(),
        note=(payload.get('note') or '').strip()[:500],
    )
    try:
        customer.save()
    except ValidationError as exc:
        return _json_error('; '.join(exc.messages), 400)
    return JsonResponse({'customer': _serialize_customer(customer)}, status=201)


@login_required
@staff_or_manager_required
@require_GET
def api_promotions(request):
    user = request.user
    if not user.tenant_id:
        return _json_error('Tài khoản chưa được gán doanh nghiệp.', 400)

    store = get_accessible_store_or_default(user, request.GET.get('store_id'))
    if not store:
        return _json_error('Store không hợp lệ hoặc không có quyền truy cập.', 403)

    try:
        subtotal = _parse_decimal(request.GET.get('subtotal', '0'), field='subtotal')
    except ValueError as exc:
        return _json_error(str(exc), 400)
    if subtotal < 0:
        return _json_error('subtotal không được âm.', 400)

    has_promotions = Promotion.objects.filter(tenant=user.tenant).exists()
    promotions = get_available_promotions(tenant=user.tenant, store=store, subtotal=subtotal)
    return JsonResponse(
        {
            'promotions': [_serialize_promotion(row, subtotal=subtotal) for row in promotions[:30]],
            'has_promotions': has_promotions,
        }
    )


@login_required
@staff_or_manager_required
@require_POST
def api_checkout(request):
    user = request.user
    if not user.tenant_id:
        return _json_error('Tài khoản chưa được gán doanh nghiệp.', 400)

    payload = _parse_json_request(request)
    if payload is None:
        return _json_error('Payload JSON không hợp lệ.', 400)

    store = get_accessible_store_or_default(user, payload.get('store_id'))
    if not store:
        return _json_error('Store không hợp lệ hoặc không có quyền truy cập.', 403)

    items = payload.get('items') or []
    if not items:
        return _json_error('Giỏ hàng trống.', 400)

    payment_method = payload.get('payment_method') or Order.PaymentMethod.CASH
    if payment_method not in {Order.PaymentMethod.CASH, Order.PaymentMethod.CARD}:
        return _json_error('Phương thức thanh toán không hợp lệ.', 400)

    try:
        tax_rate = _parse_decimal(payload.get('tax_rate', '0'), field='tax_rate')
    except ValueError as exc:
        return _json_error(str(exc), 400)

    if tax_rate < 0:
        return _json_error('tax_rate không được âm.', 400)

    try:
        customer_paid = _parse_decimal(payload.get('customer_paid', '0'), field='customer_paid')
    except ValueError as exc:
        return _json_error(str(exc), 400)

    with transaction.atomic():
        prepared_items = []
        subtotal = Decimal('0')

        for item in items:
            product_id = item.get('product_id')
            unit_id = item.get('unit_id')
            try:
                quantity = int(item.get('quantity', 0))
            except (TypeError, ValueError):
                return _json_error('Số lượng không hợp lệ.', 400)
            note = (item.get('note') or '').strip()[:255]

            if quantity <= 0:
                return _json_error('Số lượng phải lớn hơn 0.', 400)

            unit = _resolve_product_unit_for_store(
                tenant=user.tenant,
                store=store,
                product_id=product_id,
                unit_id=unit_id,
            )
            if not unit:
                return _json_error(f'Sản phẩm hoặc đơn vị không hợp lệ: {product_id}/{unit_id}', 400)

            try:
                topping_links = _resolve_topping_links_for_unit(
                    unit=unit,
                    raw_topping_ids=item.get('topping_ids'),
                )
            except ValueError as exc:
                return _json_error(str(exc), 400)

            base_price = get_effective_unit_price(unit=unit, store_id=store.id)
            topping_total = calc_toppings_total(topping_links)
            effective_unit_price = base_price + topping_total
            line_total = effective_unit_price * quantity
            subtotal += line_total
            prepared_items.append(
                {
                    'product': unit.product,
                    'unit': unit,
                    'quantity': quantity,
                    'note': note,
                    'unit_price': effective_unit_price,
                    'line_total': line_total,
                    'snapshot_toppings': _snapshot_rows_from_product_toppings(topping_links),
                }
            )

        customer_id = payload.get('customer_id')
        customer = resolve_customer_for_checkout(tenant=user.tenant, customer_id=customer_id)
        if customer_id and not customer:
            return _json_error('Khách hàng không hợp lệ hoặc đã ngưng hoạt động.', 400)

        promotion_id = payload.get('promotion_id')
        promotion = resolve_promotion_for_checkout(
            tenant=user.tenant,
            store=store,
            promotion_id=promotion_id,
            subtotal=subtotal,
        )
        if promotion_id and not promotion:
            return _json_error('Khuyến mãi không hợp lệ hoặc không đủ điều kiện áp dụng.', 400)

        totals = calculate_order_totals(subtotal=subtotal, tax_rate=tax_rate, promotion=promotion, customer=customer)
        discount_amount = totals['discount_amount']
        tier_discount_amount = totals['tier_discount_amount']
        tier_discount_percent = totals['tier_discount_percent']
        discount_source = totals['discount_source']
        tax_amount = totals['tax_amount']
        total_amount = totals['total_amount']

        if payment_method == Order.PaymentMethod.CASH and customer_paid < total_amount:
            return _json_error('Khách đưa chưa đủ tiền.', 400)

        if payment_method == Order.PaymentMethod.CARD and customer_paid <= 0:
            customer_paid = total_amount

        change_amount = customer_paid - total_amount

        order = Order.objects.create(
            tenant=user.tenant,
            store=store,
            cashier=user,
            customer=customer,
            promotion=promotion,
            payment_method=payment_method,
            sale_channel=Order.SaleChannel.TAKEAWAY,
            subtotal=subtotal,
            discount_amount=discount_amount,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            total_amount=total_amount,
            customer_paid=customer_paid,
            change_amount=change_amount,
            **_snapshot_promotion_fields(promotion),
            **_snapshot_tier_discount_fields(totals),
        )

        for item in prepared_items:
            order_item = OrderItem.objects.create(
                order=order,
                product=item['product'],
                unit=item['unit'],
                snapshot_product_name=item['product'].name,
                snapshot_unit_name=item['unit'].name,
                unit_price=item['unit_price'],
                quantity=item['quantity'],
                note=item['note'],
                line_total=item['line_total'],
            )
            OrderItemTopping.objects.bulk_create(
                [
                    OrderItemTopping(
                        order_item=order_item,
                        topping_id=row.get('topping_id'),
                        snapshot_topping_name=row['name'],
                        snapshot_price=row['price'],
                    )
                    for row in item['snapshot_toppings']
                ]
            )

        points_earned = calculate_points_for_amount(total_amount) if customer else 0
        if customer:
            customer = recompute_customer_stats(customer)

    return JsonResponse(
        {
            'order_id': order.id,
            'order_code': order.order_code,
            'subtotal': float(subtotal),
            'discount_amount': float(discount_amount),
            'discount_source': discount_source,
            'tier_discount_amount': float(tier_discount_amount),
            'tier_discount_percent': float(tier_discount_percent),
            'tax_amount': float(tax_amount),
            'total_amount': float(total_amount),
            'customer_paid': float(customer_paid),
            'change_amount': float(change_amount),
            'points_earned': points_earned,
            'customer_tier': customer.tier if customer else '',
        },
        status=201,
    )


@login_required
@staff_or_manager_required
@require_GET
def api_tables(request):
    user = request.user
    store = get_accessible_store_or_default(user, request.GET.get('store_id'))
    if not store:
        return _json_error('Store không hợp lệ hoặc không có quyền truy cập.', 403)

    tables_qs = DiningTable.objects.filter(tenant=user.tenant, store=store, is_active=True).order_by('display_order', 'id')

    cart_aggs = {
        row['table_id']: {
            'item_count': int(row['item_count'] or 0),
            'total_amount': row['total_amount'] or Decimal('0'),
        }
        for row in TableCartItem.objects.filter(table__in=tables_qs)
        .values('table_id')
        .annotate(
            item_count=Coalesce(Sum('quantity'), 0),
            total_amount=Coalesce(
                Sum(
                    ExpressionWrapper(
                        F('quantity') * F('unit_price_snapshot'),
                        output_field=DecimalField(max_digits=14, decimal_places=2),
                    )
                ),
                Decimal('0'),
            ),
        )
    }

    pending_aggs = {
        row['table_id']: int(row['pending_count'])
        for row in QROrder.objects.filter(table__in=tables_qs, status=QROrder.Status.PENDING)
        .values('table_id')
        .annotate(pending_count=Count('id'))
    }

    tables = []
    for table in tables_qs:
        cart_info = cart_aggs.get(table.id, {'item_count': 0, 'total_amount': Decimal('0')})
        pending_count = pending_aggs.get(table.id, 0)
        item_count = int(cart_info['item_count'])
        total_amount = Decimal(cart_info['total_amount'])

        if pending_count > 0:
            status = 'pending'
        elif item_count > 0:
            status = 'occupied'
        else:
            status = 'empty'

        tables.append(
            {
                'id': table.id,
                'code': table.code,
                'name': table.name,
                'status': status,
                'pending_count': pending_count,
                'item_count': item_count,
                'total_amount': float(total_amount),
            }
        )

    return JsonResponse({'store': {'id': store.id, 'name': store.name}, 'tables': tables})


@login_required
@staff_or_manager_required
@require_GET
def api_table_cart(request, table_id):
    user = request.user
    table = _get_accessible_table_or_403(user, table_id)
    if not table:
        return _json_error('Không có quyền truy cập bàn này.', 403)

    items = list(
        TableCartItem.objects.filter(table=table)
        .select_related('product', 'unit')
        .prefetch_related('toppings')
        .order_by('created_at', 'id')
    )
    summary = _table_cart_summary(table)

    return JsonResponse(
        {
            'table': {'id': table.id, 'name': table.name, 'code': table.code},
            'items': [_serialize_table_cart_item(item) for item in items],
            'summary': summary,
        }
    )


@login_required
@staff_or_manager_required
@require_POST
def api_table_cart_add(request, table_id):
    user = request.user
    table = _get_accessible_table_or_403(user, table_id)
    if not table:
        return _json_error('Không có quyền truy cập bàn này.', 403)

    payload = _parse_json_request(request)
    if payload is None:
        return _json_error('Payload JSON không hợp lệ.', 400)

    product_id = payload.get('product_id')
    unit_id = payload.get('unit_id')
    try:
        quantity = int(payload.get('quantity', 0))
    except (TypeError, ValueError):
        return _json_error('Số lượng không hợp lệ.', 400)

    note = (payload.get('note') or '').strip()[:255]
    if quantity <= 0:
        return _json_error('Số lượng phải lớn hơn 0.', 400)

    unit = _resolve_product_unit_for_store(
        tenant=user.tenant,
        store=table.store,
        product_id=product_id,
        unit_id=unit_id,
    )
    if not unit:
        return _json_error('Sản phẩm hoặc đơn vị không hợp lệ.', 400)

    try:
        topping_links = _resolve_topping_links_for_unit(
            unit=unit,
            raw_topping_ids=payload.get('topping_ids'),
        )
    except ValueError as exc:
        return _json_error(str(exc), 400)

    base_unit_price = get_effective_unit_price(unit=unit, store_id=table.store.id)

    with transaction.atomic():
        item = _upsert_table_cart_item(
            tenant=user.tenant,
            store=table.store,
            table=table,
            unit=unit,
            quantity=quantity,
            base_unit_price=base_unit_price,
            snapshot_toppings=_snapshot_rows_from_product_toppings(topping_links),
            note=note,
            source=TableCartItem.Source.STAFF,
        )

    return JsonResponse(
        {
            'item': _serialize_table_cart_item(item),
            'summary': _table_cart_summary(table),
        },
        status=201,
    )


@login_required
@staff_or_manager_required
@require_POST
def api_table_import_takeaway(request, table_id):
    user = request.user
    table = _get_accessible_table_or_403(user, table_id)
    if not table:
        return _json_error('Không có quyền truy cập bàn này.', 403)

    payload = _parse_json_request(request)
    if payload is None:
        return _json_error('Payload JSON không hợp lệ.', 400)

    raw_items = payload.get('items') or []
    if not raw_items:
        return _json_error('Không có món để lưu vào bàn.', 400)

    prepared_rows = []
    for row in raw_items:
        product_id = row.get('product_id')
        unit_id = row.get('unit_id')
        try:
            quantity = int(row.get('quantity', 0))
        except (TypeError, ValueError):
            return _json_error('Số lượng không hợp lệ.', 400)
        note = (row.get('note') or '').strip()[:255]
        if quantity <= 0:
            return _json_error('Số lượng phải lớn hơn 0.', 400)

        unit = _resolve_product_unit_for_store(
            tenant=user.tenant,
            store=table.store,
            product_id=product_id,
            unit_id=unit_id,
        )
        if not unit:
            return _json_error('Sản phẩm hoặc đơn vị không hợp lệ.', 400)
        try:
            topping_links = _resolve_topping_links_for_unit(
                unit=unit,
                raw_topping_ids=row.get('topping_ids'),
            )
        except ValueError as exc:
            return _json_error(str(exc), 400)

        prepared_rows.append(
            {
                'unit': unit,
                'quantity': quantity,
                'note': note,
                'base_unit_price': get_effective_unit_price(unit=unit, store_id=table.store.id),
                'snapshot_toppings': _snapshot_rows_from_product_toppings(topping_links),
            }
        )

    with transaction.atomic():
        for row in prepared_rows:
            _upsert_table_cart_item(
                tenant=user.tenant,
                store=table.store,
                table=table,
                unit=row['unit'],
                quantity=row['quantity'],
                base_unit_price=row['base_unit_price'],
                snapshot_toppings=row['snapshot_toppings'],
                note=row['note'],
                source=TableCartItem.Source.STAFF,
            )

    return JsonResponse(
        {
            'detail': 'Đã lưu giỏ mang về vào bàn.',
            'summary': _table_cart_summary(table),
        },
        status=201,
    )


@login_required
@staff_or_manager_required
@require_POST
def api_table_cart_move_to(request, table_id):
    user = request.user
    from_table = _get_accessible_table_or_403(user, table_id)
    if not from_table:
        return _json_error('Không có quyền truy cập bàn này.', 403)

    payload = _parse_json_request(request)
    if payload is None:
        return _json_error('Payload JSON không hợp lệ.', 400)

    to_table_id = payload.get('to_table_id')
    try:
        to_table_id = int(to_table_id)
    except (TypeError, ValueError):
        return _json_error('to_table_id không hợp lệ.', 400)
    if to_table_id == from_table.id:
        return _json_error('Bàn đích phải khác bàn hiện tại.', 400)

    to_table = _get_accessible_table_or_403(user, to_table_id)
    if not to_table:
        return _json_error('Không có quyền truy cập bàn đích.', 403)
    if to_table.store_id != from_table.store_id:
        return _json_error('Không thể chuyển giỏ giữa hai cửa hàng khác nhau.', 400)

    items = list(
        TableCartItem.objects.filter(table=from_table)
        .select_related('unit', 'product')
        .prefetch_related('toppings')
        .order_by('id')
    )
    if not items:
        return JsonResponse(
            {
                'detail': 'Giỏ bàn đang trống.',
                'from_table': {'id': from_table.id, 'name': from_table.name},
                'to_table': {'id': to_table.id, 'name': to_table.name},
                'summary': _table_cart_summary(to_table),
            }
        )

    if any(not item.unit_id for item in items):
        return _json_error('Item không hợp lệ (thiếu unit).', 400)

    with transaction.atomic():
        for item in items:
            snapshot_toppings = [
                {
                    'topping_id': row.topping_id,
                    'name': row.snapshot_topping_name,
                    'price': row.snapshot_price,
                }
                for row in item.toppings.all().order_by('id')
            ]
            base_unit_price = get_effective_unit_price(unit=item.unit, store_id=to_table.store_id)
            _upsert_table_cart_item(
                tenant=user.tenant,
                store=to_table.store,
                table=to_table,
                unit=item.unit,
                quantity=item.quantity,
                base_unit_price=base_unit_price,
                snapshot_toppings=snapshot_toppings,
                note=item.note,
                source=item.source,
                qr_order=item.qr_order if item.qr_order_id else None,
            )

        TableCartItem.objects.filter(table=from_table).delete()

    return JsonResponse(
        {
            'detail': 'Đã chuyển giỏ sang bàn khác.',
            'from_table': {'id': from_table.id, 'name': from_table.name},
            'to_table': {'id': to_table.id, 'name': to_table.name},
            'summary': _table_cart_summary(to_table),
        }
    )


@login_required
@staff_or_manager_required
@require_http_methods(['PATCH', 'DELETE'])
def api_table_cart_item(request, table_id, item_id):
    user = request.user
    table = _get_accessible_table_or_403(user, table_id)
    if not table:
        return _json_error('Không có quyền truy cập bàn này.', 403)

    item = get_object_or_404(
        TableCartItem.objects.select_related('table', 'unit').prefetch_related('toppings'),
        id=item_id,
        table=table,
    )

    if request.method == 'DELETE':
        item.delete()
        return JsonResponse({'detail': 'Đã xóa item khỏi bàn.', 'summary': _table_cart_summary(table)})

    payload = _parse_json_request(request)
    if payload is None:
        return _json_error('Payload JSON không hợp lệ.', 400)

    note = payload.get('note')
    quantity = payload.get('quantity')
    topping_ids = payload.get('topping_ids') if 'topping_ids' in payload else None

    if note is not None:
        item.note = str(note).strip()[:255]

    if quantity is not None:
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return _json_error('Số lượng không hợp lệ.', 400)

        if quantity <= 0:
            item.delete()
            return JsonResponse({'detail': 'Đã xóa item khỏi bàn.', 'summary': _table_cart_summary(table)})
        item.quantity = quantity

    update_fields = ['note', 'quantity', 'updated_at']
    if topping_ids is not None:
        if not item.unit_id:
            return _json_error('Không thể cập nhật topping cho item không có unit.', 400)
        try:
            topping_links = _resolve_topping_links_for_unit(
                unit=item.unit,
                raw_topping_ids=topping_ids,
            )
        except ValueError as exc:
            return _json_error(str(exc), 400)
        base_unit_price = get_effective_unit_price(unit=item.unit, store_id=table.store_id)
        item.unit_price_snapshot = base_unit_price + calc_toppings_total(topping_links)
        update_fields.append('unit_price_snapshot')
        item.save(update_fields=update_fields)
        _replace_table_item_toppings(
            table_item=item,
            snapshot_rows=_snapshot_rows_from_product_toppings(topping_links),
        )
        item.refresh_from_db()
    else:
        item.save(update_fields=update_fields)
    return JsonResponse({'item': _serialize_table_cart_item(item), 'summary': _table_cart_summary(table)})


@login_required
@staff_or_manager_required
@require_POST
def api_table_checkout(request, table_id):
    user = request.user
    table = _get_accessible_table_or_403(user, table_id)
    if not table:
        return _json_error('Không có quyền truy cập bàn này.', 403)

    payload = _parse_json_request(request)
    if payload is None:
        return _json_error('Payload JSON không hợp lệ.', 400)

    payment_method = payload.get('payment_method') or Order.PaymentMethod.CASH
    if payment_method not in {Order.PaymentMethod.CASH, Order.PaymentMethod.CARD}:
        return _json_error('Phương thức thanh toán không hợp lệ.', 400)

    try:
        tax_rate = _parse_decimal(payload.get('tax_rate', '0'), field='tax_rate')
        customer_paid = _parse_decimal(payload.get('customer_paid', '0'), field='customer_paid')
    except ValueError as exc:
        return _json_error(str(exc), 400)

    if tax_rate < 0:
        return _json_error('tax_rate không được âm.', 400)

    with transaction.atomic():
        cart_items = list(
            TableCartItem.objects.filter(table=table)
            .select_related('product', 'unit')
            .prefetch_related('toppings')
        )
        if not cart_items:
            return _json_error('Bàn này chưa có món để thanh toán.', 400)

        subtotal = Decimal('0')
        for item in cart_items:
            subtotal += item.unit_price_snapshot * item.quantity

        customer_id = payload.get('customer_id')
        customer = resolve_customer_for_checkout(tenant=user.tenant, customer_id=customer_id)
        if customer_id and not customer:
            return _json_error('Khách hàng không hợp lệ hoặc đã ngưng hoạt động.', 400)

        promotion_id = payload.get('promotion_id')
        promotion = resolve_promotion_for_checkout(
            tenant=user.tenant,
            store=table.store,
            promotion_id=promotion_id,
            subtotal=subtotal,
        )
        if promotion_id and not promotion:
            return _json_error('Khuyến mãi không hợp lệ hoặc không đủ điều kiện áp dụng.', 400)

        totals = calculate_order_totals(subtotal=subtotal, tax_rate=tax_rate, promotion=promotion, customer=customer)
        discount_amount = totals['discount_amount']
        tier_discount_amount = totals['tier_discount_amount']
        tier_discount_percent = totals['tier_discount_percent']
        discount_source = totals['discount_source']
        tax_amount = totals['tax_amount']
        total_amount = totals['total_amount']

        if payment_method == Order.PaymentMethod.CASH and customer_paid < total_amount:
            return _json_error('Khách đưa chưa đủ tiền.', 400)

        if payment_method == Order.PaymentMethod.CARD and customer_paid <= 0:
            customer_paid = total_amount

        change_amount = customer_paid - total_amount

        order = Order.objects.create(
            tenant=user.tenant,
            store=table.store,
            cashier=user,
            customer=customer,
            promotion=promotion,
            payment_method=payment_method,
            sale_channel=Order.SaleChannel.DINE_IN,
            subtotal=subtotal,
            discount_amount=discount_amount,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            total_amount=total_amount,
            customer_paid=customer_paid,
            change_amount=change_amount,
            **_snapshot_promotion_fields(promotion),
            **_snapshot_tier_discount_fields(totals),
        )

        for item in cart_items:
            order_item = OrderItem.objects.create(
                order=order,
                product=item.product,
                unit=item.unit,
                snapshot_product_name=item.snapshot_product_name,
                snapshot_unit_name=item.snapshot_unit_name,
                unit_price=item.unit_price_snapshot,
                quantity=item.quantity,
                note=item.note,
                line_total=item.unit_price_snapshot * item.quantity,
            )
            OrderItemTopping.objects.bulk_create(
                [
                    OrderItemTopping(
                        order_item=order_item,
                        topping_id=topping.topping_id,
                        snapshot_topping_name=topping.snapshot_topping_name,
                        snapshot_price=topping.snapshot_price,
                    )
                    for topping in item.toppings.all().order_by('id')
                ]
            )

        TableCartItem.objects.filter(table=table).delete()

        points_earned = calculate_points_for_amount(total_amount) if customer else 0
        if customer:
            customer = recompute_customer_stats(customer)

    return JsonResponse(
        {
            'detail': 'Thanh toán bàn thành công.',
            'order_id': order.id,
            'order_code': order.order_code,
            'discount_amount': float(discount_amount),
            'discount_source': discount_source,
            'tier_discount_amount': float(tier_discount_amount),
            'tier_discount_percent': float(tier_discount_percent),
            'total_amount': float(total_amount),
            'change_amount': float(change_amount),
            'points_earned': points_earned,
            'customer_tier': customer.tier if customer else '',
            'table_status': 'empty',
        },
        status=201,
    )


@login_required
@staff_or_manager_required
@require_GET
def api_qr_orders(request):
    user = request.user
    store = get_accessible_store_or_default(user, request.GET.get('store_id'))
    if not store:
        return _json_error('Store không hợp lệ hoặc không có quyền truy cập.', 403)

    status = (request.GET.get('status') or 'pending').strip().upper()
    status_map = {
        'PENDING': QROrder.Status.PENDING,
        'APPROVED': QROrder.Status.APPROVED,
        'REJECTED': QROrder.Status.REJECTED,
        'CANCELLED': QROrder.Status.CANCELLED,
    }
    selected_status = status_map.get(status, QROrder.Status.PENDING)

    orders = (
        QROrder.objects.filter(tenant=user.tenant, store=store, status=selected_status)
        .select_related('table', 'rejected_by')
        .prefetch_related('items', 'items__toppings')
        .order_by('-created_at')
    )

    payload = []
    for order in orders:
        items_payload = []
        total = Decimal('0')
        for item in order.items.all():
            line_total = item.unit_price_snapshot * item.quantity
            total += line_total
            toppings = _serialize_topping_rows(item.toppings.all().order_by('id'))
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
                    'toppings': toppings,
                }
            )

        row = {
            'id': order.id,
            'status': order.status,
            'table_id': order.table_id,
            'table_name': order.table.name,
            'customer_note': order.customer_note,
            'created_at': order.created_at.isoformat(),
            'time': timezone.localtime(order.created_at).strftime('%H:%M'),
            'total': float(total),
            'items': items_payload,
        }
        if order.status == QROrder.Status.REJECTED:
            row['rejection_reason'] = order.rejection_reason or ''
            row['rejected_by'] = order.rejected_by.get_username() if order.rejected_by_id else ''
        payload.append(row)

    return JsonResponse({'store': {'id': store.id, 'name': store.name}, 'orders': payload})


@login_required
@staff_or_manager_required
@require_POST
def api_qr_order_approve(request, order_id):
    user = request.user

    with transaction.atomic():
        order = get_object_or_404(
            QROrder.objects.select_for_update().select_related('table', 'store').prefetch_related('items', 'items__toppings'),
            id=order_id,
            tenant=user.tenant,
        )

        if not get_user_accessible_stores(user).filter(id=order.store_id).exists():
            return _json_error('Không có quyền duyệt đơn QR của cửa hàng này.', 403)

        if order.status == QROrder.Status.APPROVED:
            return JsonResponse({'detail': 'Đơn đã được duyệt trước đó.', 'status': order.status})
        if order.status == QROrder.Status.REJECTED:
            return _json_error('Đơn đã bị từ chối nên không thể duyệt.', 400)
        if order.status == QROrder.Status.CANCELLED:
            return _json_error('Đơn đã bị khách hủy nên không thể duyệt.', 400)

        for qr_item in order.items.all():
            if not qr_item.unit_id or not qr_item.product_id:
                continue
            snapshot_toppings = _snapshot_rows_from_qr_item_toppings(qr_item)
            topping_total = Decimal('0')
            for row in snapshot_toppings:
                topping_total += row['price']
            base_unit_price = qr_item.unit_price_snapshot - topping_total
            _upsert_table_cart_item(
                tenant=order.tenant,
                store=order.store,
                table=order.table,
                unit=qr_item.unit,
                quantity=qr_item.quantity,
                base_unit_price=base_unit_price,
                snapshot_toppings=snapshot_toppings,
                note=qr_item.note,
                source=TableCartItem.Source.QR,
                qr_order=order,
            )

        order.status = QROrder.Status.APPROVED
        order.approved_by = user
        order.resolved_at = timezone.now()
        order.save(update_fields=['status', 'approved_by', 'resolved_at', 'updated_at'])

    notify_qr_order_changed(
        store_id=order.store_id,
        order_id=order.id,
        status=order.status,
        reason='approved',
    )
    return JsonResponse({'detail': 'Đã duyệt đơn QR.', 'status': order.status, 'table_id': order.table_id})


@login_required
@staff_or_manager_required
@require_POST
def api_qr_order_reject(request, order_id):
    user = request.user
    payload = _parse_json_request(request)
    if payload is None:
        payload = {}
    reason = (payload.get('reason') or '').strip()
    if len(reason) > 500:
        return _json_error('Lý do không được quá 500 ký tự.', 400)

    with transaction.atomic():
        order = get_object_or_404(
            QROrder.objects.select_for_update().select_related('store'),
            id=order_id,
            tenant=user.tenant,
        )

        if not get_user_accessible_stores(user).filter(id=order.store_id).exists():
            return _json_error('Không có quyền từ chối đơn QR của cửa hàng này.', 403)

        if order.status == QROrder.Status.REJECTED:
            return JsonResponse({'detail': 'Đơn đã bị từ chối trước đó.', 'status': order.status})
        if order.status == QROrder.Status.APPROVED:
            return _json_error('Đơn đã được duyệt nên không thể từ chối.', 400)
        if order.status == QROrder.Status.CANCELLED:
            return _json_error('Đơn đã bị khách hủy nên không thể từ chối.', 400)

        if not reason:
            return _json_error('Vui lòng chọn hoặc nhập lý do từ chối.', 400)

        order.status = QROrder.Status.REJECTED
        order.rejected_by = user
        order.rejection_reason = reason
        order.resolved_at = timezone.now()
        order.save(
            update_fields=['status', 'rejected_by', 'rejection_reason', 'resolved_at', 'updated_at']
        )

    notify_qr_order_changed(
        store_id=order.store_id,
        order_id=order.id,
        status=order.status,
        reason='rejected',
    )
    return JsonResponse({'detail': 'Đã từ chối đơn QR.', 'status': order.status})
