from django.conf import settings

from App_Core.views import build_not_found_response


class NotFoundRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code != 404:
            return response
        if request.method not in {'GET', 'HEAD'}:
            return response
        if request.path.startswith(str(settings.STATIC_URL)) or request.path.startswith(str(settings.MEDIA_URL)):
            return response
        if request.path.startswith('/api/'):
            if request.resolver_match is None:
                return build_not_found_response(request)
            return response
        if (
            response.has_header('Content-Type')
            and 'application/json' in response['Content-Type'].lower()
        ):
            return response
        return build_not_found_response(request)
