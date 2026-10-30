from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.templatetags.static import static as static_url
from django.urls import reverse


def _expects_json_response(request):
    accept_header = (request.headers.get('Accept') or '').lower()
    requested_with = (request.headers.get('X-Requested-With') or '').lower()
    return (
        request.path.startswith('/api/')
        or 'application/json' in accept_header
        or requested_with == 'xmlhttprequest'
    )


def _home_for(user):
    """Trang "về nhà" theo vai trò: (url, nhãn nút)."""
    if user.is_authenticated:
        if user.is_superuser and not user.tenant_id:
            return reverse('admin:index'), 'Về trang quản trị'
        if getattr(user, 'is_manager', False):
            return reverse('App_Quanly:dashboard'), 'Về trang quản lý'
        if getattr(user, 'is_kitchen', False):
            return reverse('App_Sales:kitchen'), 'Về màn hình bếp'
        return reverse('App_Sales:pos'), 'Về màn hình bán hàng'
    return reverse('App_Accounts:login'), 'Đăng nhập'


def render_error_page(request, status, title, message, **extra):
    home_url, home_label = _home_for(request.user)
    context = {
        'status_code': status,
        'badge': f'LỖI {status}',
        'title': title,
        'message': message,
        'home_url': home_url,
        'home_label': home_label,
        **extra,
    }
    return render(request, 'App_Core/error.html', context, status=status)


def build_not_found_response(request):
    if _expects_json_response(request):
        return JsonResponse({'detail': 'Đường dẫn không tồn tại.'}, status=404)
    # Trả 404 thật (không chuyển hướng im lặng về POS / login, không cộng dồn flash message).
    return render_error_page(
        request,
        404,
        'Không tìm thấy trang',
        'Đường dẫn không tồn tại hoặc dữ liệu đã bị xoá. Kiểm tra lại địa chỉ hoặc quay về trang chính.',
    )


def redirect_not_found(request, exception):
    return build_not_found_response(request)


DEFAULT_PERMISSION_MESSAGE = 'Tài khoản của bạn không có quyền truy cập trang này. Liên hệ quản lý nếu cần được cấp quyền.'


def permission_denied_view(request, exception=None):
    if _expects_json_response(request):
        return JsonResponse({'detail': str(exception or '') or 'Bạn không có quyền truy cập.'}, status=403)
    detail = str(exception or '').strip()
    # Thông báo mặc định của decorator quá ngắn; câu riêng của view (VD "Tính năng … đang tắt") thì giữ nguyên.
    if not detail or detail == 'Bạn không có quyền truy cập.':
        detail = DEFAULT_PERMISSION_MESSAGE
    return render_error_page(request, 403, 'Không có quyền truy cập', detail)


def method_not_allowed_response(request):
    return render_error_page(
        request,
        405,
        'Thao tác không hợp lệ',
        'Trang này không mở trực tiếp bằng đường dẫn được. Hãy quay lại và thao tác từ giao diện.',
    )


def _abs_static(request, relative_path: str) -> str:
    return request.build_absolute_uri(static_url(relative_path))


# Định danh PWA của eApp FnB. Nhiều project eApp khác cũng là PWA (POS, PM, Reader…): tên, icon, cache
# và cookie phải riêng để không lẫn khi cài app hoặc khi chạy dev chung host.
PWA_APP_ID = '/'  # Giữ nguyên: đổi id làm app đã cài trên máy người dùng thành "app khác".
PWA_CACHE_PREFIX = 'eapp-fnb-'
# Tăng khi đổi JS/CSS tĩnh có hành vi mới: cache cũ bị xoá lúc service worker activate.
PWA_CACHE_NAME = f'{PWA_CACHE_PREFIX}v7'
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
  '/static/css/dropdowns.css',
  '/static/css/dropdowns-fnb.css',
  '/static/js/dropdowns.js',
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


# --- SEO: robots.txt / sitemap.xml / llms.txt (trước đây 302 về trang đăng nhập) ---------------

PUBLIC_SITEMAP_ROUTES = ('App_Accounts:login', 'App_Accounts:signup')


def robots_txt_view(request):
    lines = [
        'User-agent: *',
        'Allow: /accounts/login/',
        'Allow: /accounts/signup/',
        'Allow: /llms.txt',
        # Vùng ứng dụng sau đăng nhập và link gọi món có token: không cần index.
        'Disallow: /quanly/',
        'Disallow: /api/',
        'Disallow: /orders/',
        'Disallow: /tables/',
        'Disallow: /kitchen/',
        'Disallow: /shifts/',
        'Disallow: /accounts/password/',
        'Disallow: /accounts/logout/',
        'Disallow: /*/qr/',
        '',
        f'Sitemap: {request.build_absolute_uri(reverse("pwa_sitemap"))}',
    ]
    return HttpResponse('\n'.join(lines) + '\n', content_type='text/plain; charset=utf-8')


def sitemap_xml_view(request):
    urls = '\n'.join(
        f'  <url><loc>{request.build_absolute_uri(reverse(name))}</loc></url>' for name in PUBLIC_SITEMAP_ROUTES
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'{urls}\n'
        '</urlset>\n'
    )
    return HttpResponse(xml, content_type='application/xml; charset=utf-8')


def llms_txt_view(request):
    login_url = request.build_absolute_uri(reverse('App_Accounts:login'))
    signup_url = request.build_absolute_uri(reverse('App_Accounts:signup'))
    text = f"""# eApp FnB

> eApp FnB là phần mềm bán hàng (POS) và quản lý cho quán cà phê, trà sữa, nhà hàng tại Việt Nam:
> bán tại quầy, gọi món tại bàn qua mã QR, màn hình bếp, khuyến mãi, khách hàng thân thiết và
> báo cáo doanh thu cho nhiều chi nhánh. Chạy trên trình duyệt, cài được như ứng dụng (PWA).

## Tính năng chính
- POS tại quầy: chọn bàn, size/topping, ghi chú món, chuyển bàn, thanh toán tiền mặt hoặc thẻ/QR, in hoá đơn 58/80mm.
- Gọi món QR: khách quét mã ở bàn, chọn món và gửi đơn; nhân viên duyệt đơn trên POS.
- Màn hình bếp: nhận phiếu theo thời gian thực, đánh dấu đang làm / đã xong.
- Quản lý: danh mục, món, đơn vị bán, topping, nhiều cửa hàng, nhân viên theo cửa hàng, ca làm việc.
- Khuyến mãi, hạng khách hàng thân thiết, hoàn tiền, nhật ký thao tác, xuất báo cáo Excel/CSV.

## Liên kết
- [Đăng nhập]({login_url})
- [Đăng ký cửa hàng miễn phí]({signup_url})
- [Trang sản phẩm eApp](https://eapp.vn/)
"""
    return HttpResponse(text, content_type='text/plain; charset=utf-8')
