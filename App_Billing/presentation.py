"""Presentation rules shared by rendered cards, modal and history refresh."""
from django.core.exceptions import PermissionDenied
from . import adapter
from .models import SubscriptionRequest

FREE_PLANS = ('free', 'mien-phi')


def is_free(plan_key):
    return plan_key in FREE_PLANS


def current_subscription(account):
    snapshot = adapter.subscription_snapshot(account)
    key = snapshot['plan']
    active = snapshot.get('active', True)
    cycle = 'none' if is_free(key) else None
    if active and not is_free(key):
        grants = SubscriptionRequest.objects.filter(account=account, plan_key=key, status='approved')
        grant = grants.filter(activation_snapshot=snapshot).first()
        # Existing PM/Photo grants already carry a request reference; this is reliable
        # even before activation_snapshot was introduced. Never infer a cycle from days.
        reference = snapshot.get('reference', '')
        if grant is None and reference.startswith('billing:'):
            grant = grants.filter(reference=reference.removeprefix('billing:'), activation_snapshot={}).first()
        if grant:
            cycle = grant.billing_cycle
    return {'plan': key, 'cycle': cycle, 'active': active}


def request_presentation(request):
    from .services import account_for
    authenticated = bool(request and request.user.is_authenticated)
    account, state, pending = None, None, None
    if authenticated:
        try:
            account = account_for(request)
        except PermissionDenied:
            pass
        else:
            state = current_subscription(account)
            pending = SubscriptionRequest.objects.filter(account=account, status='pending').first()
    actions = {}
    for plan in adapter.plans():
        key = plan['key']
        free = is_free(key)
        current = bool(state and state['active'] and state['plan'] == key)
        caption = ''
        if current:
            caption = {'month': 'Gói hiện tại · Theo tháng', 'year': 'Gói hiện tại · Theo năm',
                       'none': 'Miễn phí · Không thời hạn'}.get(state['cycle'], 'Gói hiện tại · Chưa xác định kỳ hạn')
        item = {'free': free, 'caption': caption}
        for cycle, label in (('month', 'tháng'), ('year', 'năm')):
            disabled = bool(authenticated and account is None)
            text = 'Chọn gói này'
            if free:
                text = 'Đang sử dụng' if current else ('Chuyển về miễn phí' if authenticated else 'Bắt đầu miễn phí')
                disabled = disabled or current
            elif current:
                if state['cycle'] == cycle:
                    text = 'Gia hạn gói'
                elif state['cycle'] in ('month', 'year'):
                    text = f'Chuyển sang gói {label}'
                else:
                    text = f'Gia hạn theo {label}'
            elif state and not state['active'] and state['plan'] == key:
                text = 'Đăng ký lại'
            if pending and pending.plan_key == key and (free or pending.billing_cycle == cycle):
                text, disabled = 'Đang chờ xử lý', True
            item[cycle] = {'label': text, 'disabled': disabled}
        actions[key] = item
    return {'account': account, 'state': state, 'pending': pending, 'actions': actions}
