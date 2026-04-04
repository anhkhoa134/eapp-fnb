from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static as static_url


def _expects_json_response(request):
    accept_header = (request.headers.get('Accept') or '').lower()
    requested_with = (request.headers.get('X-Requested-With') or '').lower()
    return (
        request.path.startswith('/api/')
        or 'application/json' in accept_header
        or requested_with == 'xmlhttprequest'
    )


def build_not_found_response(request):
    if _expects_json_response(request):
        return JsonResponse({'detail': 'Đường dẫn không tồn tại.'}, status=404)

    if request.user.is_authenticated:
        if request.user.is_superuser:
            target = 'admin:index'
            message = 'Không tìm thấy trang. Đã chuyển về trang quản trị.'
        elif getattr(request.user, 'is_manager', False):
            target = 'App_Quanly:dashboard'
            message = 'Không tìm thấy trang. Đã chuyển về dashboard quản lý.'
        else:
            target = 'App_Sales:pos'
            message = 'Không tìm thấy trang. Đã chuyển về POS.'
    else:
        target = 'App_Accounts:login'
        message = 'Không tìm thấy trang. Vui lòng đăng nhập lại.'

    messages.warning(request, message)
    return redirect(target)


def redirect_not_found(request, exception):
    return build_not_found_response(request)


def _abs_static(request, relative_path: str) -> str:
    return request.build_absolute_uri(static_url(relative_path))


def manifest_view(request):
    """Web App Manifest (installable PWA)."""
    icon_files = [
        (72, 'icon-72x72.png'),
        (96, 'icon-96x96.png'),
        (128, 'icon-128x128.png'),
        (144, 'icon-144x144.png'),
        (152, 'icon-152x152.png'),
        (180, 'icon-180x180.png'),
        (192, 'icon-192x192.png'),
        (384, 'icon-384x384.png'),
        (512, 'icon-512x512.png'),
    ]
    icons = []
    for size, name in icon_files:
        entry = {
            'src': _abs_static(request, f'pwa/icons/{name}'),
            'sizes': f'{size}x{size}',
            'type': 'image/png',
            'purpose': 'any maskable' if size in (192, 512) else 'any',
        }
        icons.append(entry)

    data = {
        'name': 'eApp FnB',
        'short_name': 'FnB',
        'description': 'Ứng dụng bán hàng & quản lý F&B đa cửa hàng, đa doanh nghiệp.',
        'start_url': '/',
        'scope': '/',
        'display': 'standalone',
        'background_color': '#ffffff',
        'theme_color': '#10b981',
        'lang': 'vi',
        'icons': icons,
        'screenshots': [
            {
                'src': _abs_static(request, 'pwa/screenshots/splash-750x1334.png'),
                'type': 'image/png',
                'sizes': '750x1334',
                'form_factor': 'narrow',
            },
            {
                'src': _abs_static(request, 'pwa/screenshots/water-splash.jpg'),
                'type': 'image/jpeg',
                'form_factor': 'wide',
            },
        ],
    }
    response = JsonResponse(data)
    response['Content-Type'] = 'application/manifest+json; charset=utf-8'
    return response


def service_worker_view(request):
    """Service worker: precache offline shell; network-first for navigations; cache-first for static/media."""
    js = """
const CACHE_NAME = 'eapp-fnb-v1';
const PRECACHE_URLS = [
  '/offline/',
  '/manifest.webmanifest',
  '/static/pwa/icons/icon-192x192.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.pathname.startsWith('/api/')) return;

  if (request.mode === 'navigate' || request.destination === 'document') {
    event.respondWith(
      fetch(request).catch(() => caches.match('/offline/'))
    );
    return;
  }

  if (url.pathname.startsWith('/static/') || url.pathname.startsWith('/media/')) {
    event.respondWith(
      caches.match(request).then((cached) => {
        if (cached) return cached;
        return fetch(request).then((response) => {
          const copy = response.clone();
          if (response.ok) {
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          }
          return response;
        });
      })
    );
  }
});
"""
    response = HttpResponse(js.strip(), content_type='application/javascript; charset=utf-8')
    response['Cache-Control'] = 'no-cache, must-revalidate'
    return response


def offline_view(request):
    return render(request, 'offline.html')
