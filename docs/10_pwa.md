# eApp FnB — PWA (Progressive Web App)

## 1. Tổng quan

Ứng dụng hỗ trợ PWA để người dùng **cài đặt như app** trên màn hình chính (Chrome/Edge/Android, Safari iOS).

Mục tiêu:

- Cài đặt (installable) từ trình duyệt
- Trang fallback khi ngoại tuyến (`/offline/`)
- Icon và tên app nhất quán trên iOS và Android

## 2. Thành phần PWA trong repo

### 2.1 Manifest

- Endpoint: `GET /manifest.webmanifest`
- View: `App_Core/views.py` → `manifest_view`
- Layout gắn manifest (và meta PWA): `templates/App_Core/base.html`, `templates/App_Sales/index.html` (POS) qua partial `templates/App_Core/_pwa_head.html`

Nội dung chính:

- `name`, `short_name`, `description`
- `start_url`: `"/"` (tránh redirect không cần thiết, Lighthouse dễ pass hơn)
- `display`: `standalone`
- `theme_color` / `background_color`
- `icons`: kích thước trong `static/pwa/icons/*` (192×192 và 512×512 dùng `purpose: "any maskable"`)
- `screenshots`: ảnh trong `static/pwa/screenshots/*` (narrow + wide)

### 2.2 Service Worker

- Endpoint: `GET /sw.js`
- View: `App_Core/views.py` → `service_worker_view`
- Đăng ký tự động: partial `templates/App_Core/_pwa_register.html` (gắn ở `base.html` và `App_Sales/index.html`)

Hành vi cache (tóm tắt):

- **Precache**: `/offline/`, `/manifest.webmanifest`, icon 192×192.
- **Điều hướng (HTML)**: network-first; khi lỗi mạng trả về trang `/offline/` (không cache HTML động để tránh rò nội dung đã đăng nhập khi offline).
- **Tài nguyên tĩnh** (`/static/`, `/media/`): cache-first sau lần tải thành công.
- **API** (`/api/`): không chặn — luôn do trình duyệt xử lý.

Khi đổi logic cache, tăng `CACHE_NAME` trong `service_worker_view` (ví dụ `eapp-fnb-v2`) để client tải worker mới.

### 2.3 Trang offline

- Endpoint: `GET /offline/`
- Template: `templates/offline.html` (HTML tối giản, style inline để vẫn đọc được khi CDN không tải được)

### 2.4 Asset icon & screenshot

Thư mục:

- `static/pwa/icons/*`
- `static/pwa/screenshots/*`

Lưu ý iOS:

- Safari ưu tiên `apple-touch-icon` **180×180** — đã khai báo trong `_pwa_head.html`.

## 3. iOS (Add to Home Screen)

Safari không luôn lấy đủ thông tin từ manifest như Android. Cần thêm:

- `meta name="apple-mobile-web-app-title"`
- `link rel="apple-touch-icon" sizes="180x180" ...`

Đã gắn trong `templates/App_Core/_pwa_head.html`.

Nếu icon/tên không đổi sau khi cập nhật:

- Xóa shortcut cũ trên Home Screen và thêm lại từ Safari (iOS hay cache icon/tên cũ).

## 4. Kiểm thử nhanh

### Chrome (Desktop)

- DevTools → **Application**
  - **Manifest**: name, `start_url`, icons
  - **Service Workers**: SW active, scope `/`
  - **Cache Storage**: cache `eapp-fnb-v1`
- **Network** → **Offline** → reload một trang bất kỳ  
  - Kỳ vọng: hiển thị `/offline/` khi không có mạng (sau khi đã từng mở site online để SW cài và precache).

### iPhone (Safari)

- Mở site → Share → **Add to Home Screen**
- Kiểm tra tên app và icon.

## 5. Liên quan

- Ghi chú thiết kế ban đầu: `backup/7_pwa.md`
