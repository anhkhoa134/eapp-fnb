from django import forms
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone

from App_Accounts import login_throttle
from App_Accounts.models import User
from App_Tenant.access import (
    BLOCK_SUBSCRIPTION_EXPIRED,
    BLOCK_TENANT_INACTIVE,
    SUBSCRIPTION_EXPIRED_STAFF_MESSAGE,
    TENANT_INACTIVE_MESSAGE,
    tenant_block_reason,
)


class LoginThrottleMixin:
    """Khoá tạm username + IP sau nhiều lần đăng nhập sai. Dùng cho form kế thừa AuthenticationForm."""

    def clean(self):
        username = self.cleaned_data.get('username')
        if not username:
            return super().clean()
        ip_address = login_throttle.get_client_ip(self.request)
        until = login_throttle.locked_until(username, ip_address)
        if until:
            raise self._locked_error(until)
        try:
            cleaned_data = super().clean()
        except ValidationError as error:
            if getattr(error, 'code', None) == 'invalid_login':
                until = login_throttle.record_failure(username, ip_address)
                if until:
                    raise self._locked_error(until) from error
            raise
        login_throttle.reset(username, ip_address)
        return cleaned_data

    @staticmethod
    def _locked_error(until):
        minutes = max(1, -(-int((until - timezone.now()).total_seconds()) // 60))
        return ValidationError(
            f'Bạn đã nhập sai quá nhiều lần. Vui lòng thử lại sau {minutes} phút.',
            code='locked',
        )


class POSAuthenticationForm(LoginThrottleMixin, AuthenticationForm):
    username = forms.CharField(label='Tên đăng nhập')
    password = forms.CharField(label='Mật khẩu', widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{existing} form-control'.strip()

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
        for field in self.fields.values():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{existing} form-control'.strip()


class SignupForm(forms.Form):
    store_name = forms.CharField(
        label='Tên quán / cửa hàng',
        max_length=150,
        widget=forms.TextInput(attrs={'placeholder': 'VD: Cà phê Góc Phố', 'autocomplete': 'organization'}),
    )
    username = forms.CharField(
        label='Tên đăng nhập',
        max_length=150,
        validators=[User.username_validator],
        help_text='Chỉ gồm chữ, số và các ký tự @ . + - _',
        widget=forms.TextInput(attrs={'placeholder': 'VD: gocpho_quanly', 'autocomplete': 'username'}),
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
        for field in self.fields.values():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{existing} form-control'.strip()

    def clean_store_name(self):
        store_name = self.cleaned_data['store_name'].strip()
        if not store_name:
            raise ValidationError('Vui lòng nhập tên quán.')
        return store_name

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError('Tên đăng nhập đã tồn tại, vui lòng chọn tên khác.')
        return username

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
