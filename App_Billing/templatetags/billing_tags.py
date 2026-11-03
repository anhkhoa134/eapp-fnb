import uuid
from urllib.parse import urlencode
from django import template
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.shortcuts import resolve_url
from App_Billing import adapter
from App_Billing.models import SubscriptionRequest
from App_Billing.services import account_for, money

register = template.Library()
register.filter("billing_money", money)


@register.inclusion_tag('App_Billing/panel.html', takes_context=True)
def billing_panel(context):
    request = context.get('request')
    can_manage, history, pending = False, [], None
    authenticated = bool(request and request.user.is_authenticated)
    if authenticated:
        try:
            account = account_for(request)
        except PermissionDenied:
            pass
        else:
            can_manage = True
            query = SubscriptionRequest.objects.filter(account=account)
            history = list(query[:20])
            pending = query.filter(status='pending').first()
    plans = adapter.plans()
    for plan in plans:
        plan['month_label'] = money(plan['month'])
        plan['year_label'] = money(plan['year'])
    next_url = request.get_full_path() if request else '/'
    return {
        'request': request, 'csrf_token': context.get('csrf_token'),
        'billing_can_manage': can_manage, 'billing_authenticated': authenticated,
        'billing_login_url': resolve_url(settings.LOGIN_URL) + '?' + urlencode({'next': next_url}),
        'billing_plans': plans, 'billing_history': history, 'billing_pending': pending,
        'billing_token': uuid.uuid4(),
    }
