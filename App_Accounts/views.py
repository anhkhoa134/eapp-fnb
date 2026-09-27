from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    LoginView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.db import IntegrityError
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from App_Accounts import login_throttle, rate_limit
from App_Accounts.forms import (
    POSAuthenticationForm,
    POSPasswordChangeForm,
    POSPasswordResetForm,
    POSSetPasswordForm,
    SignupForm,
)
from App_Accounts.models import User
from App_Tenant.services import get_default_subscription_plan, register_free_tenant


class POSLoginView(LoginView):
    # Không override get_success_url: LoginView tự dùng ?next= (đã kiểm tra host), mặc định LOGIN_REDIRECT_URL.
    template_name = 'App_Accounts/login.html'
    redirect_authenticated_user = True
    authentication_form = POSAuthenticationForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['password_reset_enabled'] = settings.PASSWORD_RESET_ENABLED
        return context


def signup(request):
    if request.user.is_authenticated:
        return redirect('App_Sales:pos')

    form = SignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        ip_address = login_throttle.get_client_ip(request)
        window = timedelta(hours=settings.SIGNUP_WINDOW_HOURS)
        until = rate_limit.limited_until(
            rate_limit.SCOPE_SIGNUP_IP, ip_address, limit=settings.SIGNUP_LIMIT_PER_IP, window=window
        )
        if until:
            form.add_error(None, 'Bạn đã tạo quá nhiều tài khoản trong thời gian ngắn. Vui lòng thử lại sau.')
        else:
            try:
                user = register_free_tenant(
                    store_name=form.cleaned_data['store_name'],
                    username=form.cleaned_data['username'],
                    email=form.cleaned_data['email'],
                    password=form.cleaned_data['password1'],
                )
            except IntegrityError:
                # Hai người gửi cùng lúc: form đã kiểm tra trùng nhưng DB mới là chốt chặn cuối.
                if User.objects.filter(username=form.cleaned_data['username']).exists():
                    form.add_error('username', 'Tên đăng nhập đã tồn tại, vui lòng chọn tên khác.')
                else:
                    form.add_error(None, 'Không tạo được tài khoản, vui lòng thử lại.')
            else:
                rate_limit.hit(rate_limit.SCOPE_SIGNUP_IP, ip_address, window=window)
                login(request, user)
                messages.success(request, 'Tạo tài khoản thành công! Hãy thêm món đầu tiên cho thực đơn của bạn.')
                return redirect('App_Quanly:products')

    return render(request, 'App_Accounts/signup.html', {'form': form, 'free_plan': get_default_subscription_plan()})


class PasswordResetEnabledMixin:
    def dispatch(self, request, *args, **kwargs):
        if not settings.PASSWORD_RESET_ENABLED:
            raise Http404
        return super().dispatch(request, *args, **kwargs)


class POSPasswordResetView(PasswordResetEnabledMixin, PasswordResetView):
    template_name = 'App_Accounts/password_reset_form.html'
    email_template_name = 'App_Accounts/emails/password_reset_email.txt'
    subject_template_name = 'App_Accounts/emails/password_reset_subject.txt'
    form_class = POSPasswordResetForm
    success_url = reverse_lazy('App_Accounts:password_reset_done')

    def form_valid(self, form):
        # Chặn dùng form để spam email người khác.
        ip_address = login_throttle.get_client_ip(self.request)
        window = timedelta(hours=1)
        if rate_limit.limited_until(
            rate_limit.SCOPE_PASSWORD_RESET_IP, ip_address, limit=settings.PASSWORD_RESET_LIMIT_PER_IP, window=window
        ):
            form.add_error(None, 'Bạn đã yêu cầu quá nhiều lần. Vui lòng thử lại sau 1 giờ.')
            return self.form_invalid(form)
        rate_limit.hit(rate_limit.SCOPE_PASSWORD_RESET_IP, ip_address, window=window)
        return super().form_valid(form)


class POSPasswordResetDoneView(PasswordResetEnabledMixin, PasswordResetDoneView):
    template_name = 'App_Accounts/password_reset_done.html'


class POSPasswordResetConfirmView(PasswordResetEnabledMixin, PasswordResetConfirmView):
    template_name = 'App_Accounts/password_reset_confirm.html'
    form_class = POSSetPasswordForm
    success_url = reverse_lazy('App_Accounts:password_reset_complete')


class POSPasswordResetCompleteView(PasswordResetEnabledMixin, PasswordResetCompleteView):
    template_name = 'App_Accounts/password_reset_complete.html'


@require_POST
@login_required
def pos_logout(request):
    logout(request)
    return redirect('App_Accounts:login')


@login_required
def password_change(request):
    next_url = request.POST.get('next') or request.GET.get('next') or reverse_lazy('App_Sales:pos')
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_url = reverse_lazy('App_Sales:pos')

    if request.method == 'POST':
        form = POSPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, 'Đổi mật khẩu thành công.')
            return redirect(next_url)
        messages.error(request, 'Đổi mật khẩu thất bại. Vui lòng kiểm tra lại thông tin.')
    else:
        form = POSPasswordChangeForm(request.user)

    return render(
        request,
        'App_Accounts/password_change.html',
        {
            'form': form,
            'next_url': next_url,
        },
    )
