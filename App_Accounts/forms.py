from datetime import timedelta

from django import forms
from django.conf import settings
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from App_Accounts import login_throttle, rate_limit
from App_Accounts.models import User
from App_Tenant.access import (
    BLOCK_SUBSCRIPTION_EXPIRED,
    BLOCK_TENANT_INACTIVE,
    SUBSCRIPTION_EXPIRED_STAFF_MESSAGE,
    TENANT_INACTIVE_MESSAGE,
    tenant_block_reason,
)


def _add_form_control_class(form):
    for field in form.fields.values():
        existing = field.widget.attrs.get('class', '')
        field.widget.attrs['class'] = f'{existing} form-control'.strip()


class LoginThrottleMixin:
    """
    Chống brute-force cho form kế thừa AuthenticationForm:
    - khoá tạm username + IP sau LOGIN_FAILURE_LIMIT lần sai;
    - chặn cả IP sau LOGIN_IP_FAILURE_LIMIT lần sai (dò mật khẩu rải trên nhiều username).
    """

    def clean(self):
        username = self.cleaned_data.get('username')
        if not username:
            return super().clean()
        ip_address = login_throttle.get_client_ip(self.request)
        window = timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
        until = login_throttle.locked_until(username, ip_address) or rate_limit.limited_until(
            rate_limit.SCOPE_LOGIN_IP, ip_address, limit=settings.LOGIN_IP_FAILURE_LIMIT, window=window
        )
        if until:
            raise self._locked_error(until)
        try:
            cleaned_data = super().clean()
        except ValidationError as error:
            if getattr(error, 'code', None) == 'invalid_login':
                rate_limit.hit(rate_limit.SCOPE_LOGIN_IP, ip_address, window=window)
                until = login_throttle.record_failure(username, ip_address)
                if until:
                    raise self._locked_error(until) from error
            raise
        login_throttle.reset(username, ip_address)
        return cleaned_data

    @staticmethod
    def _locked_error(until):
        return ValidationError(
            f'Bạn đã nhập sai quá nhiều lần. Vui lòng thử lại sau {rate_limit.minutes_until(until)} phút.',
            code='locked',
        )


class POSAuthenticationForm(LoginThrottleMixin, AuthenticationForm):
    username = forms.CharField(
        label='Tên đăng nhập',
        widget=forms.TextInput(attrs={'placeholder': 'Nhập tên đăng nhập', 'autocomplete': 'username', 'autofocus': True}),
    )
    password = forms.CharField(
        label='Mật khẩu',
        widget=forms.PasswordInput(attrs={'placeholder': 'Nhập mật khẩu', 'autocomplete': 'current-password'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _add_form_control_class(self)

    def clean_username(self):
        # Đăng nhập không phân biệt hoa thường khi chỉ có đúng 1 tài khoản khớp.
        username = self.cleaned_data['username'].strip()
        if not User.objects.filter(username=username).exists():
            matches = list(User.objects.filter(username__iexact=username).values_list('username', flat=True)[:2])
            if len(matches) == 1:
                username = matches[0]
        return username

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.tenant_id:
            return
        reason = tenant_block_reason(user.tenant)
        if reason == BLOCK_TENANT_INACTIVE:
            raise ValidationError(TENANT_INACTIVE_MESSAGE, code=reason)
        # Hết hạn gói: quản lý vẫn đăng nhập được để gia hạn, nhân viên thì không.
        if reason == BLOCK_SUBSCRIPTION_EXPIRED and not user.is_manager:
            raise ValidationError(SUBSCRIPTION_EXPIRED_STAFF_MESSAGE, code=reason)


class ThrottledAdminAuthenticationForm(LoginThrottleMixin, AdminAuthenticationForm):
    pass


class POSPasswordChangeForm(PasswordChangeForm):
    field_order = ['old_password', 'new_password1', 'new_password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].label = 'Mật khẩu hiện tại'
        self.fields['new_password1'].label = 'Mật khẩu mới'
        self.fields['new_password2'].label = 'Xác nhận mật khẩu mới'
        _add_form_control_class(self)


class POSPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].label = 'Email đăng ký'
        self.fields['email'].widget.attrs.update({'placeholder': 'VD: ban@gmail.com', 'autofocus': True})
        _add_form_control_class(self)


class POSSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].label = 'Mật khẩu mới'
        self.fields['new_password1'].help_text = ''
        self.fields['new_password1'].widget.attrs['placeholder'] = 'Tối thiểu 8 ký tự'
        self.fields['new_password2'].label = 'Xác nhận mật khẩu mới'
        self.fields['new_password2'].widget.attrs['placeholder'] = 'Nhập lại mật khẩu mới'
        _add_form_control_class(self)


class SignupForm(forms.Form):
    # Tài khoản đăng ký luôn là tài khoản quản lý: người dùng nhập phần đầu, hậu tố cố định.
    USERNAME_SUFFIX = '_quanly'

    store_name = forms.CharField(
        label='Tên quán / cửa hàng',
        max_length=120,
        widget=forms.TextInput(attrs={'placeholder': 'VD: Cà phê Góc Phố', 'autocomplete': 'organization'}),
    )
    username = forms.CharField(
        label='Tên đăng nhập',
        max_length=150 - len(USERNAME_SUFFIX),
        validators=[User.username_validator],
        help_text='Chỉ gồm chữ, số và các ký tự @ . + - _',
        # Ô này chỉ là phần đầu; template có ô ẩn autocomplete=username chứa tên đầy đủ cho trình duyệt lưu.
        widget=forms.TextInput(attrs={'placeholder': 'VD: gocpho', 'autocomplete': 'off', 'autocapitalize': 'none'}),
    )
    email = forms.EmailField(
        label='Email',
        help_text='Dùng để lấy lại mật khẩu khi quên.',
        widget=forms.EmailInput(attrs={'placeholder': 'VD: ban@gmail.com', 'autocomplete': 'email'}),
    )
    password1 = forms.CharField(
        label='Mật khẩu',
        widget=forms.PasswordInput(attrs={'placeholder': 'Tối thiểu 8 ký tự', 'autocomplete': 'new-password'}),
    )
    password2 = forms.CharField(
        label='Xác nhận mật khẩu',
        widget=forms.PasswordInput(attrs={'placeholder': 'Nhập lại mật khẩu', 'autocomplete': 'new-password'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _add_form_control_class(self)

    def clean_store_name(self):
        store_name = self.cleaned_data['store_name'].strip()
        if not store_name:
            raise ValidationError('Vui lòng nhập tên quán.')
        return store_name

    def clean_username(self):
        # Luôn lưu chữ thường để đăng nhập không bị lệch hoa/thường.
        username = self.cleaned_data['username'].strip().lower()
        if username.endswith(self.USERNAME_SUFFIX):
            username = username[:-len(self.USERNAME_SUFFIX)]
        if not username:
            raise ValidationError('Vui lòng nhập tên đăng nhập.')
        if username == settings.DEMO_TENANT_SLUG:
            raise ValidationError('Tên đăng nhập này đã được hệ thống sử dụng, vui lòng chọn tên khác.')
        username = f'{username}{self.USERNAME_SUFFIX}'
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError('Tên đăng nhập đã tồn tại, vui lòng chọn tên khác.')
        return username

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'Mật khẩu xác nhận không khớp.')
        if password1:
            try:
                validate_password(password1, User(username=cleaned_data.get('username') or ''))
            except ValidationError as error:
                self.add_error('password1', error)
        return cleaned_data
