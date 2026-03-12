import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from App_Accounts.permissions import staff_or_manager_required
from App_Catalog.models import Product, ProductUnit
from App_Sales.models import Order, OrderItem
from App_Sales.services import get_accessible_store_or_default, get_effective_unit_price
from App_Tenant.services import get_user_accessible_stores


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
def api_products(request):
    user = request.user
    if not user.tenant_id:
        return JsonResponse({'detail': 'User chưa được gán tenant.'}, status=400)

    store_id = request.GET.get('store_id')
    store = get_accessible_store_or_default(user, store_id)
    if not store:
        return JsonResponse({'detail': 'Store không hợp lệ hoặc không có quyền truy cập.'}, status=403)

    queryset = (
        Product.objects.filter(
            tenant=user.tenant,
            is_active=True,
            store_links__store=store,
            store_links__is_available=True,
        )
        .select_related('category')
        .prefetch_related('units')
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
        for unit in product.units.filter(is_active=True).order_by('display_order', 'id'):
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

        products.append(
            {
                'id': product.id,
                'name': product.name,
                'category': product.category.name if product.category else 'Khác',
                'category_id': str(product.category_id or ''),
                'image': product.image_url or 'https://placehold.co/600x600/png?text=Product',
                'units': units_payload,
                'base_price': units_payload[0]['price'],
            }
        )

    return JsonResponse(
        {
            'store': {
                'id': store.id,
                'name': store.name,
            },
            'categories': categories,
            'products': products,
        }
    )


@login_required
@staff_or_manager_required
@require_POST
def api_checkout(request):
    user = request.user
    if not user.tenant_id:
        return JsonResponse({'detail': 'User chưa được gán tenant.'}, status=400)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Payload JSON không hợp lệ.'}, status=400)

    store = get_accessible_store_or_default(user, payload.get('store_id'))
    if not store:
        return JsonResponse({'detail': 'Store không hợp lệ hoặc không có quyền truy cập.'}, status=403)

    items = payload.get('items') or []
    if not items:
        return JsonResponse({'detail': 'Giỏ hàng trống.'}, status=400)

    payment_method = payload.get('payment_method') or Order.PaymentMethod.CASH
    if payment_method not in {Order.PaymentMethod.CASH, Order.PaymentMethod.CARD}:
        return JsonResponse({'detail': 'Phương thức thanh toán không hợp lệ.'}, status=400)

    try:
        tax_rate = Decimal(str(payload.get('tax_rate', '0')))
    except (InvalidOperation, TypeError, ValueError):
        return JsonResponse({'detail': 'tax_rate không hợp lệ.'}, status=400)

    if tax_rate < 0:
        return JsonResponse({'detail': 'tax_rate không được âm.'}, status=400)

    try:
        customer_paid = Decimal(str(payload.get('customer_paid', '0')))
    except (InvalidOperation, TypeError, ValueError):
        return JsonResponse({'detail': 'customer_paid không hợp lệ.'}, status=400)

    with transaction.atomic():
        prepared_items = []
        subtotal = Decimal('0')

        for item in items:
            product_id = item.get('product_id')
            unit_id = item.get('unit_id')
            try:
                quantity = int(item.get('quantity', 0))
            except (TypeError, ValueError):
                return JsonResponse({'detail': 'Số lượng không hợp lệ.'}, status=400)
            note = (item.get('note') or '').strip()

            if quantity <= 0:
                return JsonResponse({'detail': 'Số lượng phải lớn hơn 0.'}, status=400)

            try:
                unit = ProductUnit.objects.select_related('product').get(
                    id=unit_id,
                    product_id=product_id,
                    product__tenant=user.tenant,
                    product__is_active=True,
                    is_active=True,
                    product__store_links__store=store,
                    product__store_links__is_available=True,
                )
            except ProductUnit.DoesNotExist:
                return JsonResponse(
                    {'detail': f'Sản phẩm hoặc đơn vị không hợp lệ: {product_id}/{unit_id}'},
                    status=400,
                )

            unit_price = get_effective_unit_price(unit=unit, store_id=store.id)
            line_total = unit_price * quantity
            subtotal += line_total
            prepared_items.append(
                {
                    'product': unit.product,
                    'unit': unit,
                    'quantity': quantity,
                    'note': note,
                    'unit_price': unit_price,
                    'line_total': line_total,
                }
            )

        tax_amount = subtotal * tax_rate
        total_amount = subtotal + tax_amount
        if customer_paid < total_amount:
            return JsonResponse({'detail': 'Khách đưa chưa đủ tiền.'}, status=400)

        change_amount = customer_paid - total_amount

        order = Order.objects.create(
            tenant=user.tenant,
            store=store,
            cashier=user,
            payment_method=payment_method,
            subtotal=subtotal,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            total_amount=total_amount,
            customer_paid=customer_paid,
            change_amount=change_amount,
        )

        OrderItem.objects.bulk_create(
            [
                OrderItem(
                    order=order,
                    product=item['product'],
                    unit=item['unit'],
                    snapshot_product_name=item['product'].name,
                    snapshot_unit_name=item['unit'].name,
                    unit_price=item['unit_price'],
                    quantity=item['quantity'],
                    note=item['note'][:255],
                    line_total=item['line_total'],
                )
                for item in prepared_items
            ]
        )

    return JsonResponse(
        {
            'order_id': order.id,
            'order_code': order.order_code,
            'subtotal': float(subtotal),
            'tax_amount': float(tax_amount),
            'total_amount': float(total_amount),
            'customer_paid': float(customer_paid),
            'change_amount': float(change_amount),
        },
        status=201,
    )
