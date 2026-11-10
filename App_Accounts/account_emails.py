"""Email tài khoản theo giao diện eApp ERP: quên mật khẩu và kích hoạt tài khoản tự đăng ký.

Mẫu thư: templates/emails/ (_card.html + password_reset_* + signup_verify_*), bản HTML kèm bản text.
Thương hiệu (tên, logo, khẩu hiệu) lấy từ settings.EMAIL_BRAND. Tài khoản demo dùng chung không nhận email
đặt lại mật khẩu (xem demo.py).
"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse

from App_Core.demo import is_shared_demo_account

logger = logging.getLogger(__name__)

LOCAL_HOSTS = {'127.0.0.1', 'localhost', 'testserver', '::1'}
SIGNUP_VERIFY_SALT = 'fnb-signup-verify'


def brand_context(request=None):
    brand = settings.EMAIL_BRAND
    logo_url = brand['site_url'].rstrip('/') + brand['logo_path']
    if request is not None:
        try:
            if request.get_host().split(':')[0].lower() not in LOCAL_HOSTS:
                logo_url = request.build_absolute_uri(brand['logo_path'])
        except Exception:  # Host lạ (DisallowedHost…): giữ logo của domain chính
            pass
    return {
        'brand_name': brand['name'],
        'brand_tagline': brand['tagline'],
        'brand_slogan': brand['slogan'],
        'brand_logo_url': logo_url,
    }


def display_name(user):
    for attr in ('full_name', 'display_name'):
        value = getattr(user, attr, '')
        if value and isinstance(value, str):
            return value
    return user.get_full_name() or user.get_username()


def send_branded_email(*, template, user, to, request=None, **context):
    """Gửi emails/<template>_email.{txt,html} với tiêu đề emails/<template>_subject.txt."""
    ctx = {**brand_context(request), 'user': user, 'display_name': display_name(user), **context}
    subject = ''.join(render_to_string(f'emails/{template}_subject.txt', ctx).splitlines()).strip()
    message = EmailMultiAlternatives(
        subject, render_to_string(f'emails/{template}_email.txt', ctx), None, list(to),
    )
    message.attach_alternative(render_to_string(f'emails/{template}_email.html', ctx), 'text/html')
    return message.send()


class BrandedPasswordResetForm(PasswordResetForm):
    """Quên mật khẩu: thư giao diện ERP, không gửi cho tài khoản demo dùng chung (trang vẫn báo "đã gửi")."""

    confirm_url_name = 'App_Accounts:password_reset_confirm'

    def get_users(self, email):
        return (user for user in super().get_users(email) if not is_shared_demo_account(user))

    def save(self, *args, request=None, **kwargs):
        self._request = request
        return super().save(*args, request=request, **kwargs)

    def send_mail(self, subject_template_name, email_template_name, context, from_email, to_email,
                  html_email_template_name=None):
        path = reverse(self.confirm_url_name, kwargs={'uidb64': context['uid'], 'token': context['token']})
        request = getattr(self, '_request', None)
        # Dựng link theo host đang truy cập (không theo bảng Site của django.contrib.sites, thường vẫn là example.com).
        action_url = request.build_absolute_uri(path) if request is not None else f"{context['protocol']}://{context['domain']}{path}"
        try:
            send_branded_email(
                template='password_reset',
                user=context['user'],
                to=[to_email],
                request=request,
                action_url=action_url,
                reset_hours=max(1, settings.PASSWORD_RESET_TIMEOUT // 3600),
            )
        except Exception:
            # Giống Django: lỗi SMTP không làm lộ email nào tồn tại; ghi log để xử lý.
            logger.exception('Không gửi được email đặt lại mật khẩu.')


# Kích hoạt tài khoản tự đăng ký (giống eApp ERP SAAS-08). Token ký bằng SECRET_KEY, chứa id + email:
# đổi email thì link cũ hết hiệu lực.
def awaiting_verification(user):
    return not user.is_active and user.last_login is None


def signup_token(user):
    return signing.dumps({'u': user.pk, 'e': user.email}, salt=SIGNUP_VERIFY_SALT)


def user_from_signup_token(token):
    """Trả (user, lỗi). lỗi: None | "expired" | "invalid"."""
    try:
        data = signing.loads(token, salt=SIGNUP_VERIFY_SALT, max_age=settings.SIGNUP_VERIFY_MAX_AGE)
    except signing.SignatureExpired:
        return None, 'expired'
    except signing.BadSignature:
        return None, 'invalid'
    user = get_user_model().objects.filter(pk=data.get('u'), email=data.get('e')).first()
    return (user, None) if user else (None, 'invalid')


def send_signup_verification(request, user, verify_url_name='App_Accounts:signup_verify'):
    link = request.build_absolute_uri(reverse(verify_url_name, args=[signup_token(user)]))
    try:
        send_branded_email(
            template='signup_verify',
            user=user,
            to=[user.email],
            request=request,
            action_url=link,
            days=max(1, settings.SIGNUP_VERIFY_MAX_AGE // 86400),
        )
    except Exception:  # SMTP hỏng: tài khoản vẫn tạo, người dùng bấm «Gửi lại» sau
        logger.exception('Không gửi được email kích hoạt tài khoản tự đăng ký.')


@transaction.atomic
def activate_signup(user):
    user = get_user_model().objects.select_for_update().get(pk=user.pk)
    if not awaiting_verification(user):
        return None
    user.is_active = True
    user.save(update_fields=['is_active'])
    return user
