from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache

from App_Core.seed_initial_data_runner import reset_demo_tenant


@never_cache
def demo_seed_reset_confirm(request):
    """Chỉ superuser. Xoá sạch doanh nghiệp demo và seed lại từ đầu."""
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    if not request.user.is_superuser:
        raise PermissionDenied

    if request.method == 'POST':
        reset_demo_tenant()
        messages.success(
            request,
            'Đã xoá sạch và seed lại doanh nghiệp "demo": tài khoản, mật khẩu, cửa hàng, sản phẩm/danh mục, bàn, đơn hàng.',
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
