from datetime import datetime, time, timedelta
from io import BytesIO
from decimal import Decimal
from urllib.parse import urlencode

import qrcode
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from App_Accounts.models import User
from App_Accounts.permissions import manager_required
from App_Catalog.models import Category, Product, ProductTopping, ProductUnit, StoreCategory, StoreProduct, Topping
from App_Quanly.catalog_excel import MAX_UPLOAD_BYTES, import_catalog_from_upload, template_workbook_bytes
from App_Quanly.forms import (
    CategoryForm,
    DiningTableForm,
    ProductForm,
    ProductToppingForm,
    ProductUnitForm,
    StaffCreateForm,
    StaffPasswordResetForm,
    StorePaymentForm,
    ToppingForm,
)
from App_Sales.models import DiningTable, Order, OrderItem, generate_qr_token
from App_Tenant.models import Store, UserStoreAccess


def _tenant_or_404(user):
    if not user.tenant_id:
        raise Http404('User chưa được gán tenant')
    return user.tenant


def _parse_date_bounds(date_from, date_to):
    tz = timezone.get_current_timezone()
    start_dt = None
    end_dt = None
    if date_from:
        start_dt = timezone.make_aware(datetime.combine(datetime.fromisoformat(date_from).date(), time.min), tz)
    if date_to:
        end_dt = timezone.make_aware(datetime.combine(datetime.fromisoformat(date_to).date(), time.max), tz)
    return start_dt, end_dt


def _sync_category_store_links(category, selected_store_ids):
    all_store_ids = list(Store.objects.filter(tenant=category.tenant).values_list('id', flat=True))
    for store_id in all_store_ids:
        link, _ = StoreCategory.objects.get_or_create(store_id=store_id, category=category)
        link.is_visible = store_id in selected_store_ids
        link.save(update_fields=['is_visible', 'updated_at'])


def _sync_product_store_links(product, selected_store_ids):
    all_store_ids = list(Store.objects.filter(tenant=product.tenant).values_list('id', flat=True))
    for store_id in all_store_ids:
        link, _ = StoreProduct.objects.get_or_create(store_id=store_id, product=product)
        link.is_available = store_id in selected_store_ids
        link.save(update_fields=['is_available', 'updated_at'])


