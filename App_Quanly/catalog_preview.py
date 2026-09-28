"""Read-only catalog import plans, shared by preview and confirmation."""
from collections import defaultdict
import hashlib
import json
import re
import unicodedata
from decimal import InvalidOperation

from django.core.serializers.json import DjangoJSONEncoder

from App_Catalog.models import Category, Product, ProductUnit, ProductTopping, StoreCategory, StoreProduct, Topping
from App_Tenant.models import Store
from App_Quanly.catalog_excel import (
    SHEET_DANH_MUC, SHEET_SAN_PHAM, SHEET_DON_VI, SHEET_TOPPING, SHEET_SAN_PHAM_TOPPING,
    parse_decimal_cell,
)


def catalog_state_fingerprint(tenant):
    """Invalidate a confirmation if catalog, store settings or quota changed since scanning."""
    querysets = [
        Category.objects.filter(tenant=tenant), Product.objects.filter(tenant=tenant),
        ProductUnit.objects.filter(product__tenant=tenant), Topping.objects.filter(tenant=tenant),
        ProductTopping.objects.filter(product__tenant=tenant),
        StoreCategory.objects.filter(category__tenant=tenant), StoreProduct.objects.filter(product__tenant=tenant),
        Store.objects.filter(tenant=tenant),
    ]
    state = [tenant.max_products, *[list(qs.order_by('pk').values()) for qs in querysets]]
    return hashlib.sha256(json.dumps(state, cls=DjangoJSONEncoder, sort_keys=True).encode()).hexdigest()


