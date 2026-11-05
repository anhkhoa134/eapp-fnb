import uuid
from urllib.parse import urlencode
from django import template
from django.conf import settings
from django.shortcuts import resolve_url
from App_Billing import adapter
from App_Billing.models import SubscriptionRequest
from App_Billing.services import money

register = template.Library()
register.filter("billing_money", money)


@register.inclusion_tag('App_Billing/panel.html', takes_context=True)
def billing_panel(context):
    request = context.get('request')
    presentation = _presentation(context)
    account, pending = presentation['account'], presentation['pending']
    can_manage = account is not None
    authenticated = bool(request and request.user.is_authenticated)
    history = list(SubscriptionRequest.objects.filter(account=account)[:20]) if can_manage else []
    plans = adapter.plans()
    for plan in plans:
        plan['is_free'] = presentation['actions'][plan['key']]['free']
        plan['disabled'] = bool(plan['is_free'] and presentation['state'] and presentation['state']['active'] and presentation['state']['plan'] == plan['key'])
        plan['month_label'] = money(plan['month'])
        plan['year_label'] = money(plan['year'])
    next_url = request.get_full_path() if request else '/'
    return {
        'request': request, 'csrf_token': context.get('csrf_token'),
        'billing_can_manage': can_manage, 'billing_authenticated': authenticated,
        'billing_login_url': resolve_url(settings.LOGIN_URL) + '?' + urlencode({'next': next_url}),
        'billing_plans': plans, 'billing_history': history, 'billing_pending': pending,
        'billing_token': uuid.uuid4(), 'billing_state': presentation['state'],
    }


def _presentation(context):
    from App_Billing.presentation import request_presentation
    request = context.get('request')
    if request is None:
        return request_presentation(None)
    if not hasattr(request, '_billing_presentation'):
        request._billing_presentation = request_presentation(request)
    return request._billing_presentation


@register.inclusion_tag('App_Billing/cta.html', takes_context=True)
def billing_cta(context, key, button_class):
    action = _presentation(context)['actions'].get(str(key), {})
    return {'key': key, 'button_class': button_class, 'action': action}