@manager_required
def dashboard(request):
    tenant = _tenant_or_404(request.user)
    stores = Store.objects.filter(tenant=tenant, is_active=True).order_by('name')
    tenant_orders = Order.objects.filter(tenant=tenant, status=Order.Status.COMPLETED)
    orders = tenant_orders

    store_id = request.GET.get('store')
    if store_id and store_id.isdigit():
        selected_store_id = int(store_id)
        orders = orders.filter(store_id=selected_store_id)
        tenant_orders = tenant_orders.filter(store_id=selected_store_id)

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    try:
        start_dt, end_dt = _parse_date_bounds(date_from, date_to)
    except ValueError:
        messages.error(request, 'Bộ lọc ngày không hợp lệ.')
        start_dt, end_dt = None, None

    if start_dt:
        orders = orders.filter(created_at__gte=start_dt)
    if end_dt:
        orders = orders.filter(created_at__lte=end_dt)

    stats = orders.aggregate(
        total_revenue=Coalesce(Sum('total_amount'), Decimal('0')),
        total_orders=Coalesce(Count('id'), 0),
    )

    total_orders = stats['total_orders'] or 0
    total_revenue = stats['total_revenue'] or Decimal('0')
    avg_order_value = (total_revenue / total_orders) if total_orders else Decimal('0')
    active_store_count = stores.count()

    payment_stats = orders.values('payment_method').annotate(total=Count('id'))
    payment_map = {row['payment_method']: row['total'] for row in payment_stats}
    cash_orders = payment_map.get(Order.PaymentMethod.CASH, 0)
    card_orders = payment_map.get(Order.PaymentMethod.CARD, 0)
    cash_percent = int(round((cash_orders * 100) / total_orders)) if total_orders else 0
    card_percent = 100 - cash_percent if total_orders else 0

    today_local = timezone.localdate()
    tz = timezone.get_current_timezone()
    today_start = timezone.make_aware(datetime.combine(today_local, time.min), tz)
    today_end = timezone.make_aware(datetime.combine(today_local, time.max), tz)
    today_stats = tenant_orders.filter(created_at__gte=today_start, created_at__lte=today_end).aggregate(
        total_revenue=Coalesce(Sum('total_amount'), Decimal('0')),
        total_orders=Coalesce(Count('id'), 0),
    )

    store_kpis = list(
        orders.values('store__name')
        .annotate(
            total_revenue=Coalesce(Sum('total_amount'), Decimal('0')),
            total_orders=Coalesce(Count('id'), 0),
        )
        .order_by('-total_revenue', 'store__name')[:5]
    )
    top_store_name = store_kpis[0]['store__name'] if store_kpis else ''
    top_store_revenue = store_kpis[0]['total_revenue'] if store_kpis else Decimal('0')

    chart_orders = orders
    chart_caption = 'Theo bộ lọc hiện tại'
    if not date_from and not date_to:
        chart_start_dt = timezone.now() - timedelta(days=13)
        chart_orders = chart_orders.filter(created_at__gte=chart_start_dt)
        chart_caption = '14 ngày gần nhất'

    daily_chart_rows = list(
        chart_orders.annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(
            total_revenue=Coalesce(Sum('total_amount'), Decimal('0')),
            total_orders=Coalesce(Count('id'), 0),
        )
        .order_by('day')
    )
    chart_day_map = {
        row['day']: {
            'revenue': int((row['total_revenue'] or Decimal('0')).quantize(Decimal('1'))),
            'orders': int(row['total_orders'] or 0),
        }
        for row in daily_chart_rows
        if row['day']
    }
    if daily_chart_rows:
        chart_start_day = daily_chart_rows[0]['day']
        chart_end_day = daily_chart_rows[-1]['day']
    else:
        chart_end_day = timezone.localdate()
        chart_start_day = chart_end_day - timedelta(days=6)

    chart_revenue_labels = []
    chart_revenue_values = []
    chart_orders_values = []
    cursor_day = chart_start_day
    while cursor_day <= chart_end_day:
        day_point = chart_day_map.get(cursor_day, {'revenue': 0, 'orders': 0})
        chart_revenue_labels.append(cursor_day.strftime('%d/%m'))
        chart_revenue_values.append(day_point['revenue'])
        chart_orders_values.append(day_point['orders'])
        cursor_day += timedelta(days=1)

    chart_payment_names = ['Tiền mặt', 'Card/QR']
    chart_payment_values = [cash_orders, card_orders]
    chart_store_names = [row['store__name'] for row in store_kpis]
    chart_store_values = [int((row['total_revenue'] or Decimal('0')).quantize(Decimal('1'))) for row in store_kpis]

    recent_orders = orders.select_related('store', 'cashier').order_by('-created_at')[:10]
    if date_from and date_to:
        period_label = f'{date_from} -> {date_to}'
    elif date_from:
        period_label = f'Từ {date_from}'
    elif date_to:
        period_label = f'Đến {date_to}'
    else:
        period_label = 'Toàn bộ thời gian'

    context = {
        'stores': stores,
        'selected_store': int(store_id) if store_id and store_id.isdigit() else None,
        'date_from': date_from or '',
        'date_to': date_to or '',
        'period_label': period_label,
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'avg_order_value': avg_order_value,
        'active_store_count': active_store_count,
        'cash_orders': cash_orders,
        'card_orders': card_orders,
        'cash_percent': cash_percent,
        'card_percent': card_percent,
        'today_revenue': today_stats['total_revenue'] or Decimal('0'),
        'today_orders': today_stats['total_orders'] or 0,
        'store_kpis': store_kpis,
        'top_store_name': top_store_name,
        'top_store_revenue': top_store_revenue,
        'chart_caption': chart_caption,
        'chart_revenue_labels': chart_revenue_labels,
        'chart_revenue_values': chart_revenue_values,
        'chart_orders_values': chart_orders_values,
        'chart_payment_names': chart_payment_names,
        'chart_payment_values': chart_payment_values,
        'chart_store_names': chart_store_names,
        'chart_store_values': chart_store_values,
        'recent_orders': recent_orders,
    }
    return render(request, 'App_Quanly/dashboard.html', context)