def build_catalog_preview(tenant, sheets, compact, errors, ignored_sheets):
    categories = defaultdict(list)
    products = defaultdict(list)
    products_by_name = defaultdict(list)
    units = {}
    toppings = defaultdict(list)
    mappings = {}
    active_store_ids = set(Store.objects.filter(tenant=tenant, is_active=True).values_list('pk', flat=True))
    category_stores, product_stores = defaultdict(set), defaultdict(set)
    for category_id, store_id in StoreCategory.objects.filter(category__tenant=tenant, is_visible=True).values_list('category_id', 'store_id'):
        category_stores[category_id].add(store_id)
    for product_id, store_id in StoreProduct.objects.filter(product__tenant=tenant, is_available=True).values_list('product_id', 'store_id'):
        product_stores[product_id].add(store_id)
    custom_prices = set(StoreProduct.objects.filter(product__tenant=tenant, custom_price__isnull=False).values_list('product_id', flat=True))
    for category in Category.objects.filter(tenant=tenant):
        categories[category.name].append(category)
    for product in Product.objects.filter(tenant=tenant).select_related('category'):
        products[(product.category.name if product.category else '', product.name)].append(product)
        products_by_name[product.name].append(product)
    for unit in ProductUnit.objects.filter(product__tenant=tenant):
        units[(unit.product_id, unit.name)] = unit
    for topping in Topping.objects.filter(tenant=tenant):
        toppings[topping.name].append(topping)
    for mapping in ProductTopping.objects.filter(product__tenant=tenant):
        mappings[(mapping.product_id, mapping.topping_id)] = mapping

    row_errors = defaultdict(list)
    for error in errors:
        match = re.match(r'^(\S+) dòng (\d+):\s*(.*)', error)
        if match:
            row_errors[(match[1], int(match[2]))].append(match[3])
    warnings = []
    if ignored_sheets:
        warnings.append('Bỏ qua các sheet không thuộc mẫu: ' + ', '.join(ignored_sheets))
    if not compact or any(rows for name, rows in sheets.items() if name != SHEET_SAN_PHAM):
        warnings.append('File có sheet theo mẫu cũ: các dòng này cập nhật mô tả, trạng thái, cửa hàng theo quy tắc mẫu cũ; cột trống dùng giá trị mặc định. Kiểm tra trước khi nhập.')
    rows = []
    new_categories, new_products = set(), set()
    summary = dict.fromkeys(('create', 'update', 'unchanged', 'error', 'warning'), 0)

    def text(value):
        return str(value).strip() if value is not None else ''

    def similar(value):
        return unicodedata.normalize('NFKC', value).casefold()

    for sheet, data_rows in sheets.items():
        for number, data in data_rows:
            cat_name, prod_name = text(data.get('ten_danh_muc')), text(data.get('ten_san_pham'))
            unit_name, top_name = text(data.get('ten_don_vi')), text(data.get('ten_topping'))
            cat_matches = categories.get(cat_name, [])
            cat = cat_matches[0] if len(cat_matches) == 1 else None
            matches = products.get((cat_name, prod_name), []) if cat_name else products_by_name.get(prod_name, [])
            product = matches[0] if len(matches) == 1 else None
            unit = units.get((product.pk, unit_name)) if product else None
            top_matches = toppings.get(top_name, [])
            topping = top_matches[0] if len(top_matches) == 1 else None
            row = {
                'sheet': sheet, 'row': number, 'category': cat_name, 'product': prod_name,
                'unit': unit_name or top_name, 'old_price': None, 'price': None,
                'action': 'create', 'details': [], 'warnings': [],
                'errors': row_errors.get((sheet, number), []),
            }
            if compact and sheet == SHEET_SAN_PHAM:
                row['details'].append('Danh mục: đã có, giữ nguyên.' if cat else 'Danh mục: tạo mới (chỉ một lần cho các dòng cùng tên).')
                row['details'].append('Sản phẩm: đã có, giữ nguyên.' if product else 'Sản phẩm: tạo mới trong danh mục này.')
                if unit:
                    row['old_price'] = str(unit.price)
                    row['action'] = 'update'
                    row['details'].append('Đơn vị: chỉ cập nhật giá, giữ nguyên thiết lập khác.')
                else:
                    row['details'].append('Đơn vị: tạo mới, mặc định hoạt động.')
                if not cat:
                    new_categories.add(cat_name)
                    if any(similar(name) == similar(cat_name) for name in categories):
                        row['warnings'].append('Có danh mục gần giống tên (khác hoa/thường hoặc Unicode). Tên khác sẽ tạo danh mục riêng.')
                if not product:
                    new_products.add((cat_name, prod_name))
                    if products_by_name.get(prod_name):
                        row['warnings'].append('Tên sản phẩm đã có ở danh mục khác. Sẽ tạo sản phẩm riêng, không chuyển danh mục cũ.')
                    elif any(similar(name) == similar(prod_name) for name in products_by_name):
                        row['warnings'].append('Có sản phẩm gần giống tên. Kiểm tra chính tả; hệ thống không tự gộp tên khác nhau.')
                for label, obj in (('Danh mục', cat), ('Sản phẩm', product), ('Đơn vị', unit)):
                    if obj and not obj.is_active:
                        row['warnings'].append(f'{label} đang tắt và sẽ tiếp tục tắt sau khi nhập.')
                if (cat and active_store_ids - category_stores[cat.pk]) or (product and active_store_ids - product_stores[product.pk]):
                    row['warnings'].append('Có giới hạn hiển thị/bán theo cửa hàng; giữ nguyên giới hạn hiện tại.')
                if product and product.pk in custom_prices:
                    row['warnings'].append('Có giá riêng theo cửa hàng; giá riêng giữ nguyên, chỉ giá đơn vị được cập nhật.')
            else:
                existing = None
                if sheet == SHEET_DANH_MUC:
                    existing = cat
                    row['details'].append('Mẫu cũ: ghi mô tả, trạng thái và cửa hàng; cột trống dùng mặc định.')
                    if not cat:
                        new_categories.add(cat_name)
                elif sheet == SHEET_SAN_PHAM:
                    existing = product
                    row['details'].append('Mẫu cũ: ghi mô tả, trạng thái và cửa hàng; cột trống dùng mặc định.')
                    if not product:
                        new_products.add((cat_name, prod_name))
                elif sheet == SHEET_DON_VI:
                    existing = unit
                    row['details'].append('Mẫu cũ: ghi giá và trạng thái đơn vị.')
                elif sheet == SHEET_TOPPING:
                    existing = topping
                    row['details'].append('Mẫu cũ: ghi tên và trạng thái topping.')
                elif sheet == SHEET_SAN_PHAM_TOPPING:
                    existing = mappings.get((product.pk, topping.pk)) if product and topping else None
                    row['details'].append('Mẫu cũ: ghi giá thêm và trạng thái gán topping.')
                row['action'] = 'update' if existing else 'create'
                if existing and sheet in (SHEET_DON_VI, SHEET_SAN_PHAM_TOPPING):
                    row['old_price'] = str(existing.price)
            price_column = 'gia_them' if sheet == SHEET_SAN_PHAM_TOPPING else 'gia'
            if price_column in data:
                try:
                    price = parse_decimal_cell(data[price_column])
                    row['price'] = str(price) if price.is_finite() else text(data[price_column])
                    if compact and sheet == SHEET_SAN_PHAM and unit and price == unit.price:
                        row['action'] = 'unchanged'
                        row['details'][-1] = 'Đơn vị: giá giống hiện tại, không thay đổi.'
                except (ValueError, InvalidOperation):
                    row['price'] = text(data[price_column])
            if row['errors']:
                row['action'] = 'error'
            summary[row['action']] += 1
            if row['warnings']:
                summary['warning'] += 1
            rows.append(row)
    summary.update(total=len(rows), categories_new=len(new_categories - {''}), products_new=len(new_products))
    return {
        'ok': not errors, 'errors': list(dict.fromkeys(errors)), 'warnings': warnings,
        'rows': rows, 'summary': summary, 'compact': compact,
        'message': 'Quét xong. Chưa ghi dữ liệu.' if not errors else 'File có lỗi. Chưa ghi dữ liệu; hãy sửa file rồi chọn lại.',
    }
