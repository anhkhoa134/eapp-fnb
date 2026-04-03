from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect


def _expects_json_response(request):
    accept_header = (request.headers.get('Accept') or '').lower()
    requested_with = (request.headers.get('X-Requested-With') or '').lower()
    return (
        request.path.startswith('/api/')
        or 'application/json' in accept_header
        or requested_with == 'xmlhttprequest'
    )


def build_not_found_response(request):
    if _expects_json_response(request):
        return JsonResponse({'detail': 'Đường dẫn không tồn tại.'}, status=404)

    if request.user.is_authenticated:
        if request.user.is_superuser:
            target = 'admin:index'
            message = 'Không tìm thấy trang. Đã chuyển về trang quản trị.'
        elif getattr(request.user, 'is_manager', False):
            target = 'App_Quanly:dashboard'
            message = 'Không tìm thấy trang. Đã chuyển về dashboard quản lý.'
        else:
            target = 'App_Sales:pos'
            message = 'Không tìm thấy trang. Đã chuyển về POS.'
    else:
        target = 'App_Accounts:login'
        message = 'Không tìm thấy trang. Vui lòng đăng nhập lại.'

    messages.warning(request, message)
    return redirect(target)


def redirect_not_found(request, exception):
    return build_not_found_response(request)