@manager_required
def order_history(request):
    tenant = _tenant_or_404(request.user)
    stores = Store.objects.filter(tenant=tenant, is_active=True).order_by('name')
    cashiers = (
        User.objects.filter(tenant=tenant, orders__isnull=False)
        .distinct()
        .order_by('username')
    )

    orders = Order.objects.filter(tenant=tenant).select_related('store', 'cashier')

    selected_store = (request.GET.get('store') or '').strip()
    selected_payment = (request.GET.get('payment_method') or '').strip()
    selected_status = (request.GET.get('status') or '').strip()
    selected_cashier = (request.GET.get('cashier') or '').strip()
    selected_q = (request.GET.get('q') or '').strip()
    date_from = (request.GET.get('date_from') or '').strip()
    date_to = (request.GET.get('date_to') or '').strip()

    if selected_store.isdigit():
        orders = orders.filter(store_id=int(selected_store))
    if selected_payment in {Order.PaymentMethod.CASH, Order.PaymentMethod.CARD}:
        orders = orders.filter(payment_method=selected_payment)
    if selected_status in {Order.Status.COMPLETED, Order.Status.CANCELLED}:
        orders = orders.filter(status=selected_status)
    if selected_cashier.isdigit():
        orders = orders.filter(cashier_id=int(selected_cashier))
    if selected_q:
        orders = orders.filter(
            Q(order_code__icontains=selected_q)
            | Q(cashier__username__icontains=selected_q)
            | Q(store__name__icontains=selected_q)
        )

    try:
        start_dt, end_dt = _parse_date_bounds(date_from, date_to)
    except ValueError:
        messages.error(request, 'Bộ lọc ngày không hợp lệ.')
        start_dt, end_dt = None, None
    if start_dt:
        orders = orders.filter(created_at__gte=start_dt)
    if end_dt:
        orders = orders.filter(created_at__lte=end_dt)

    summary = orders.aggregate(
        total_orders=Coalesce(Count('id'), 0),
        total_revenue=Coalesce(Sum('total_amount'), Decimal('0')),
    )

    orders = orders.prefetch_related(
        Prefetch(
            'items',
            queryset=OrderItem.objects.prefetch_related('toppings').order_by('id'),
        )
    ).order_by('-created_at')

    paginator = Paginator(orders, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    query_params = request.GET.copy()
    query_params.pop('page', None)

    return render(
        request,
        'App_Quanly/order_history.html',
        {
            'stores': stores,
            'cashiers': cashiers,
            'page_obj': page_obj,
            'orders': page_obj.object_list,
            'total_orders': summary['total_orders'] or 0,
            'total_revenue': summary['total_revenue'] or Decimal('0'),
            'selected_store': selected_store,
            'selected_payment': selected_payment,
            'selected_status': selected_status,
            'selected_cashier': selected_cashier,
            'selected_q': selected_q,
            'date_from': date_from,
            'date_to': date_to,
            'payment_choices': Order.PaymentMethod.choices,
            'status_choices': Order.Status.choices,
            'query_string': query_params.urlencode(),
        },
    )


@manager_required
@require_POST
def order_delete(request, pk):
    tenant = _tenant_or_404(request.user)
    order = get_object_or_404(Order, pk=pk, tenant=tenant)
    code = order.order_code
    order.delete()
    messages.success(request, f'Đã xóa đơn hàng {code}.')
    next_url = (request.POST.get('next') or '').strip()
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect('App_Quanly:orders')


@manager_required
def category_list_create(request):
    tenant = _tenant_or_404(request.user)
    stores = Store.objects.filter(tenant=tenant, is_active=True).order_by('name')
    categories = (
        Category.objects.filter(tenant=tenant)
        .prefetch_related(
            Prefetch(
                'store_links',
                queryset=StoreCategory.objects.select_related('store').filter(store__is_active=True),
            )
        )
        .order_by('name')
    )
    form = CategoryForm(request.POST or None, tenant=tenant)

    if request.method == 'POST' and form.is_valid():
        category = form.save(commit=False)
        category.tenant = tenant
        category.save()
        selected_store_ids = set(form.cleaned_data['store_ids'].values_list('id', flat=True))
        _sync_category_store_links(category, selected_store_ids)
        messages.success(request, 'Đã tạo danh mục.')
        return redirect('App_Quanly:categories')

    category_rows = []
    for category in categories:
        visible_links = [link for link in category.store_links.all() if link.is_visible]
        visible_store_ids = [link.store_id for link in visible_links]
        visible_store_names = [link.store.name for link in visible_links]
        category_rows.append(
            {
                'category': category,
                'visible_store_ids_csv': ','.join(str(store_id) for store_id in visible_store_ids),
                'visible_store_names': ', '.join(visible_store_names),
            }
        )

    return render(
        request,
        'App_Quanly/categories.html',
        {
            'category_rows': category_rows,
            'stores': stores,
            'form': form,
            'open_create_modal': request.method == 'POST' and form.errors,
        },
    )


@manager_required
def category_edit(request, pk):
    tenant = _tenant_or_404(request.user)
    category = get_object_or_404(Category, pk=pk, tenant=tenant)
    initial_store_ids = category.store_links.filter(is_visible=True).values_list('store_id', flat=True)
    if request.method != 'POST':
        return redirect('App_Quanly:categories')

    form = CategoryForm(request.POST, instance=category, tenant=tenant, initial={'store_ids': initial_store_ids})
    if form.is_valid():
        category = form.save()
        selected_store_ids = set(form.cleaned_data['store_ids'].values_list('id', flat=True))
        _sync_category_store_links(category, selected_store_ids)
        messages.success(request, 'Đã cập nhật danh mục.')
    else:
        messages.error(request, 'Không thể cập nhật danh mục, vui lòng kiểm tra lại dữ liệu.')
    return redirect('App_Quanly:categories')


@manager_required
@require_POST
def category_delete(request, pk):
    tenant = _tenant_or_404(request.user)
    category = get_object_or_404(Category, pk=pk, tenant=tenant)
    category.delete()
    messages.success(request, 'Đã xóa danh mục.')
    return redirect('App_Quanly:categories')


@manager_required
def catalog_import_template_download(request):
    _tenant_or_404(request.user)
    buf = BytesIO(template_workbook_bytes())
    return FileResponse(
        buf,
        as_attachment=True,
        filename='eapp_catalog_mau.xlsx',
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


@manager_required
@require_POST
def catalog_import_upload(request):
    tenant = _tenant_or_404(request.user)
    upload = request.FILES.get('excel_file')
    if not upload:
        messages.error(request, 'Chưa chọn file Excel.')
        return redirect('App_Quanly:categories')
    if upload.size > MAX_UPLOAD_BYTES:
        messages.error(request, 'File quá lớn (tối đa 5 MB).')
        return redirect('App_Quanly:categories')
    if not (upload.name or '').lower().endswith('.xlsx'):
        messages.error(request, 'Chỉ chấp nhận file .xlsx')
        return redirect('App_Quanly:categories')
    result = import_catalog_from_upload(tenant, upload)
    if result['ok']:
        messages.success(request, result['message'])
    else:
        err_list = result['errors']
        max_show = 40
        for msg in err_list[:max_show]:
            messages.error(request, msg)
        if len(err_list) > max_show:
            messages.error(request, f'… và thêm {len(err_list) - max_show} lỗi.')
    return redirect('App_Quanly:categories')


@manager_required
def product_list_create(request):
    tenant = _tenant_or_404(request.user)
    stores = Store.objects.filter(tenant=tenant, is_active=True).order_by('name')
    products = (
        Product.objects.filter(tenant=tenant)
        .select_related('category')
        .prefetch_related('units', 'store_links__store')
        .order_by('name')
    )
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, tenant=tenant)
    else:
        form = ProductForm(tenant=tenant)

    if request.method == 'POST' and form.is_valid():
        product = form.save(commit=False)
        product.tenant = tenant
        product.save()
        selected_store_ids = set(form.cleaned_data['store_ids'].values_list('id', flat=True))
        _sync_product_store_links(product, selected_store_ids)
        messages.success(request, 'Đã tạo sản phẩm. Hãy thêm đơn vị bán ở bên dưới.')
        return redirect('App_Quanly:products')

    product_rows = []
    for product in products:
        available_store_ids = []
        available_store_names = []
        for link in product.store_links.all():
            if link.is_available:
                available_store_ids.append(link.store_id)
                available_store_names.append(link.store.name)
        product_rows.append(
            {
                'product': product,
                'available_store_ids_csv': ','.join(str(store_id) for store_id in available_store_ids),
                'available_store_names': ', '.join(available_store_names),
            }
        )

    return render(
        request,
        'App_Quanly/products.html',
        {
            'product_rows': product_rows,
            'stores': stores,
            'categories': form.fields['category'].queryset,
            'form': form,
            'unit_form': ProductUnitForm(),
            'open_create_modal': request.method == 'POST' and form.errors,
        },
    )


@manager_required
def product_edit(request, pk):
    tenant = _tenant_or_404(request.user)
    product = get_object_or_404(Product, pk=pk, tenant=tenant)
    initial_store_ids = product.store_links.filter(is_available=True).values_list('store_id', flat=True)
    if request.method != 'POST':
        return redirect('App_Quanly:products')

    form = ProductForm(
        request.POST,
        request.FILES,
        instance=product,
        tenant=tenant,
        initial={'store_ids': initial_store_ids},
    )
    if form.is_valid():
        product = form.save()
        selected_store_ids = set(form.cleaned_data['store_ids'].values_list('id', flat=True))
        _sync_product_store_links(product, selected_store_ids)
        messages.success(request, 'Đã cập nhật sản phẩm.')
    else:
        messages.error(request, 'Không thể cập nhật sản phẩm, vui lòng kiểm tra lại dữ liệu.')
    return redirect('App_Quanly:products')


@manager_required
@require_POST
def product_delete(request, pk):
    tenant = _tenant_or_404(request.user)
    product = get_object_or_404(Product, pk=pk, tenant=tenant)
    product.delete()
    messages.success(request, 'Đã xóa sản phẩm.')
    return redirect('App_Quanly:products')


@manager_required
@require_POST
def unit_add(request, product_pk):
    tenant = _tenant_or_404(request.user)
    product = get_object_or_404(Product, pk=product_pk, tenant=tenant)
    form = ProductUnitForm(request.POST)
    if form.is_valid():
        unit = form.save(commit=False)
        unit.product = product
        unit.save()
        messages.success(request, 'Đã thêm đơn vị sản phẩm.')
    else:
        messages.error(request, 'Không thể thêm đơn vị, vui lòng kiểm tra dữ liệu.')
    return redirect('App_Quanly:products')


@manager_required
def unit_edit(request, pk):
    tenant = _tenant_or_404(request.user)
    unit = get_object_or_404(ProductUnit, pk=pk, product__tenant=tenant)
    if request.method != 'POST':
        return redirect('App_Quanly:products')
    form = ProductUnitForm(request.POST, instance=unit)
    if form.is_valid():
        form.save()
        messages.success(request, 'Đã cập nhật đơn vị sản phẩm.')
    else:
        messages.error(request, 'Không thể cập nhật đơn vị sản phẩm, vui lòng kiểm tra lại dữ liệu.')
    return redirect('App_Quanly:products')


@manager_required
@require_POST
def unit_delete(request, pk):
    tenant = _tenant_or_404(request.user)
    unit = get_object_or_404(ProductUnit, pk=pk, product__tenant=tenant)
    unit.delete()
    messages.success(request, 'Đã xóa đơn vị sản phẩm.')
    return redirect('App_Quanly:products')


@manager_required
def topping_list_create(request):
    tenant = _tenant_or_404(request.user)
    toppings = Topping.objects.filter(tenant=tenant).order_by('display_order', 'name')
    mappings = (
        ProductTopping.objects.filter(product__tenant=tenant)
        .select_related('product', 'topping')
        .order_by('product__name', 'display_order', 'id')
    )

    topping_form = ToppingForm(prefix='topping')
    mapping_form = ProductToppingForm(prefix='mapping', tenant=tenant)
    open_topping_modal = False
    open_mapping_modal = False

    if request.method == 'POST':
        form_type = (request.POST.get('form_type') or '').strip()
        if form_type == 'topping':
            topping_form = ToppingForm(request.POST, prefix='topping')
            if topping_form.is_valid():
                topping = topping_form.save(commit=False)
                topping.tenant = tenant
                topping.save()
                messages.success(request, 'Đã tạo topping.')
                return redirect('App_Quanly:toppings')
            messages.error(request, 'Không thể tạo topping, vui lòng kiểm tra dữ liệu.')
            open_topping_modal = True
        elif form_type == 'mapping':
            mapping_form = ProductToppingForm(request.POST, prefix='mapping', tenant=tenant)
            if mapping_form.is_valid():
                mapping = mapping_form.save()
                messages.success(request, f'Đã gán topping "{mapping.topping.name}" cho "{mapping.product.name}".')
                return redirect('App_Quanly:toppings')
            messages.error(request, 'Không thể gán topping cho sản phẩm, vui lòng kiểm tra dữ liệu.')
            open_mapping_modal = True

    return render(
        request,
        'App_Quanly/toppings.html',
        {
            'toppings': toppings,
            'mappings': mappings,
            'topping_form': topping_form,
            'mapping_form': mapping_form,
            'mapping_products': mapping_form.fields['product'].queryset,
            'mapping_toppings': mapping_form.fields['topping'].queryset,
            'open_topping_modal': open_topping_modal,
            'open_mapping_modal': open_mapping_modal,
        },
    )


@manager_required
def topping_edit(request, pk):
    tenant = _tenant_or_404(request.user)
    topping = get_object_or_404(Topping, pk=pk, tenant=tenant)
    if request.method != 'POST':
        return redirect('App_Quanly:toppings')
    form = ToppingForm(request.POST, instance=topping)
    if form.is_valid():
        form.save()
        messages.success(request, 'Đã cập nhật topping.')
    else:
        messages.error(request, 'Không thể cập nhật topping, vui lòng kiểm tra lại dữ liệu.')
    return redirect('App_Quanly:toppings')


@manager_required
@require_POST
def topping_delete(request, pk):
    tenant = _tenant_or_404(request.user)
    topping = get_object_or_404(Topping, pk=pk, tenant=tenant)
    topping.delete()
    messages.success(request, 'Đã xóa topping.')
    return redirect('App_Quanly:toppings')


@manager_required
def product_topping_list_create(request):
    return redirect('App_Quanly:toppings')


@manager_required
def product_topping_edit(request, pk):
    tenant = _tenant_or_404(request.user)
    mapping = get_object_or_404(ProductTopping.objects.select_related('product', 'topping'), pk=pk, product__tenant=tenant)
    if request.method != 'POST':
        return redirect('App_Quanly:toppings')
    form = ProductToppingForm(request.POST, instance=mapping, tenant=tenant)
    if form.is_valid():
        form.save()
        messages.success(request, 'Đã cập nhật gán topping sản phẩm.')
    else:
        messages.error(request, 'Không thể cập nhật gán topping, vui lòng kiểm tra lại dữ liệu.')
    return redirect('App_Quanly:toppings')


@manager_required
@require_POST
def product_topping_delete(request, pk):
    tenant = _tenant_or_404(request.user)
    mapping = get_object_or_404(ProductTopping, pk=pk, product__tenant=tenant)
    mapping.delete()
    messages.success(request, 'Đã xóa gán topping khỏi sản phẩm.')
    return redirect('App_Quanly:toppings')


@manager_required
def payment_qr_settings(request):
    tenant = _tenant_or_404(request.user)
    stores = Store.objects.filter(tenant=tenant, is_active=True).order_by('name')
    if not stores.exists():
        return render(
            request,
            'App_Quanly/payment_qr.html',
            {'stores': stores, 'selected_store': None, 'form': None},
        )

    store_id_raw = (request.GET.get('store') or '').strip()
    if request.method == 'POST':
        store_id_raw = (request.POST.get('store') or '').strip()

    if store_id_raw.isdigit():
        selected_store = get_object_or_404(Store, pk=int(store_id_raw), tenant=tenant, is_active=True)
    else:
        selected_store = stores.first()

    if request.method == 'POST':
        form = StorePaymentForm(request.POST, request.FILES, instance=selected_store)
        if form.is_valid():
            form.save()
            messages.success(request, f'Đã cập nhật QR thanh toán cho "{selected_store.name}".')
            return redirect(f'{reverse("App_Quanly:payment_qr_settings")}?store={selected_store.id}')
        messages.error(request, 'Không thể lưu, vui lòng kiểm tra dữ liệu.')
    else:
        form = StorePaymentForm(instance=selected_store)

    return render(
        request,
        'App_Quanly/payment_qr.html',
        {
            'stores': stores,
            'selected_store': selected_store,
            'form': form,
        },
    )


def _build_table_qr_url(request, *, tenant_slug, table):
    base_path = reverse('App_Public:tenant_qr_ordering', kwargs={'public_slug': tenant_slug})
    return request.build_absolute_uri(f'{base_path}?{urlencode({"table_code": table.code, "token": table.qr_token})}')


def _build_qr_png_buffer(*, qr_url, box_size=8, border=2):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(qr_url)
    qr.make(fit=True)
    image = qr.make_image(fill_color='black', back_color='white').convert('RGB')
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer


@manager_required
def qr_table_list_create(request):
    tenant = _tenant_or_404(request.user)
    stores = Store.objects.filter(tenant=tenant, is_active=True).order_by('name')
    selected_store = (request.GET.get('store') or '').strip()

    tables_qs = DiningTable.objects.filter(tenant=tenant).select_related('store').order_by('store__name', 'display_order', 'id')
    if selected_store.isdigit():
        tables_qs = tables_qs.filter(store_id=int(selected_store))

    form = DiningTableForm(request.POST or None, tenant=tenant)
    open_create_modal = False
    if request.method == 'POST':
        if form.is_valid():
            table = form.save(commit=False)
            table.tenant = tenant
            table.save()
            messages.success(request, f'Đã tạo bàn "{table.name}".')
            return redirect('App_Quanly:qr_tables')
        messages.error(request, 'Không thể tạo bàn QR, vui lòng kiểm tra dữ liệu.')
        open_create_modal = True

    table_rows = [
        {
            'table': table,
            'qr_url': _build_table_qr_url(request, tenant_slug=tenant.public_slug, table=table),
        }
        for table in tables_qs
    ]

    return render(
        request,
        'App_Quanly/qr_tables.html',
        {
            'stores': stores,
            'selected_store': selected_store,
            'form': form,
            'table_rows': table_rows,
            'open_create_modal': open_create_modal,
        },
    )


@manager_required
def qr_table_edit(request, pk):
    tenant = _tenant_or_404(request.user)
    table = get_object_or_404(DiningTable, pk=pk, tenant=tenant)
    if request.method != 'POST':
        return redirect('App_Quanly:qr_tables')
    form = DiningTableForm(request.POST, instance=table, tenant=tenant)
    if form.is_valid():
        table = form.save()
        messages.success(request, f'Đã cập nhật bàn "{table.name}".')
    else:
        messages.error(request, 'Không thể cập nhật bàn QR, vui lòng kiểm tra dữ liệu.')
    return redirect('App_Quanly:qr_tables')


@manager_required
@require_POST
def qr_table_delete(request, pk):
    tenant = _tenant_or_404(request.user)
    table = get_object_or_404(DiningTable, pk=pk, tenant=tenant)
    table.delete()
    messages.success(request, 'Đã xóa bàn QR.')
    return redirect('App_Quanly:qr_tables')


@manager_required
@require_POST
def qr_table_reset_token(request, pk):
    tenant = _tenant_or_404(request.user)
    table = get_object_or_404(DiningTable, pk=pk, tenant=tenant)

    new_token = generate_qr_token()
    while DiningTable.objects.filter(qr_token=new_token).exclude(pk=table.pk).exists():
        new_token = generate_qr_token()

    table.qr_token = new_token
    table.save(update_fields=['qr_token', 'updated_at'])
    messages.success(request, f'Đã reset token QR cho bàn "{table.name}".')
    return redirect('App_Quanly:qr_tables')


@manager_required
def qr_table_png(request, pk):
    tenant = _tenant_or_404(request.user)
    table = get_object_or_404(DiningTable.objects.select_related('store'), pk=pk, tenant=tenant)
    qr_url = _build_table_qr_url(request, tenant_slug=tenant.public_slug, table=table)
    png_buffer = _build_qr_png_buffer(qr_url=qr_url)
    filename = f'qr-{table.store.slug}-{table.code}.png'
    return FileResponse(png_buffer, as_attachment=True, filename=filename, content_type='image/png')


@manager_required
def qr_tables_store_pdf(request):
    tenant = _tenant_or_404(request.user)
    store_id = (request.GET.get('store') or '').strip()
    if not store_id.isdigit():
        return HttpResponse('Thiếu store hợp lệ để in PDF.', status=400)

    store = get_object_or_404(Store, pk=int(store_id), tenant=tenant, is_active=True)
    tables = list(
        DiningTable.objects.filter(tenant=tenant, store=store).order_by('display_order', 'id')
    )
    if not tables:
        return HttpResponse('Cửa hàng chưa có bàn để in PDF.', status=400)

    page_size = landscape(A3)
    page_width, page_height = page_size
    cols = 5
    rows = 3
    margin_x = 10 * mm
    margin_y = 14 * mm
    cell_w = (page_width - margin_x * 2) / cols
    cell_h = (page_height - margin_y * 2) / rows

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=page_size)
    now_label = timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M')

    per_page = cols * rows  # 15 bàn / trang
    for index, table in enumerate(tables):
        slot = index % (cols * rows)
        if slot == 0:
            if index > 0:
                pdf.showPage()
            page_no = (index // per_page) + 1
            total_pages = (len(tables) + per_page - 1) // per_page
            pdf.setFont('Helvetica-Bold', 15)
            pdf.drawString(margin_x, page_height - 8 * mm, f'QR bàn - {store.name}')
            pdf.setFont('Helvetica', 9)
            pdf.drawRightString(page_width - margin_x, page_height - 8 * mm, f'{now_label} | Trang {page_no}/{total_pages}')

        row = slot // cols
        col = slot % cols
        x = margin_x + col * cell_w
        y = page_height - margin_y - (row + 1) * cell_h

        qr_url = _build_table_qr_url(request, tenant_slug=tenant.public_slug, table=table)
        qr_png = _build_qr_png_buffer(qr_url=qr_url, box_size=8, border=2)
        qr_reader = ImageReader(qr_png)

        title_y = y + cell_h - 6 * mm
        code_y = title_y - 5 * mm
        max_qr_h = code_y - (y + 4 * mm) - 2 * mm
        max_qr_w = cell_w * 0.68
        qr_size = min(max_qr_w, max_qr_h)
        qr_x = x + (cell_w - qr_size) / 2
        qr_y = code_y - 2 * mm - qr_size
        pdf.drawImage(qr_reader, qr_x, qr_y, width=qr_size, height=qr_size, preserveAspectRatio=True, mask='auto')

        pdf.setFont('Helvetica-Bold', 10)
        pdf.drawCentredString(x + cell_w / 2, title_y, table.name)
        pdf.setFont('Helvetica', 8)
        pdf.drawCentredString(x + cell_w / 2, code_y, f'Mã bàn: {table.code}')

    pdf.save()
    buffer.seek(0)
    filename = f'qr-ban-{store.slug}.pdf'
    return FileResponse(buffer, as_attachment=True, filename=filename, content_type='application/pdf')


@manager_required
def staff_list_create(request):
    tenant = _tenant_or_404(request.user)
    staffs = (
        User.objects.filter(tenant=tenant, role=User.Role.STAFF)
        .prefetch_related('store_accesses__store')
        .order_by('username')
    )
    form = StaffCreateForm(request.POST or None, tenant=tenant)

    if request.method == 'POST' and form.is_valid():
        username = form.cleaned_data['username']
        password = form.cleaned_data['password1']
        selected_stores = list(form.cleaned_data['store_ids'])
        default_store = form.cleaned_data['default_store']

        staff_user = User.objects.create_user(
            username=username,
            password=password,
            tenant=tenant,
            role=User.Role.STAFF,
            is_staff=False,
        )

        for store in selected_stores:
            UserStoreAccess.objects.create(
                user=staff_user,
                store=store,
                is_default=(store.id == default_store.id),
            )
        messages.success(request, f'Đã tạo nhân viên "{staff_user.username}".')
        return redirect('App_Quanly:staffs')

    return render(
        request,
        'App_Quanly/staffs.html',
        {
            'staffs': staffs,
            'form': form,
            'open_create_modal': request.method == 'POST' and form.errors,
        },
    )


@manager_required
def staff_password_reset(request, pk):
    tenant = _tenant_or_404(request.user)
    staff_user = get_object_or_404(User, pk=pk, tenant=tenant, role=User.Role.STAFF)
    if request.method == 'POST':
        form = StaffPasswordResetForm(staff_user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f'Đã cập nhật mật khẩu cho nhân viên "{staff_user.username}".')
        else:
            messages.error(request, f'Không thể cập nhật mật khẩu cho "{staff_user.username}", vui lòng kiểm tra lại dữ liệu.')
        return redirect('App_Quanly:staffs')

    form = StaffPasswordResetForm(staff_user)
    return render(
        request,
        'App_Quanly/staff_password_reset.html',
        {
            'staff_user': staff_user,
            'form': form,
        },
    )
