from django.conf import settings

# Nguồn ngoài mà template đang dùng: Bootstrap / icon / flatpickr / echarts / Sortable (jsDelivr),
# Font Awesome (cdnjs), Google Fonts. Ảnh món có thể là URL ngoài bất kỳ (image_url), nên img-src mở https:.
# Template còn nhiều <script>/<style> inline nên chưa bỏ được 'unsafe-inline'.
CDN_SOURCES = 'https://cdn.jsdelivr.net https://cdnjs.cloudflare.com'

PERMISSIONS_POLICY = ', '.join(
    [
        'camera=()',
        'microphone=()',
        'geolocation=()',
        'payment=()',
        'usb=()',
        'serial=()',
        'bluetooth=()',
        'magnetometer=()',
        'gyroscope=()',
        'accelerometer=()',
        'fullscreen=(self)',
        'clipboard-write=(self)',
    ]
)


def build_content_security_policy(request) -> str:
    host = request.get_host()
    directives = {
        'default-src': "'self'",
        'script-src': f"'self' 'unsafe-inline' {CDN_SOURCES}",
        'style-src': f"'self' 'unsafe-inline' {CDN_SOURCES} https://fonts.googleapis.com",
        'font-src': f"'self' data: {CDN_SOURCES} https://fonts.gstatic.com",
        'img-src': "'self' data: blob: https:",
        'media-src': "'self' data: blob:",
        # WebSocket cùng host (POS, bếp, trang khách QR); CDN cho service worker / sourcemap.
        'connect-src': f"'self' wss://{host} ws://{host} {CDN_SOURCES}",
        'frame-src': "'self'",
        'worker-src': "'self'",
        'manifest-src': "'self'",
        'object-src': "'none'",
        'base-uri': "'self'",
        'form-action': "'self'",
    }
    return '; '.join(f'{name} {value}' for name, value in directives.items())


class SecurityHeadersMiddleware:
    """Content-Security-Policy + Permissions-Policy cho các trang của app (trừ Django admin/Jazzmin)."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.admin_prefix = f'/{settings.REAL_ADMIN_PATH}'

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault('Permissions-Policy', PERMISSIONS_POLICY)
        if request.path.startswith(self.admin_prefix):
            return response
        content_type = (response.get('Content-Type') or '').lower()
        if content_type.startswith('text/html'):
            response.setdefault('Content-Security-Policy', build_content_security_policy(request))
        return response
