from django.http import HttpResponse


class HealthCheckMiddleware:
    """Answer the container health probe before host checks, auth and tenant redirects."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == "/healthz/":
            return HttpResponse("ok", content_type="text/plain")
        return self.get_response(request)
