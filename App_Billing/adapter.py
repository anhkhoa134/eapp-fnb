from datetime import timedelta
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from App_Tenant.models import SubscriptionPlan


def account_for(request):
    user = request.user
    if user.role != user.Role.MANAGER or not user.tenant_id or not user.tenant.is_active:
        raise PermissionDenied('Chỉ quản lý doanh nghiệp đang hoạt động được yêu cầu gói dịch vụ.')
    return user.tenant


def plans():
    return [{'key': p.slug, 'name': p.name,
             'month': None if p.is_contact_price else int(p.price_monthly),
             'year': None if p.is_contact_price else int(p.price_yearly)} for p in SubscriptionPlan.objects.all()]


def current_plan_key(account):
    return account.subscription_plan.slug if account.subscription_plan_id else 'mien-phi'


def activate(account, item):
    from .services import add_months
    if not account.is_active:
        raise ValidationError('Doanh nghiệp đã ngừng hoạt động.')
    plan = SubscriptionPlan.objects.filter(slug=item.plan_key).first()
    if plan is None:
        raise ValidationError('Gói không còn khả dụng.')
    today = timezone.localdate()
    same = account.subscription_plan_id == plan.pk
    old_end = account.subscription_ends_on
    start = old_end + timedelta(days=1) if same and old_end and old_end >= today else today
    original_start = account.subscription_starts_on
    account.apply_subscription_plan(plan)
    account.subscription_starts_on = original_start if same and old_end and old_end >= today else today
    account.subscription_ends_on = None if plan.is_free else add_months(start, item.months) - timedelta(days=1)
    account.save()
