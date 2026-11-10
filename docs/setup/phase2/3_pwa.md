# 3) PWA (Progressive Web App)

## 1. Tổng quan

Ứng dụng hỗ trợ PWA để người dùng **cài đặt như app** trên màn hình chính (Chrome/Edge/Android, Safari iOS).

Mục tiêu:

- Cài đặt (installable) từ trình duyệt
- Trang fallback khi ngoại tuyến (`/offline/`)
- Icon và tên app nhất quán trên iOS và Android, **không lẫn với các PWA eApp khác** (mục 5)

## 2. Thành phần PWA trong repo

### 2.1 Manifest

- Endpoint: `GET /manifest.webmanifest`
- View: `App_Core/views.py` → `manifest_view` (hằng số `PWA_*` ngay trên view)
- Layout gắn manifest (và meta PWA): `templates/App_Core/base.html`, `templates/App_Sales/index.html` (POS) qua partial `templates/App_Core/_pwa_head.html`. Trang khách (menu online, gọi món QR) **không** gắn manifest → khách không bị mời cài app bán hàng.

Nội dung chính:

| Trường | Giá trị | Ghi chú |
|---|---|---|
| `id` | `"/"` | Định danh app đã cài. **Không đổi**: đổi `id` thì máy đã cài coi là app khác, không nhận cập nhật manifest |
| `name` / `short_name` | `eApp FnB` / `eApp FnB` | Trùng `apple-mobile-web-app-title` |
| `start_url` / `scope` | `"/"` | |
| `display` | `standalone` | |
| `theme_color` / `background_color` | `#10b981` / `#ffffff` | |
| `categories` | `business`, `food` | |
| `icons` | `static/pwa/icons/fnb-icon-<cỡ>.webp`, 72 → 512 px | Mỗi cỡ khai báo `purpose: "any"`; 192 và 512 khai báo thêm một mục `purpose: "maskable"` riêng (Chrome không khuyến khích gộp `"any maskable"`) |
| `screenshots` | `static/pwa/screenshots/fnb-pos-narrow.webp` (780×1688), `fnb-pos-wide.webp` (1280×800) | Ảnh chụp thật màn hình POS, có `label`; hiện trong hộp thoại cài app của Chrome |

### 2.2 Service Worker

