# eApp PM - Tài Liệu PWA (Progressive Web App)

## 1. Tổng quan
Ứng dụng có hỗ trợ PWA để người dùng có thể **cài đặt như app** trên màn hình chính (Chrome/Edge/Android, Safari iOS).

Mục tiêu:
- Cài đặt (installable) từ trình duyệt
- Có offline fallback page
- Có icon/tên app đúng trên iOS và Android

## 2. Các thành phần PWA trong dự án

### 2.1 Manifest
- Endpoint: `GET /manifest.webmanifest`
- View tạo manifest: `App_UI/views.py` -> `manifest_view`
- Template đã gắn manifest:
  - `templates/base.html`
  - `templates/accounts/onboarding.html`

Nội dung quan trọng:
- `name`, `short_name`
- `start_url`: hiện tại set `"/"` để tránh redirect (Lighthouse dễ pass hơn)
- `display: "standalone"`
- `icons`: có thêm `purpose: "any maskable"` + icon `180x180` (hỗ trợ iOS)

### 2.2 Service Worker
- Endpoint: `GET /sw.js`
- View trả SW JS: `App_UI/views.py` -> `service_worker_view`
- SW được register từ:
  - `templates/base.html`
  - `templates/accounts/onboarding.html`

Hành vi cache (tóm tắt):
- Precache: `offline`, `manifest`, `main.css`, `main.js`, icon cơ bản.
- Navigations (HTML): **network-first và KHÔNG cache HTML** (tránh rò nội dung đã đăng nhập khi offline).
- Static assets (`/static/`, `/media/`): cache-first.

### 2.3 Offline page
- Endpoint: `GET /offline/`
- Template: `templates/offline.html`
- Mục đích: fallback khi user offline và truy cập trang (navigate).

### 2.4 Icon & screenshot assets
Thư mục:
- `static/pwa/icons/*`
- `static/pwa/screenshots/*`

Lưu ý iOS:
- iOS ưu tiên `apple-touch-icon` size **180x180**.

## 3. iOS (Add to Home Screen) - Tên app và Icon
Safari iOS không luôn lấy tên/icon từ manifest như Android. Cần có thêm meta và apple-touch-icon:
- `meta name="apple-mobile-web-app-title"`
- `link rel="apple-touch-icon" sizes="180x180" ...`

Đã được khai báo trong:
- `templates/base.html`
- `templates/accounts/onboarding.html`

Nếu thấy icon/tên không cập nhật:
- Xóa icon PWA cũ khỏi Home Screen
- Add lại từ Safari (do iOS hay cache icon/tên cũ)

## 4. Cách test nhanh

### 4.1 Chrome (Desktop)
- Mở DevTools -> Application
  - Manifest: kiểm tra name, start_url, icons
  - Service Workers: kiểm tra SW active, scope
  - Cache Storage: kiểm tra cache `eapppm-v*`
- Network -> Offline -> reload
  - Kỳ vọng: hiển thị `/offline/`

### 4.2 iPhone (Safari)
- Mở site bằng Safari
- Share -> Add to Home Screen
- Kiểm tra:
  - Tên app hiển thị đúng
  - Icon hiển thị đúng (không bị trắng)
