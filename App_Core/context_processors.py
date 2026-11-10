from django.conf import settings

from App_Tenant.access import subscription_notice


def core_context(request):
    context = {
        'app_name': 'eApp FnB',
        'demo_mode': settings.DEMO_MODE,
        'demo_password': settings.DEMO_SEED_DEFAULT_PASSWORD,
    }
    match = getattr(request, 'resolver_match', None)
    user = getattr(request, 'user', None)
    if (
        match is not None
        and match.namespace == 'App_Quanly'
        and user is not None
        and user.is_authenticated
        and user.tenant_id
    ):
        context['subscription_notice'] = subscription_notice(user.tenant)
    return context
