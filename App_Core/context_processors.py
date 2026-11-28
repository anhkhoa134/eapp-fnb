from django.conf import settings

from App_Tenant.access import subscription_notice


# Tiêu đề tab cho từng trang quản lý; trước đây mọi trang đều là "eApp FnB" (FNB-09).
QUANLY_PAGE_TITLES = {
    'dashboard': 'Tổng quan',
    'orders': 'Lịch sử đơn',
    'categories': 'Danh mục',
    'products': 'Sản phẩm',
    'staffs': 'Nhân viên',
    'staff_password_reset': 'Đặt lại mật khẩu nhân viên',
    'feature_settings': 'Cấu hình tính năng',
    'stores': 'Cửa hàng',
    'customers': 'Khách hàng',
    'promotions': 'Khuyến mãi',
    'toppings': 'Topping',
    'product_toppings': 'Topping theo món',
    'qr_tables': 'QR bàn',
    'ingredients': 'Nguyên liệu',
    'ingredient_usage': 'Tiêu hao nguyên liệu',
    'recipes': 'Định mức NVL',
    'recipe_edit': 'Định mức NVL',
    'audit_log': 'Nhật ký thao tác',
    'payment_qr_settings': 'QR thanh toán',
    'account': 'Tài khoản',
}


def core_context(request):
    context = {
        'app_name': 'eApp FnB',
        'demo_mode': settings.DEMO_MODE,
        'demo_password': settings.DEMO_SEED_DEFAULT_PASSWORD,
    }
    match = getattr(request, 'resolver_match', None)
    user = getattr(request, 'user', None)
    if (
        match is not None
        and match.namespace == 'App_Quanly'
        and user is not None
        and user.is_authenticated
        and user.tenant_id
    ):
        context['subscription_notice'] = subscription_notice(user.tenant)
    if match is not None and match.namespace == 'App_Quanly':
        context['page_title'] = QUANLY_PAGE_TITLES.get(match.url_name, 'Quản lý')
    return context