- Endpoint: `GET /sw.js`
- View: `App_Core/views.py` → `service_worker_view`
- Đăng ký tự động: file chung `eapp-pwa.js` (thuộc tính `data-sw-url`, gắn ở `base.html` và `App_Sales/index.html`), scope `/` — xem [mục 2.5](#25-nút-cài-app-cập-nhật-tải-lại-và-live-file-chung-eapp-pwa)

Hành vi cache (tóm tắt):

- **Tên cache**: `PWA_CACHE_NAME` = `eapp-fnb-v3`, tiền tố `PWA_CACHE_PREFIX` = `eapp-fnb-`.
- **Dọn cache khi activate**: chỉ xoá cache có tiền tố `eapp-fnb-` khác bản hiện tại — **không** xoá cache của PWA khác chạy cùng origin.
- **Precache**: `/offline/`, `/manifest.webmanifest`, `fnb-icon-192x192.webp`.
- **Điều hướng (HTML)**: network-first; khi lỗi mạng trả về trang `/offline/` (không cache HTML động để tránh rò nội dung đã đăng nhập khi offline).
- **Tài nguyên tĩnh** (`/static/`, `/media/`): *stale-while-revalidate* — trả bản trong cache ngay, đồng thời tải bản mới để lần mở sau dùng (tên file static không có hash, cache-first thuần sẽ giữ JS/CSS cũ sau khi deploy).
- **API** (`/api/`): không chặn — luôn do trình duyệt xử lý.

Khi đổi logic cache, tăng số phiên bản trong `PWA_CACHE_NAME` (giữ tiền tố `eapp-fnb-`) để client tải worker mới.

### 2.3 Trang offline

- Endpoint: `GET /offline/`
- Template: `templates/offline.html` (HTML tối giản, style inline để vẫn đọc được khi CDN không tải được)

### 2.4 Asset icon, favicon & screenshot

| File | Dùng ở | Định dạng |
|---|---|---|
| `static/pwa/icons/fnb-icon-{72,96,128,144,152,180,192,384,512}x….webp` | Manifest, precache SW, trang offline | WebP (chất lượng 95, nền trong suốt) |
| `static/pwa/icons/fnb-icon-180x180.png` | `apple-touch-icon` | **PNG** — Safari iOS chỉ nhận PNG cho icon màn hình chính |
| `static/pwa/icons/fnb-favicon.ico` | Favicon mọi trang (`base.html`, POS, trang in, trang khách) | ICO 16–64 px |
| `static/pwa/screenshots/fnb-pos-{narrow,wide}.webp` | Manifest `screenshots` | WebP |
| `static/images/logo/eapp.webp` | Logo trong giao diện + ảnh gốc để tạo icon | WebP |

- Icon = logo eApp + nhãn **FnB** màu mint (nằm trong vùng an toàn của icon maskable), để phân biệt với icon eApp chung của các project khác.
- Tạo lại icon + favicon: `python scripts/run/make_pwa_icons.py` (cần Pillow; font Arial Rounded Bold của macOS).
- Chụp lại screenshot: đăng nhập POS với dữ liệu demo, chụp viewport 390×844 @2x (narrow) và 1280×800 (wide), lưu WebP chất lượng 85, cập nhật `sizes` trong `manifest_view`.
- Ảnh vẫn là PNG có chủ đích: `apple-touch-icon` (iOS), file QR bàn tải về để in (`/quanly/qr-tables/<id>/png/`, cần ảnh không nén mất dữ liệu). Ảnh QR thanh toán người dùng upload giữ nguyên định dạng gốc.

### 2.5 Nút cài app, cập nhật, Tải lại và Live (file chung eapp-pwa)

Từ 10/11/2026 (eapp-fnb#8) hành vi các nút này nằm trong file chung `static/eapp-pwa/eapp-pwa.js` + `eapp-pwa.css`,
dùng chung cho 7 app eApp (ERP, POS, FnB, PM, Photo, EquipTrack, Prompt). Bản gốc ở repo hạ tầng
[`Shared-UI/pwa/`](https://github.com/anhkhoa134/Self-hosted-infrastructure/blob/main/Shared-UI/pwa/README.md). **Không sửa trực tiếp `static/eapp-pwa/*`**: sửa bản gốc, chạy `check-pwa.py`,
rồi `sync-pwa.py <repo>` và mở PR. Giao diện nút vẫn do app quyết định; file chung chỉ lo hành vi.

- Nạp: `templates/App_Core/base.html` và `templates/App_Sales/index.html` (trong `<head>`, không `defer`), `data-sw-url="{% url 'pwa_service_worker' %}"`: file chung đăng ký service worker (scope `/`), kiểm bản mới khi tải trang và mỗi giờ.
- Vị trí nút: menu tài khoản ở cả màn hình quản lý và POS.

| Nút / chỉ báo | Gắn bằng | Hành vi |
|---|---|---|
| **Cài ứng dụng** | `data-pwa-install` | Chrome/Edge/Android: chỉ hiện khi trình duyệt cho cài (sự kiện `beforeinstallprompt`); bấm mở hộp thoại cài của trình duyệt. iPhone, iPad, Safari trên Mac: nhãn đổi thành **Hướng dẫn cài đặt**, bấm mở hộp các bước Chia sẻ → Thêm vào Màn hình chính. Ẩn khi đã cài hoặc đang mở bằng icon app. |
| **Có bản cập nhật mới** | `data-pwa-update` | Hiện khi service worker mới đã sẵn sàng. Không tự tải lại trang khi người dùng đang thao tác; bấm thì kích hoạt bản mới rồi tải lại. |
| **Tải lại** | `data-account-reload` | Tải lại trang, icon xoay trong lúc chờ. |
| **Live / Offline** | `data-account-live-indicator` | Gọi `HEAD /healthz/` khi mở menu và khi trình duyệt báo đổi mạng; máy chủ không trả lời hoặc mất mạng thì chuyển **Offline**. |

API cho JS của app: `window.eAppPWA` (`install()`, `update()`, `showHelp()`, `checkLive()`, `sync()`), sự kiện trên
`window`: `pwa:installed`, `pwa:updateavailable`, `eapp-pwa:change`. Hộp hướng dẫn cài có tiếng Việt và tiếng Anh.

Đã bỏ: partial `templates/App_Core/_pwa_register.html`, CSS chấm Live/Tải lại viết inline trong 2 template, hướng dẫn cài iOS bằng `eappDialog.alert` trong `eapp_dialog.js`.

Kiểm thử: `python scripts/check_pwa_install.py` (dùng `static/eapp-pwa/eapp-pwa.js` khi có).

## 3. iOS (Add to Home Screen)

Safari không luôn lấy đủ thông tin từ manifest như Android. Cần thêm:

- `meta name="apple-mobile-web-app-title"` = `eApp FnB`
- `link rel="apple-touch-icon" sizes="180x180"` → `fnb-icon-180x180.png`

Đã gắn trong `templates/App_Core/_pwa_head.html`.

Nếu icon/tên không đổi sau khi cập nhật:

- Xóa shortcut cũ trên Home Screen và thêm lại từ Safari (iOS hay cache icon/tên cũ).

## 4. Kiểm thử nhanh

### Tự động
- `python manage.py test App_Core` — `PwaIdentityTests`: manifest (`id`, tên, icon/screenshot WebP tồn tại đúng kích thước, maskable 192/512), SW chỉ dọn cache `eapp-fnb-*`, tên cookie riêng, trang dùng favicon/logo FnB.
- Đã kiểm bằng Chrome (DevTools Protocol) ngày 28/09/2026: `Page.getAppManifest` không lỗi, `Page.getInstallabilityErrors` rỗng (cài được); cache giả `eapppm-v9` của app khác được giữ, cache cũ `eapp-fnb-v1` bị dọn.

### Chrome (Desktop)

- DevTools → **Application**
  - **Manifest**: name `eApp FnB`, `id` `/`, icons FnB, không có cảnh báo
  - **Service Workers**: `sw.js` active, scope `/`
  - **Cache Storage**: `eapp-fnb-v3`
- **Network** → **Offline** → reload một trang bất kỳ
  - Kỳ vọng: hiển thị `/offline/` khi không có mạng (sau khi đã từng mở site online để SW cài và precache).

### iPhone (Safari)

- Mở site → Share → **Add to Home Screen** (hoặc menu tài khoản → **Hướng dẫn cài đặt**)
- Kiểm tra tên app `eApp FnB` và icon có nhãn FnB.

## 5. Tránh nhầm với PWA của project khác

Máy dev có nhiều project eApp cũng là PWA (POS, PM, Prompt, Photo, Reader, EquipTrack…), đều khai báo `start_url` / `scope` / `id` là `/`. Trình duyệt phân biệt PWA theo **origin** = giao thức + host + cổng; mọi thứ dưới đây dùng chung trong một origin:

| Thứ dùng chung | Hậu quả khi các project chạy chung `127.0.0.1:8000` | Cách FnB tránh |
|---|---|---|
| Service worker scope `/` | SW của project mở sau thay SW của project trước; SW cũ có thể trả file static / trang offline của app khác | **Cổng dev riêng `127.0.0.1:8002`** (`scripts/run.txt`, `phase1/1_setup_and_run.md`) |
| Cache Storage | SW dọn "mọi cache không phải của mình" sẽ xoá cache app khác | SW FnB chỉ dọn cache tiền tố `eapp-fnb-` |
| Định danh app đã cài (`id` = origin + `/`) | Cài app này đè lên app kia trong Chrome | Cổng riêng (dev); domain riêng `fnb.eapp.vn` (prod) |
| localStorage | Trùng khoá thì đọc nhầm cấu hình | Mọi khoá FnB có tiền tố `eapp_…` riêng (đã so với các project khác: không trùng) |
| Cookie (**không phân biệt cổng**) | Đăng nhập project khác làm mất phiên FnB, lỗi CSRF | Tên cookie riêng: `eappfnb_sessionid`, `eappfnb_csrftoken` (`SESSION_COOKIE_NAME`, `CSRF_COOKIE_NAME`) |
| Icon, favicon, ảnh screenshot, tên | Trước 28/09/2026 FnB dùng icon + screenshot giống hệt POS, Prompt, Reader, EquipTrack… → không phân biệt được app đã cài | Icon/favicon riêng có nhãn FnB, screenshot thật của POS FnB, tên file `fnb-*` |

**Dọn dẹp một lần trên máy dev** (sau khi chuyển FnB sang cổng 8002): mở `http://127.0.0.1:8000` → DevTools → Application → **Storage → Clear site data** để gỡ các SW / cache cũ của nhiều project đã chồng lên nhau ở cổng 8000. Nếu đã cài app FnB từ cổng 8000, gỡ app đó (`chrome://apps`) rồi cài lại từ `127.0.0.1:8002`.

Đổi tên cookie khi deploy: mọi người dùng bị đăng xuất **một lần** (cookie phiên cũ không còn được đọc).

Gợi ý cho các project khác (chưa sửa, nằm ngoài repo này): mỗi project một cổng dev riêng; SW chỉ dọn cache theo tiền tố riêng (eApp Prompt và eApp PM hiện đều dùng tiền tố `eapppm-` và xoá cache của mọi app khác); đặt tên cookie riêng; icon riêng.

## 6. Liên quan

- Ghi chú thiết kế ban đầu: `backup/7_pwa.md`
