from datetime import datetime, time
from io import BytesIO
from decimal import Decimal
from urllib.parse import urlencode

import qrcode
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q, Sum
from django.db.models.functions import Coalesce
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from App_Accounts.models import User
from App_Accounts.permissions import manager_required
from App_Catalog.models import Category, Product, ProductTopping, ProductUnit, StoreCategory, StoreProduct, Topping
from App_Quanly.forms import (
    CategoryForm,
    DiningTableForm,
    ProductForm,
    ProductToppingForm,
    ProductUnitForm,
    StaffCreateForm,
    StaffPasswordResetForm,
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

    orders = Order.objects.filter(tenant=tenant, status=Order.Status.COMPLETED)

    store_id = request.GET.get('store')
    if store_id and store_id.isdigit():
        orders = orders.filter(store_id=int(store_id))

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

    recent_orders = orders.select_related('store', 'cashier').order_by('-created_at')[:10]

    context = {
        'stores': stores,
        'selected_store': int(store_id) if store_id and store_id.isdigit() else None,
        'date_from': date_from or '',
        'date_to': date_to or '',
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'avg_order_value': avg_order_value,
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
def category_list_create(request):
    tenant = _tenant_or_404(request.user)
    categories = Category.objects.filter(tenant=tenant).order_by('name')
    form = CategoryForm(request.POST or None, tenant=tenant)

    if request.method == 'POST' and form.is_valid():
        category = form.save(commit=False)
        category.tenant = tenant
        category.save()
        selected_store_ids = set(form.cleaned_data['store_ids'].values_list('id', flat=True))
        _sync_category_store_links(category, selected_store_ids)
        messages.success(request, 'Đã tạo danh mục.')
        return redirect('App_Quanly:categories')

    return render(
        request,
        'App_Quanly/categories.html',
        {
            'categories': categories,
            'form': form,
        },
    )


@manager_required
def category_edit(request, pk):
    tenant = _tenant_or_404(request.user)
    category = get_object_or_404(Category, pk=pk, tenant=tenant)
    initial_store_ids = category.store_links.filter(is_visible=True).values_list('store_id', flat=True)

    form = CategoryForm(request.POST or None, instance=category, tenant=tenant, initial={'store_ids': initial_store_ids})
    if request.method == 'POST' and form.is_valid():
        category = form.save()
        selected_store_ids = set(form.cleaned_data['store_ids'].values_list('id', flat=True))
        _sync_category_store_links(category, selected_store_ids)
        messages.success(request, 'Đã cập nhật danh mục.')
        return redirect('App_Quanly:categories')

    return render(request, 'App_Quanly/category_edit.html', {'form': form, 'category': category})


@manager_required
@require_POST
def category_delete(request, pk):
    tenant = _tenant_or_404(request.user)
    category = get_object_or_404(Category, pk=pk, tenant=tenant)
    category.delete()
    messages.success(request, 'Đã xóa danh mục.')
    return redirect('App_Quanly:categories')


@manager_required
def product_list_create(request):
    tenant = _tenant_or_404(request.user)
    products = Product.objects.filter(tenant=tenant).select_related('category').prefetch_related('units').order_by('name')
    form = ProductForm(request.POST or None, tenant=tenant)

    if request.method == 'POST' and form.is_valid():
        product = form.save(commit=False)
        product.tenant = tenant
        product.save()
        selected_store_ids = set(form.cleaned_data['store_ids'].values_list('id', flat=True))
        _sync_product_store_links(product, selected_store_ids)
        messages.success(request, 'Đã tạo sản phẩm. Hãy thêm đơn vị bán ở bên dưới.')
        return redirect('App_Quanly:products')

    return render(
        request,
        'App_Quanly/products.html',
        {
            'products': products,
            'form': form,
            'unit_form': ProductUnitForm(),
        },
    )


@manager_required
def product_edit(request, pk):
    tenant = _tenant_or_404(request.user)
    product = get_object_or_404(Product, pk=pk, tenant=tenant)
    initial_store_ids = product.store_links.filter(is_available=True).values_list('store_id', flat=True)

    form = ProductForm(request.POST or None, instance=product, tenant=tenant, initial={'store_ids': initial_store_ids})
    if request.method == 'POST' and form.is_valid():
        product = form.save()
        selected_store_ids = set(form.cleaned_data['store_ids'].values_list('id', flat=True))
        _sync_product_store_links(product, selected_store_ids)
        messages.success(request, 'Đã cập nhật sản phẩm.')
        return redirect('App_Quanly:products')

    return render(request, 'App_Quanly/product_edit.html', {'form': form, 'product': product})


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
    form = ProductUnitForm(request.POST or None, instance=unit)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Đã cập nhật đơn vị sản phẩm.')
        return redirect('App_Quanly:products')
    return render(request, 'App_Quanly/unit_edit.html', {'form': form, 'unit': unit})


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
        elif form_type == 'mapping':
            mapping_form = ProductToppingForm(request.POST, prefix='mapping', tenant=tenant)
            if mapping_form.is_valid():
                mapping = mapping_form.save()
                messages.success(request, f'Đã gán topping "{mapping.topping.name}" cho "{mapping.product.name}".')
                return redirect('App_Quanly:toppings')
            messages.error(request, 'Không thể gán topping cho sản phẩm, vui lòng kiểm tra dữ liệu.')

    return render(
        request,
        'App_Quanly/toppings.html',
        {
            'toppings': toppings,
            'mappings': mappings,
            'topping_form': topping_form,
            'mapping_form': mapping_form,
        },
    )


@manager_required
def topping_edit(request, pk):
    tenant = _tenant_or_404(request.user)
    topping = get_object_or_404(Topping, pk=pk, tenant=tenant)
    form = ToppingForm(request.POST or None, instance=topping)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Đã cập nhật topping.')
        return redirect('App_Quanly:toppings')
    return render(request, 'App_Quanly/topping_edit.html', {'form': form, 'topping': topping})


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
    form = ProductToppingForm(request.POST or None, instance=mapping, tenant=tenant)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Đã cập nhật gán topping sản phẩm.')
        return redirect('App_Quanly:toppings')
    return render(request, 'App_Quanly/product_topping_edit.html', {'form': form, 'mapping': mapping})


@manager_required
@require_POST
def product_topping_delete(request, pk):
    tenant = _tenant_or_404(request.user)
    mapping = get_object_or_404(ProductTopping, pk=pk, product__tenant=tenant)
    mapping.delete()
    messages.success(request, 'Đã xóa gán topping khỏi sản phẩm.')
    return redirect('App_Quanly:toppings')


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
    if request.method == 'POST':
        if form.is_valid():
            table = form.save(commit=False)
            table.tenant = tenant
            table.save()
            messages.success(request, f'Đã tạo bàn "{table.name}".')
            return redirect('App_Quanly:qr_tables')
        messages.error(request, 'Không thể tạo bàn QR, vui lòng kiểm tra dữ liệu.')

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
        },
    )


