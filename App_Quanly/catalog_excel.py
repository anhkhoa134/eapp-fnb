"""
Import / export catalog (Category, Product, ProductUnit, Topping, ProductTopping) từ Excel.
"""
from __future__ import annotations

import io
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction
from django.db.models import Max

from App_Catalog.models import Category, Product, ProductTopping, ProductUnit, StoreCategory, StoreProduct, Topping
from App_Tenant.models import Store, Tenant

SHEET_HUONG_DAN = 'Huong_dan'
SHEET_DANH_MUC = 'Danh_muc'
SHEET_SAN_PHAM = 'San_pham'
SHEET_DON_VI = 'Don_vi'
SHEET_TOPPING = 'Topping'
SHEET_SAN_PHAM_TOPPING = 'San_pham_Topping'

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_IMPORT_ROWS = 5000


def _norm_header(val: Any) -> str:
    if val is None:
        return ''
    return str(val).strip().lower().replace(' ', '_')


def _row_is_empty(row: tuple[Any, ...]) -> bool:
    return all(v is None or (isinstance(v, str) and not str(v).strip()) for v in row)


def _iter_sheet_dicts(ws) -> list[tuple[int, dict[str, Any]]]:
    if ws is None:
        return []
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [_norm_header(h) for h in rows[0]]
    out: list[tuple[int, dict[str, Any]]] = []
    for excel_row_idx, row in enumerate(rows[1:], start=2):
        if not row or _row_is_empty(row):
            continue
        d: dict[str, Any] = {}
        for i, key in enumerate(headers):
            if not key:
                continue
            d[key] = row[i] if i < len(row) else None
        out.append((excel_row_idx, d))
    return out


