import json
from decimal import Decimal

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Min, Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from App_Catalog.models import Product, ProductUnit
from App_Sales.models import DiningTable, QROrder, QROrderItem
from App_Sales.services import get_effective_unit_price
from App_Tenant.models import Store, Tenant


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


@csrf_exempt
@require_POST
def api_public_qr_orders(request):
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Payload JSON không hợp lệ.'}, status=400)

    table_code = (payload.get('table_code') or '').strip().upper()
    token = (payload.get('token') or '').strip()
    customer_note = (payload.get('note') or '').strip()[:255]
    raw_items = payload.get('items') or []

    if not table_code or not token:
        return JsonResponse({'detail': 'Thiếu table_code hoặc token.'}, status=400)
    if not raw_items:
        return JsonResponse({'detail': 'Giỏ hàng QR trống.'}, status=400)

    table = DiningTable.objects.select_related('store', 'tenant').filter(
        code=table_code,
        qr_token=token,
        is_active=True,
        store__is_active=True,
        tenant__is_active=True,
    ).first()
    if not table:
        return JsonResponse({'detail': 'QR không hợp lệ hoặc đã hết hiệu lực.'}, status=403)

    prepared_items = []
    for raw in raw_items:
        product_id = raw.get('product_id')
        unit_id = raw.get('unit_id')
        try:
            quantity = int(raw.get('quantity', 0))
        except (TypeError, ValueError):
            return JsonResponse({'detail': 'Số lượng không hợp lệ.'}, status=400)

        if quantity <= 0:
            return JsonResponse({'detail': 'Số lượng phải lớn hơn 0.'}, status=400)

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
            return JsonResponse({'detail': f'Sản phẩm hoặc đơn vị không hợp lệ: {product_id}/{unit_id}'}, status=400)

        if unit.product.category_id:
            visible = unit.product.category.store_links.filter(store=table.store, is_visible=True).exists()
            if not visible:
                return JsonResponse({'detail': f'Sản phẩm không hiển thị cho bàn này: {unit.product.name}'}, status=400)

        note = (raw.get('note') or '').strip()[:255]
        unit_price = get_effective_unit_price(unit=unit, store_id=table.store_id)
        prepared_items.append(
            {
                'product': unit.product,
                'unit': unit,
                'quantity': quantity,
                'note': note,
                'unit_price': unit_price,
            }
        )

    with transaction.atomic():
        qr_order = QROrder.objects.create(
            tenant=table.tenant,
            store=table.store,
            table=table,
            status=QROrder.Status.PENDING,
            customer_note=customer_note,
            created_by_ip=request.META.get('REMOTE_ADDR') or None,
        )

        for item in prepared_items:
            QROrderItem.objects.create(
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

    return JsonResponse(
        {
            'detail': 'Đã ghi nhận đơn QR. Vui lòng chờ nhân viên duyệt.',
            'qr_order_id': qr_order.id,
            'status': qr_order.status,
            'table': {'id': table.id, 'name': table.name, 'code': table.code},
        },
        status=201,
    )
