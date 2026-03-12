from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from App_Accounts.models import User


def role_required(roles):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if request.user.role not in roles:
                raise PermissionDenied('Bạn không có quyền truy cập.')
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


manager_required = role_required([User.Role.MANAGER])
staff_or_manager_required = role_required([User.Role.MANAGER, User.Role.STAFF])