def parse_bool_cell(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return int(value) != 0
    s = str(value).strip().lower()
    if not s:
        return default
    if s in ('0', 'false', 'no', 'off', 'tắt', 'tat', 'không', 'khong'):
        return False
    if s in ('1', 'true', 'yes', 'on', 'có', 'co', 'bật', 'bat'):
        return True
    return default


def parse_decimal_cell(value: Any) -> Decimal:
    if value is None or (isinstance(value, str) and not str(value).strip()):
        raise ValueError('Giá trống')
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    s = str(value).strip().replace(' ', '')
    if not s:
        raise ValueError('Giá trống')
    if ',' in s and '.' in s:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s:
        parts = s.split(',')
        if len(parts) == 2 and len(parts[1]) <= 2 and parts[1].isdigit():
            int_part = parts[0].replace('.', '')
            s = f'{int_part}.{parts[1]}'
        else:
            s = s.replace(',', '')
    else:
        if re.fullmatch(r'\d{1,3}(\.\d{3})+', s):
            s = s.replace('.', '')
        elif s.count('.') == 1 and s.split('.')[-1].isdigit() and len(s.split('.')[-1]) <= 2:
            pass
        elif s.count('.') > 1:
            s = s.replace('.', '')
    return Decimal(s)


def resolve_store_ids(tenant: Tenant, raw: Any, stores: list[Store]) -> set[int]:
    all_ids = {s.id for s in stores}
    if raw is None:
        return all_ids
    s = str(raw).strip()
    if not s or s == '*':
        return all_ids
    parts = re.split(r'[,;]', s)
    chosen: set[int] = set()
    for p in parts:
        name = p.strip()
        if not name:
            continue
        if name == '*':
            return all_ids
        lower = name.lower()
        matches = [st for st in stores if st.name.strip().lower() == lower]
        if len(matches) != 1:
            raise ValueError(f'Cửa hàng không xác định: "{name}"')
        chosen.add(matches[0].id)
    return chosen if chosen else all_ids


def sync_category_store_links(category: Category, selected_store_ids: set[int]) -> None:
    all_store_ids = list(Store.objects.filter(tenant=category.tenant).values_list('id', flat=True))
    for store_id in all_store_ids:
        link, _ = StoreCategory.objects.get_or_create(store_id=store_id, category=category)
        link.is_visible = store_id in selected_store_ids
        link.save(update_fields=['is_visible', 'updated_at'])


def sync_product_store_links(product: Product, selected_store_ids: set[int]) -> None:
    all_store_ids = list(Store.objects.filter(tenant=product.tenant).values_list('id', flat=True))
    for store_id in all_store_ids:
        link, _ = StoreProduct.objects.get_or_create(store_id=store_id, product=product)
        link.is_available = store_id in selected_store_ids
        link.save(update_fields=['is_available', 'updated_at'])


def _categories_by_name(tenant: Tenant, name: str) -> list[Category]:
    return list(Category.objects.filter(tenant=tenant, name=name))


def _toppings_by_name(tenant: Tenant, name: str) -> list[Topping]:
    return list(Topping.objects.filter(tenant=tenant, name=name))


def _product_key(cat_name: str, prod_name: str) -> tuple[str, str]:
    return (cat_name.strip(), prod_name.strip())


def resolve_product_qs(tenant: Tenant, cat_name: str, prod_name: str):
    pn = prod_name.strip()
    cn = cat_name.strip()
    if cn:
        return Product.objects.filter(tenant=tenant, name=pn, category__name=cn)
    qs = Product.objects.filter(tenant=tenant, name=pn)
    return qs


def _style_data_sheet_header(ws, column_widths: list[float]) -> None:
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    for cell in ws[1]:
        cell.font = Font(bold=True)
    for idx, width in enumerate(column_widths, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width


def build_template_workbook():
    from openpyxl import Workbook
    from openpyxl.comments import Comment

    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_SAN_PHAM
    ws.append(['ten_danh_muc', 'ten_san_pham', 'ten_don_vi', 'gia'])
    for row in [
        ['Đồ uống', 'Cà phê sữa', 'Ly nhỏ', 25000],
        ['Đồ uống', 'Cà phê sữa', 'Ly lớn', 30000],
        ['Món ăn', 'Cơm tấm sườn', 'Phần', 55000],
    ]:
        ws.append(row)
    _style_data_sheet_header(ws, [26, 32, 22, 18])
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions
    notes = [
        'Bắt buộc. Danh mục chưa có sẽ được tạo tự động.',
        'Bắt buộc. Mỗi đơn vị một dòng; lặp lại danh mục và tên sản phẩm khi có nhiều đơn vị.',
        'Bắt buộc. Ví dụ: Ly, Ly nhỏ, Ly lớn, Phần.',
        'Bắt buộc. Giá bán bằng VND, từ 0 trở lên. Ví dụ: 25000.',
    ]
    for cell, note in zip(ws[1], notes):
        cell.comment = Comment(
            note + ' Sửa hoặc xóa các dòng mẫu trước khi nhập. '
            'Dữ liệu mới mặc định hoạt động, áp dụng mọi cửa hàng đang hoạt động. '
            'Dòng đã có chỉ cập nhật giá; các thiết lập khác được giữ nguyên.',
            'eApp FnB',
        )
    for row in ws.iter_rows(min_row=2, min_col=4, max_col=4):
        row[0].number_format = '#,##0.##'
    return wb


def template_workbook_bytes() -> bytes:
    buf = io.BytesIO()
    wb = build_template_workbook()
    wb.save(buf)
    return buf.getvalue()


def next_display_order(queryset) -> int:
    """display_order cho bản ghi mới: xếp cuối nhóm."""
    current = queryset.aggregate(value=Max('display_order'))['value']
    return (current or 0) + 1


class _ProductLimitExceeded(Exception):
    pass


def import_catalog_from_upload(tenant: Tenant, file_obj, *, preview: bool = False) -> dict[str, Any]:
    """
    Validate toàn bộ workbook, sau đó upsert trong một transaction.
    Trả về dict: ok, errors (list str), stats (dict đếm), message (str tóm tắt).
    """
    from openpyxl import load_workbook

    errors: list[str] = []
    stats = {
        'categories_created': 0,
        'categories_updated': 0,
        'products_created': 0,
        'products_updated': 0,
        'products_unchanged': 0,
        'units_created': 0,
        'units_updated': 0,
        'units_unchanged': 0,
        'toppings_created': 0,
        'toppings_updated': 0,
        'mappings_created': 0,
        'mappings_updated': 0,
    }

    stores = list(Store.objects.filter(tenant=tenant, is_active=True).order_by('name'))
    if not stores:
        return {
            'ok': False,
            'errors': ['Tenant chưa có cửa hàng hoạt động.'],
            'stats': stats,
            'message': '',
        }

    try:
        wb = load_workbook(file_obj, read_only=True, data_only=False)
    except Exception:
        return {
            'ok': False,
            'errors': ['Không đọc được file Excel. Hãy kiểm tra file và lưu lại dưới dạng .xlsx.'],
            'stats': stats,
            'message': '',
        }

    def sheet_dicts(name: str) -> list[tuple[int, dict[str, Any]]]:
        if name not in wb.sheetnames:
            return []
        return _iter_sheet_dicts(wb[name])

    supported = (SHEET_DANH_MUC, SHEET_SAN_PHAM, SHEET_DON_VI, SHEET_TOPPING, SHEET_SAN_PHAM_TOPPING)
    raw_rows = {}
    headers_by_sheet = {}
    try:
        for name in supported:
            if name not in wb.sheetnames:
                raw_rows[name] = []
                continue
            ws = wb[name]
            if ws.max_row and ws.max_row > MAX_IMPORT_ROWS + 1:
                errors.append(f'{name}: tối đa {MAX_IMPORT_ROWS} dòng. Hãy chia nhỏ file.')
                raw_rows[name] = []
                continue
            headers = [_norm_header(value) for value in next(ws.iter_rows(values_only=True), ())]
            headers_by_sheet[name] = set(headers)
            if len([h for h in headers if h]) != len(set(h for h in headers if h)):
                errors.append(f'{name}: trùng tên cột. Mỗi cột chỉ xuất hiện một lần.')
            raw_rows[name] = sheet_dicts(name)
            for r, data in raw_rows[name]:
                for column, value in data.items():
                    if isinstance(value, str) and value.startswith('='):
                        errors.append(f'{name} dòng {r}: {column} chứa công thức; hãy dán giá trị thay cho công thức.')
        ignored_sheets = [name for name in wb.sheetnames if name not in supported and name != SHEET_HUONG_DAN]
    except Exception:
        return {'ok': False, 'errors': ['Không đọc được dữ liệu trong file Excel. Hãy lưu lại dưới dạng .xlsx.'], 'stats': stats, 'message': ''}
    finally:
        wb.close()
    rows_dm = list(raw_rows[SHEET_DANH_MUC])
    rows_sp = list(raw_rows[SHEET_SAN_PHAM])
    rows_dv = list(raw_rows[SHEET_DON_VI])
    rows_tp = list(raw_rows[SHEET_TOPPING])
    rows_spt = list(raw_rows[SHEET_SAN_PHAM_TOPPING])
    product_headers = headers_by_sheet.get(SHEET_SAN_PHAM, set())
    compact = bool({'ten_don_vi', 'gia'} & product_headers) or (
        SHEET_SAN_PHAM in headers_by_sheet
        and not ({'mo_ta', 'hoat_dong', 'cua_hang'} & product_headers)
        and not any((rows_dm, rows_dv, rows_tp, rows_spt))
    )
    unit_sheet = SHEET_SAN_PHAM if compact else SHEET_DON_VI
    required_headers = {
        SHEET_DANH_MUC: ('ten_danh_muc',),
        SHEET_SAN_PHAM: ('ten_danh_muc', 'ten_san_pham', 'ten_don_vi', 'gia') if compact else ('ten_san_pham',),
        SHEET_DON_VI: ('ten_san_pham', 'ten_don_vi', 'gia'),
        SHEET_TOPPING: ('ten_topping',),
        SHEET_SAN_PHAM_TOPPING: ('ten_san_pham', 'ten_topping', 'gia_them'),
    }
    for sheet_name, headers in headers_by_sheet.items():
        missing = [col for col in required_headers[sheet_name] if col not in headers]
        if missing:
            errors.append(f'{sheet_name}: thiếu cột {", ".join(missing)}')
        for r, data in raw_rows[sheet_name]:
            for col, max_length in (('ten_danh_muc', 120), ('ten_san_pham', 180), ('ten_don_vi', 120), ('ten_topping', 140)):
                if data.get(col) is not None and len(str(data[col]).strip()) > max_length:
                    errors.append(f'{sheet_name} dòng {r}: {col} tối đa {max_length} ký tự')
    if not any((rows_dm, rows_sp, rows_dv, rows_tp, rows_spt)):
        errors.append('File không có dữ liệu để nhập. Hãy điền sheet San_pham theo mẫu.')
    if compact:
        if rows_dv:
            errors.append('Đã nhập đơn vị và giá trong San_pham thì không dùng thêm sheet Don_vi.')
        rows_dv = rows_sp
        rows_sp = []
        compact_products = set()
        category_names = {str(d.get('ten_danh_muc') or '').strip() for _, d in rows_dm}
        for r, d in rows_dv:
            for col in ('ten_danh_muc', 'ten_san_pham', 'ten_don_vi'):
                if not str(d.get(col) or '').strip():
                    errors.append(f'{SHEET_SAN_PHAM} dòng {r}: thiếu {col}')
            cat_name = str(d.get('ten_danh_muc') or '').strip()
            prod_name = str(d.get('ten_san_pham') or '').strip()
            if not cat_name or not prod_name:
                continue
            matches = _categories_by_name(tenant, cat_name)
            if len(matches) > 1:
                errors.append(f'{SHEET_SAN_PHAM} dòng {r}: nhiều danh mục trùng tên "{cat_name}" trong DB')
            if not matches and cat_name not in category_names:
                rows_dm.append((r, {'ten_danh_muc': cat_name}))
                category_names.add(cat_name)
            key = _product_key(cat_name, prod_name)
            if key not in compact_products:
                rows_sp.append((r, {'ten_danh_muc': cat_name, 'ten_san_pham': prod_name}))
                compact_products.add(key)

    names_in_dm_file: set[str] = set()
    for r, d in rows_dm:
        tn = d.get('ten_danh_muc')
        if tn is None or not str(tn).strip():
            errors.append(f'{SHEET_DANH_MUC} dòng {r}: thiếu ten_danh_muc')
            continue
        name = str(tn).strip()
        if name in names_in_dm_file:
            errors.append(f'{SHEET_DANH_MUC} dòng {r}: trùng ten_danh_muc "{name}" trong file')
        names_in_dm_file.add(name)
        try:
            resolve_store_ids(tenant, d.get('cua_hang'), stores)
        except ValueError as e:
            errors.append(f'{SHEET_DANH_MUC} dòng {r}: {e}')
        amb = _categories_by_name(tenant, name)
        if len(amb) > 1:
            errors.append(f'{SHEET_DANH_MUC} dòng {r}: nhiều danh mục trùng tên "{name}" trong DB')

    seen_products: set[tuple[str, str]] = set()
    for r, d in rows_sp:
        tdm = d.get('ten_danh_muc')
        tsp = d.get('ten_san_pham')
        cat_name = str(tdm).strip() if tdm is not None and str(tdm).strip() else ''
        if tsp is None or not str(tsp).strip():
            errors.append(f'{SHEET_SAN_PHAM} dòng {r}: thiếu ten_san_pham')
            continue
        prod_name = str(tsp).strip()
        key = _product_key(cat_name, prod_name)
        if key in seen_products:
            errors.append(f'{SHEET_SAN_PHAM} dòng {r}: trùng cặp (ten_danh_muc, ten_san_pham)')
        seen_products.add(key)
        if cat_name:
            if not Category.objects.filter(tenant=tenant, name=cat_name).exists() and cat_name not in names_in_dm_file:
                errors.append(
                    f'{SHEET_SAN_PHAM} dòng {r}: không có danh mục "{cat_name}" (trong DB hoặc sheet {SHEET_DANH_MUC})'
                )
        else:
            qn = resolve_product_qs(tenant, '', prod_name)
            c = qn.count()
            if c > 1:
                errors.append(
                    f'{SHEET_SAN_PHAM} dòng {r}: ten_san_pham "{prod_name}" không gắn danh mục nhưng có {c} sản phẩm trùng tên — cần ten_danh_muc'
                )
        if resolve_product_qs(tenant, cat_name, prod_name).count() > 1:
            errors.append(f'{SHEET_SAN_PHAM} dòng {r}: nhiều sản phẩm trùng tên trong cùng danh mục; hãy xử lý trùng trước khi nhập.')
        if cat_name and len(_categories_by_name(tenant, cat_name)) > 1:
            errors.append(f'{SHEET_SAN_PHAM} dòng {r}: nhiều danh mục trùng tên "{cat_name}" trong DB')
        try:
            resolve_store_ids(tenant, d.get('cua_hang'), stores)
        except ValueError as e:
            errors.append(f'{SHEET_SAN_PHAM} dòng {r}: {e}')

    seen_units: set[tuple[str, str, str]] = set()
    for r, d in rows_dv:
        for col in ('ten_san_pham', 'ten_don_vi'):
            if d.get(col) is None or not str(d.get(col)).strip():
                errors.append(f'{unit_sheet} dòng {r}: thiếu {col}')
                break
        else:
            tdm = d.get('ten_danh_muc')
            cat_name = str(tdm).strip() if tdm is not None and str(tdm).strip() else ''
            prod_name = str(d.get('ten_san_pham')).strip()
            unit_name = str(d.get('ten_don_vi')).strip()
            uk = (cat_name, prod_name, unit_name)
            if uk in seen_units:
                errors.append(f'{unit_sheet} dòng {r}: trùng bộ (ten_danh_muc, ten_san_pham, ten_don_vi)')
            seen_units.add(uk)
            qs = resolve_product_qs(tenant, cat_name, prod_name)
            cnt = qs.count()
            pkey = _product_key(cat_name, prod_name)
            if cnt == 0 and pkey not in seen_products:
                errors.append(
                    f'{unit_sheet} dòng {r}: không tìm thấy sản phẩm ({cat_name or "∅"}, {prod_name}) (DB hoặc sheet {SHEET_SAN_PHAM})'
                )
            elif cnt > 1:
                errors.append(
                    f'{unit_sheet} dòng {r}: nhiều sản phẩm khớp ({cat_name or "∅"}, {prod_name}) — chỉ định ten_danh_muc'
                )
            try:
                price = parse_decimal_cell(d.get('gia'))
                if not price.is_finite() or price < 0 or price >= Decimal('1000000000000'):
                    raise ValueError('Giá phải từ 0 đến dưới 1.000.000.000.000')
                if price != price.quantize(Decimal('0.01')):
                    raise ValueError('Giá chỉ được có tối đa 2 chữ số thập phân')
            except InvalidOperation:
                errors.append(f'{unit_sheet} dòng {r}: gia — Giá không hợp lệ')
            except ValueError as e:
                errors.append(f'{unit_sheet} dòng {r}: gia — {e}')

    seen_top: set[str] = set()
    for r, d in rows_tp:
        tt = d.get('ten_topping')
        if tt is None or not str(tt).strip():
            errors.append(f'{SHEET_TOPPING} dòng {r}: thiếu ten_topping')
            continue
        name = str(tt).strip()
        if name in seen_top:
            errors.append(f'{SHEET_TOPPING} dòng {r}: trùng ten_topping trong file')
        seen_top.add(name)
        amb = _toppings_by_name(tenant, name)
        if len(amb) > 1:
            errors.append(f'{SHEET_TOPPING} dòng {r}: nhiều topping trùng tên "{name}" trong DB')

    seen_map: set[tuple[str, str, str]] = set()
    for r, d in rows_spt:
        tsp = d.get('ten_san_pham')
        ttp = d.get('ten_topping')
        if tsp is None or not str(tsp).strip():
            errors.append(f'{SHEET_SAN_PHAM_TOPPING} dòng {r}: thiếu ten_san_pham')
            continue
        if ttp is None or not str(ttp).strip():
            errors.append(f'{SHEET_SAN_PHAM_TOPPING} dòng {r}: thiếu ten_topping')
            continue
        tdm = d.get('ten_danh_muc')
        cat_name = str(tdm).strip() if tdm is not None and str(tdm).strip() else ''
        prod_name = str(tsp).strip()
        top_name = str(ttp).strip()
        mk = (cat_name, prod_name, top_name)
        if mk in seen_map:
            errors.append(f'{SHEET_SAN_PHAM_TOPPING} dòng {r}: trùng bộ (ten_danh_muc, ten_san_pham, ten_topping)')
        seen_map.add(mk)
        qs = resolve_product_qs(tenant, cat_name, prod_name)
        cnt = qs.count()
        pkey = _product_key(cat_name, prod_name)
        if cnt == 0 and pkey not in seen_products:
            errors.append(
                f'{SHEET_SAN_PHAM_TOPPING} dòng {r}: không tìm thấy sản phẩm ({cat_name or "∅"}, {prod_name}) (DB hoặc sheet {SHEET_SAN_PHAM})'
            )
        elif cnt > 1:
            errors.append(
                f'{SHEET_SAN_PHAM_TOPPING} dòng {r}: nhiều sản phẩm khớp — chỉ định ten_danh_muc'
            )
        if not Topping.objects.filter(tenant=tenant, name=top_name).exists() and top_name not in seen_top:
            if not Topping.objects.filter(tenant=tenant, name=top_name).exists():
                errors.append(
                    f'{SHEET_SAN_PHAM_TOPPING} dòng {r}: không có topping "{top_name}" (DB hoặc sheet {SHEET_TOPPING})'
                )
        if len(_toppings_by_name(tenant, top_name)) > 1:
            errors.append(f'{SHEET_SAN_PHAM_TOPPING} dòng {r}: nhiều topping trùng tên "{top_name}" trong DB')
        try:
            price = parse_decimal_cell(d.get('gia_them'))
            if not price.is_finite() or price < 0 or price >= Decimal('1000000000000') or price != price.quantize(Decimal('0.01')):
                raise ValueError('Giá thêm không hợp lệ')
        except (ValueError, InvalidOperation) as e:
            errors.append(f'{SHEET_SAN_PHAM_TOPPING} dòng {r}: gia_them — {e}')

    new_products = sum(
        not resolve_product_qs(tenant, cat_name, prod_name).exists()
        for cat_name, prod_name in seen_products
    )
    if new_products and tenant.max_products is not None and tenant.product_count() + new_products > tenant.max_products:
        errors.append(
            f'File tạo thêm {new_products} sản phẩm, vượt giới hạn {tenant.max_products} món của gói hiện tại. '
            'Chưa có dữ liệu nào được ghi.'
        )
    if preview:
        from App_Quanly.catalog_preview import build_catalog_preview

        return build_catalog_preview(tenant, raw_rows, compact, errors, ignored_sheets)
    if errors:
        return {'ok': False, 'errors': errors, 'stats': stats, 'message': ''}

    try:
        with transaction.atomic():
            cat_by_name: dict[str, Category] = {c.name: c for c in Category.objects.filter(tenant=tenant)}

            for _, d in rows_dm:
                name = str(d.get('ten_danh_muc')).strip()
                store_ids = resolve_store_ids(tenant, d.get('cua_hang'), stores)
                desc = str(d.get('mo_ta') or '').strip()
                active = parse_bool_cell(d.get('hoat_dong'), default=True)
                if name in cat_by_name:
                    c = cat_by_name[name]
                    c.description = desc
                    c.is_active = active
                    c.save(update_fields=['description', 'is_active', 'updated_at'])
                    stats['categories_updated'] += 1
                else:
                    c = Category(tenant=tenant, name=name, description=desc, is_active=active)
                    c.save()
                    cat_by_name[name] = c
                    stats['categories_created'] += 1
                sync_category_store_links(c, store_ids)

            prod_by_key: dict[tuple[str, str], Product] = {}
            for p in Product.objects.filter(tenant=tenant).select_related('category'):
                cn = p.category.name if p.category_id else ''
                prod_by_key[_product_key(cn, p.name)] = p

            for _, d in rows_sp:
                tdm = d.get('ten_danh_muc')
                cat_name = str(tdm).strip() if tdm is not None and str(tdm).strip() else ''
                prod_name = str(d.get('ten_san_pham')).strip()
                store_ids = resolve_store_ids(tenant, d.get('cua_hang'), stores)
                long_d = str(d.get('mo_ta') or '')
                active = parse_bool_cell(d.get('hoat_dong'), default=True)

                if cat_name:
                    key = _product_key(cat_name, prod_name)
                    cat = cat_by_name.get(cat_name)
                else:
                    qs_list = list(Product.objects.filter(tenant=tenant, name=prod_name))
                    if len(qs_list) == 1:
                        pr0 = qs_list[0]
                        cn0 = pr0.category.name if pr0.category_id else ''
                        key = _product_key(cn0, prod_name)
                        cat = pr0.category
                    else:
                        key = _product_key('', prod_name)
                        cat = None

                product_exists = key in prod_by_key
                if product_exists:
                    pr = prod_by_key[key]
                    if cat_name:
                        pr.category = cat
                    if not compact:
                        pr.description = long_d
                        pr.is_active = active
                    if not compact:
                        pr.save()
                    stats['products_unchanged' if compact else 'products_updated'] += 1
                else:
                    pr = Product(
                        tenant=tenant,
                        category=cat,
                        name=prod_name,
                        description=long_d,
                        is_active=active,
                    )
                    pr.save()
                    prod_by_key[key] = pr
                    stats['products_created'] += 1
                    if tenant.max_products is not None and tenant.product_count() > tenant.max_products:
                        raise _ProductLimitExceeded
                if not compact or not product_exists:
                    sync_product_store_links(pr, store_ids)

            for _, d in rows_dv:
                tdm = d.get('ten_danh_muc')
                cat_name = str(tdm).strip() if tdm is not None and str(tdm).strip() else ''
                prod_name = str(d.get('ten_san_pham')).strip()
                unit_name = str(d.get('ten_don_vi')).strip()
                if cat_name:
                    pr = prod_by_key.get(_product_key(cat_name, prod_name))
                else:
                    qs_list = list(Product.objects.filter(tenant=tenant, name=prod_name))
                    pr = (
                        qs_list[0]
                        if len(qs_list) == 1
                        else prod_by_key.get(_product_key('', prod_name))
                    )
                if pr is None:
                    raise RuntimeError(f'Lỗi nội bộ: không resolve được sản phẩm ({cat_name!r}, {prod_name!r})')
                key = _product_key(
                    pr.category.name if pr.category_id else '',
                    prod_name,
                )
                prod_by_key[key] = pr
                price = parse_decimal_cell(d.get('gia'))
                active = True if compact else parse_bool_cell(d.get('hoat_dong'), default=True)
                unit = ProductUnit.objects.filter(product=pr, name=unit_name).first()
                if unit:
                    changed = unit.price != price or (not compact and unit.is_active != active)
                    unit.price = price
                    if not compact:
                        unit.is_active = active
                    if changed:
                        unit.save(update_fields=['price', 'is_active', 'updated_at'])
                    stats['units_updated' if changed else 'units_unchanged'] += 1
                else:
                    ProductUnit.objects.create(
                        product=pr,
                        name=unit_name,
                        price=price,
                        sku='',
                        display_order=next_display_order(ProductUnit.objects.filter(product=pr)),
                        is_active=active,
                    )
                    stats['units_created'] += 1

            top_by_name: dict[str, Topping] = {t.name: t for t in Topping.objects.filter(tenant=tenant)}

            for _, d in rows_tp:
                name = str(d.get('ten_topping')).strip()
                active = parse_bool_cell(d.get('hoat_dong'), default=True)
                if name in top_by_name:
                    t = top_by_name[name]
                    t.is_active = active
                    t.save(update_fields=['is_active', 'updated_at'])
                    stats['toppings_updated'] += 1
                else:
                    t = Topping(
                        tenant=tenant,
                        name=name,
                        display_order=next_display_order(Topping.objects.filter(tenant=tenant)),
                        is_active=active,
                    )
                    t.save()
                    top_by_name[name] = t
                    stats['toppings_created'] += 1

            for _, d in rows_spt:
                tdm = d.get('ten_danh_muc')
                cat_name = str(tdm).strip() if tdm is not None and str(tdm).strip() else ''
                prod_name = str(d.get('ten_san_pham')).strip()
                top_name = str(d.get('ten_topping')).strip()
                if cat_name:
                    pr = prod_by_key.get(_product_key(cat_name, prod_name))
                else:
                    qs_list = list(Product.objects.filter(tenant=tenant, name=prod_name))
                    pr = (
                        qs_list[0]
                        if len(qs_list) == 1
                        else prod_by_key.get(_product_key('', prod_name))
                    )
                if pr is None:
                    raise RuntimeError(f'Lỗi nội bộ: không resolve được sản phẩm ({cat_name!r}, {prod_name!r})')
                topping = top_by_name[top_name]
                price = parse_decimal_cell(d.get('gia_them'))
                active = parse_bool_cell(d.get('hoat_dong'), default=True)
                m = ProductTopping.objects.filter(product=pr, topping=topping).first()
                if m:
                    m.price = price
                    m.display_order = topping.display_order
                    m.is_active = active
                    m.save(update_fields=['price', 'display_order', 'is_active', 'updated_at'])
                    stats['mappings_updated'] += 1
                else:
                    ProductTopping.objects.create(
                        product=pr,
                        topping=topping,
                        price=price,
                        display_order=topping.display_order,
                        is_active=active,
                    )
                    stats['mappings_created'] += 1
    except _ProductLimitExceeded:
        return {
            'ok': False,
            'errors': [
                f'File vượt giới hạn {tenant.max_products} món của gói hiện tại, chưa có dữ liệu nào được ghi. '
                'Xem các gói nâng cấp ở trang Tài khoản.'
            ],
            'stats': stats,
            'message': '',
        }
    except Exception as exc:
        return {
            'ok': False,
            'errors': [f'Lỗi khi ghi DB: {exc}'],
            'stats': stats,
            'message': '',
        }

    parts = [
        f'DM +{stats["categories_created"]}/~{stats["categories_updated"]}',
        f'SP +{stats["products_created"]}/~{stats["products_updated"]}',
        f'ĐV +{stats["units_created"]}/~{stats["units_updated"]}',
        f'TP +{stats["toppings_created"]}/~{stats["toppings_updated"]}',
        f'Gán +{stats["mappings_created"]}/~{stats["mappings_updated"]}',
    ]
    message = 'Import thành công. ' + ', '.join(parts) + ' (tạo mới/cập nhật).'
    if compact and not any(data for name, data in raw_rows.items() if name != SHEET_SAN_PHAM):
        message = (
            f'Import thành công. Tạo mới {stats["categories_created"]} danh mục, '
            f'{stats["products_created"]} sản phẩm, {stats["units_created"]} đơn vị; '
            f'cập nhật giá {stats["units_updated"]} đơn vị; giữ nguyên {stats["units_unchanged"]} đơn vị.'
        )
    return {'ok': True, 'errors': [], 'stats': stats, 'message': message}