@manager_required
def qr_table_edit(request, pk):
    tenant = _tenant_or_404(request.user)
    table = get_object_or_404(DiningTable, pk=pk, tenant=tenant)

    form = DiningTableForm(request.POST or None, instance=table, tenant=tenant)
    if request.method == 'POST':
        if form.is_valid():
            table = form.save()
            messages.success(request, f'Đã cập nhật bàn "{table.name}".')
            return redirect('App_Quanly:qr_tables')
        messages.error(request, 'Không thể cập nhật bàn QR, vui lòng kiểm tra dữ liệu.')

    return render(
        request,
        'App_Quanly/qr_table_edit.html',
        {
            'form': form,
            'table': table,
            'qr_url': _build_table_qr_url(request, tenant_slug=tenant.public_slug, table=table),
        },
    )


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
        },
    )


@manager_required
def staff_password_reset(request, pk):
    tenant = _tenant_or_404(request.user)
    staff_user = get_object_or_404(User, pk=pk, tenant=tenant, role=User.Role.STAFF)
    form = StaffPasswordResetForm(staff_user, request.POST or None)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Đã cập nhật mật khẩu cho nhân viên "{staff_user.username}".')
        return redirect('App_Quanly:staffs')

    return render(
        request,
        'App_Quanly/staff_password_reset.html',
        {
            'staff_user': staff_user,
            'form': form,
        },
    )
