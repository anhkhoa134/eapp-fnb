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


# Định danh PWA của eApp FnB. Nhiều project eApp khác cũng là PWA (POS, PM, Reader…): tên, icon, cache
# và cookie phải riêng để không lẫn khi cài app hoặc khi chạy dev chung host.
PWA_APP_ID = '/'  # Giữ nguyên: đổi id làm app đã cài trên máy người dùng thành "app khác".
PWA_CACHE_PREFIX = 'eapp-fnb-'
PWA_CACHE_NAME = f'{PWA_CACHE_PREFIX}v3'
PWA_ICON_SIZES = (72, 96, 128, 144, 152, 180, 192, 384, 512)
PWA_MASKABLE_SIZES = (192, 512)


def _pwa_icon(size) -> str:
    return f'pwa/icons/fnb-icon-{size}x{size}.webp'


def manifest_view(request):
    """Web App Manifest (installable PWA)."""
    icons = [
        {
            'src': _abs_static(request, _pwa_icon(size)),
            'sizes': f'{size}x{size}',
            'type': 'image/webp',
            'purpose': 'any',
        }
        for size in PWA_ICON_SIZES
    ]
    # Icon maskable khai báo riêng (Chrome không khuyến khích gộp "any maskable"); nhãn "FnB" nằm trong vùng an toàn.
    icons += [
        {
            'src': _abs_static(request, _pwa_icon(size)),
            'sizes': f'{size}x{size}',
            'type': 'image/webp',
            'purpose': 'maskable',
        }
        for size in PWA_MASKABLE_SIZES
    ]

    data = {
        'id': PWA_APP_ID,
        'name': 'eApp FnB',
        'short_name': 'eApp FnB',
        'description': 'eApp FnB — bán hàng & quản lý quán cà phê, nhà hàng: POS, gọi món QR, bếp, ca làm việc.',
        'start_url': '/',
        'scope': '/',
        'display': 'standalone',
        'background_color': '#ffffff',
        'theme_color': '#10b981',
        'lang': 'vi',
        'dir': 'ltr',
        'categories': ['business', 'food'],
        'icons': icons,
        'screenshots': [
            {
                'src': _abs_static(request, 'pwa/screenshots/fnb-pos-narrow.webp'),
                'type': 'image/webp',
                'sizes': '780x1688',
                'form_factor': 'narrow',
                'label': 'Màn hình bán hàng eApp FnB trên điện thoại',
            },
            {
                'src': _abs_static(request, 'pwa/screenshots/fnb-pos-wide.webp'),
                'type': 'image/webp',
                'sizes': '1280x800',
                'form_factor': 'wide',
                'label': 'Màn hình bán hàng eApp FnB trên máy tính',
            },
        ],
    }
    response = JsonResponse(data)
    response['Content-Type'] = 'application/manifest+json; charset=utf-8'
    return response


def service_worker_view(request):
    """Service worker: precache offline shell; network-first cho trang; stale-while-revalidate cho static/media."""
    js = """
// eApp FnB service worker. Chỉ đụng tới cache có tiền tố __CACHE_PREFIX__ để không xoá cache
// của PWA khác chạy cùng origin (VD các project eApp khác cùng chạy dev ở 127.0.0.1:8000).
const CACHE_PREFIX = '__CACHE_PREFIX__';
const CACHE_NAME = '__CACHE_NAME__';
const PRECACHE_URLS = [
  '/offline/',
  '/manifest.webmanifest',
  '/static/__ICON_192__',
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
        keys.filter((k) => k.startsWith(CACHE_PREFIX) && k !== CACHE_NAME).map((k) => caches.delete(k))
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
    // Stale-while-revalidate: trả bản cache ngay cho nhanh, đồng thời tải bản mới để lần sau dùng.
    // Tên file static không có hash, nên cache-first thuần sẽ giữ JS/CSS cũ mãi sau khi deploy.
    event.respondWith(
      caches.open(CACHE_NAME).then((cache) =>
        cache.match(request).then((cached) => {
          const network = fetch(request).then((response) => {
            if (response.ok) cache.put(request, response.clone());
            return response;
          });
          if (cached) {
            event.waitUntil(network.catch(() => null));
            return cached;
          }
          return network;
        })
      )
    );
  }
});
"""
    js = (
        js.replace('__CACHE_PREFIX__', PWA_CACHE_PREFIX)
        .replace('__CACHE_NAME__', PWA_CACHE_NAME)
        .replace('__ICON_192__', _pwa_icon(192))
    )
    response = HttpResponse(js.strip(), content_type='application/javascript; charset=utf-8')
    response['Cache-Control'] = 'no-cache, must-revalidate'
    return response


def offline_view(request):
    return render(request, 'offline.html')
