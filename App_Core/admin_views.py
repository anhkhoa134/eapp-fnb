from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache

from App_Core.seed_initial_data_runner import run_seed_initial_data


@never_cache
def demo_seed_reset_confirm(request):
    """Chỉ superuser. Phục hồi tenant demo về bộ seed ban đầu (mật khẩu, catalog, ảnh, QR cửa hàng)."""
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    if not request.user.is_superuser:
        raise PermissionDenied

    if request.method == 'POST':
        default_password = getattr(settings, 'DEMO_SEED_DEFAULT_PASSWORD', '123456')
        run_seed_initial_data(
            tenant_slug='demo',
            tenant_name='Demo FNB',
            default_password=default_password,
            reset_passwords=True,
            seed_qr_pending=True,
            skip_qr_pending=False,
        )
        messages.success(
            request,
            'Đã phục hồi dữ liệu tenant "demo": mật khẩu tài khoản seed, sản phẩm/danh mục, ảnh mẫu, QR thanh toán cửa hàng, đơn QR pending.',
        )
        return redirect('admin:index')

    return render(
        request,
        'admin/app_core/demo_seed_reset_confirm.html',
        {
            'title': 'Phục hồi dữ liệu demo',
            'default_password': getattr(settings, 'DEMO_SEED_DEFAULT_PASSWORD', '123456'),
        },
    )
