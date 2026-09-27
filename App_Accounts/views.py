from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from App_Accounts.forms import POSAuthenticationForm, POSPasswordChangeForm, SignupForm
from App_Tenant.services import get_default_subscription_plan, register_free_tenant


class POSLoginView(LoginView):
    template_name = 'App_Accounts/login.html'
    redirect_authenticated_user = True
    authentication_form = POSAuthenticationForm

    def get_success_url(self):
        return reverse_lazy('App_Sales:pos')


def signup(request):
    if request.user.is_authenticated:
        return redirect('App_Sales:pos')

    form = SignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = register_free_tenant(
            store_name=form.cleaned_data['store_name'],
            username=form.cleaned_data['username'],
            password=form.cleaned_data['password1'],
        )
        login(request, user)
        messages.success(request, 'Tạo tài khoản thành công! Hãy thêm món đầu tiên cho thực đơn của bạn.')
        return redirect('App_Quanly:products')

    return render(request, 'App_Accounts/signup.html', {'form': form, 'free_plan': get_default_subscription_plan()})


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
