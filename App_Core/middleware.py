from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.http import JsonResponse
from django.shortcuts import redirect

from App_Core.views import build_not_found_response
from App_Tenant.access import (
    BLOCK_TENANT_INACTIVE,
    SUBSCRIPTION_EXPIRED_MESSAGE,
    SUBSCRIPTION_EXPIRED_STAFF_MESSAGE,
    TENANT_INACTIVE_MESSAGE,
    tenant_block_reason,
)


class NotFoundRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code != 404:
            return response
        if request.method not in {'GET', 'HEAD'}:
            return response
        if request.path.startswith(str(settings.STATIC_URL)) or request.path.startswith(str(settings.MEDIA_URL)):
            return response
        if request.path.startswith('/api/'):
            if request.resolver_match is None:
                return build_not_found_response(request)
            return response
        if (
            response.has_header('Content-Type')
            and 'application/json' in response['Content-Type'].lower()
        ):
            return response
        return build_not_found_response(request)


class TenantAccessMiddleware:
    """Chặn POS, API POS và /quanly/ khi doanh nghiệp bị tắt hoặc đã hết hạn gói.

    - Doanh nghiệp tắt: đăng xuất, API trả 403.
    - Hết hạn gói: API POS trả 403; quản lý chỉ được xem /quanly/ (GET) và trang Tài khoản để gia hạn;
      nhân viên bị đăng xuất.
    """

    PROTECTED_NAMESPACES = {'App_Sales', 'App_Sales_API', 'App_Quanly'}
    API_NAMESPACES = {'App_Sales_API'}
    READ_ONLY_WHEN_EXPIRED_NAMESPACES = {'App_Quanly'}
    ALLOWED_WHEN_EXPIRED_VIEWS = {'App_Quanly:account'}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        match = request.resolver_match
        if match is None or match.namespace not in self.PROTECTED_NAMESPACES:
            return None
        user = request.user
        if not user.is_authenticated or not user.tenant_id:
            return None
        reason = tenant_block_reason(user.tenant)
        if reason is None:
            return None

        is_api = match.namespace in self.API_NAMESPACES
        if reason == BLOCK_TENANT_INACTIVE:
            logout(request)
            if is_api:
                return JsonResponse({'detail': TENANT_INACTIVE_MESSAGE, 'code': reason}, status=403)
            messages.error(request, TENANT_INACTIVE_MESSAGE)
            return redirect('App_Accounts:login')

        if is_api:
            return JsonResponse({'detail': SUBSCRIPTION_EXPIRED_MESSAGE, 'code': reason}, status=403)
        if match.view_name in self.ALLOWED_WHEN_EXPIRED_VIEWS:
            return None
        if match.namespace in self.READ_ONLY_WHEN_EXPIRED_NAMESPACES and request.method in {'GET', 'HEAD'}:
            return None
        if not user.is_manager:
            logout(request)
            messages.error(request, SUBSCRIPTION_EXPIRED_STAFF_MESSAGE)
            return redirect('App_Accounts:login')
        messages.error(request, SUBSCRIPTION_EXPIRED_MESSAGE)
        return redirect('App_Quanly:account')
