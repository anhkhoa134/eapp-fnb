# 5) Chính sách & tiêu chuẩn bảo mật

Ký hiệu: ✅ đã áp dụng trong code · ⚠️ chưa có / cần xử lý.

## 1. Cô lập dữ liệu multi-tenant
Nguyên tắc: **mọi query dữ liệu nghiệp vụ phải lọc theo tenant của user đăng nhập** (hoặc tenant suy ra từ `public_slug` + token ở luồng public).

| Quy tắc | Trạng thái |
|---|---|
| Model nghiệp vụ có FK `tenant`; view quản lý lấy tenant từ `request.user` | ✅ |
| POS API chỉ thao tác trên store user có quyền (`UserStoreAccess`) | ✅ |
| WebSocket POS: yêu cầu login + quyền `store_id` | ✅ |
| Public QR API / WebSocket: bắt buộc `table_code` + `token` hợp lệ, order thuộc đúng bàn | ✅ |
| Reserved slug không được dùng làm `public_slug` (`RESERVED_PUBLIC_SLUGS`: `admin`, `accounts`, `api`, `quanly`, `kitchen`, `shifts`, `orders`, `tables`, `static`, `media`, `offline`, `favicon.ico`) | ✅ |
| Media upload tách thư mục theo tenant (`media/tenant_<id>/`) | ✅ |
| Cờ tính năng tuỳ chọn được **chặn ở server** (403 / 400), không chỉ ẩn menu; tính năng bán theo gói kiểm tra cả gói (`Tenant.feature_enabled()`, `customer_feature_enabled`, `promotion_feature_enabled`, `recipe_feature_enabled`) | ✅ (từ 28/09/2026) |

Checklist khi thêm view/API mới:
- [ ] Lọc queryset theo `tenant` (và `store` nếu có) — không dùng `Model.objects.get(pk=...)` trần.
- [ ] Gắn decorator `manager_required` / `staff_or_manager_required` (`App_Accounts/permissions.py`).
- [ ] Kiểm tra cờ `Tenant.show_*_feature` nếu thuộc tính năng tuỳ chọn (403 khi tắt).
- [ ] Viết test truy cập chéo tenant (user tenant A không đọc/sửa được dữ liệu tenant B).

## 2. Xác thực & phân quyền
| Quy tắc | Trạng thái |
|---|---|
| Vai trò `MANAGER` / `STAFF`; `/quanly/*` chỉ manager | ✅ |
| Tối đa 1 manager / tenant (`uq_manager_per_tenant`) | ✅ |
| Logout chỉ chấp nhận POST (`GET` → 405) | ✅ |
| Password validators mặc định Django (độ dài, phổ biến, toàn số, giống thông tin user) | ✅ |
| Đường dẫn admin ẩn qua `REAL_ADMIN_PATH` | ✅ |
| Tài khoản thuộc doanh nghiệp (quản lý, nhân viên) **không** có `is_staff` → không đăng nhập được Django Admin; chỉ superadmin vào admin | ✅ (migration `App_Accounts/0007`) |
| Giới hạn số lần đăng nhập sai / chống brute-force: khoá username + IP sau `LOGIN_FAILURE_LIMIT` (5) lần trong `LOGIN_LOCKOUT_MINUTES` (15) phút, chặn IP sau `LOGIN_IP_FAILURE_LIMIT` (30) lần; áp dụng cả trang admin (BL-002) | ✅ |
| Giới hạn đăng ký (`SIGNUP_LIMIT_PER_IP`) và Quên mật khẩu (`PASSWORD_RESET_LIMIT_PER_IP`) theo IP | ✅ |
| Tài khoản bootstrap/seed dùng mật khẩu mặc định `123456` — bắt buộc đổi trước khi bàn giao tenant thật | ⚠️ quy trình thủ công |

## 3. Token QR bàn
| Quy tắc | Trạng thái |
|---|---|
| `qr_token` sinh bằng `secrets.token_urlsafe(24)` | ✅ |
| Manager reset token khi lộ, in lại QR | ✅ |
| Đơn QR ở trạng thái terminal (`APPROVED/REJECTED/CANCELLED`) không cho sửa/huỷ/duyệt lại | ✅ |
| Gói hết hạn / tắt QR: trang QR, tạo đơn và sửa đơn (tại bàn + mang đi) trả 403 (`Tenant.is_ordering_open()`); khách vẫn huỷ được đơn đang chờ | ✅ |
| Giới hạn đầu vào mỗi đơn (POS + public): tối đa `MAX_ORDER_LINES` = 100 dòng, `MAX_ITEM_QUANTITY` = 999 / món; body JSON phải là object (`App_Sales/services.py`) | ✅ |
| Rate limit API public: đặt mang đi 10 đơn / 30 phút / IP / tenant | ✅ |
| Rate limit API public QR tại bàn | ⚠️ chưa có (BL-003) |

## 3b. Toàn vẹn thanh toán
| Quy tắc | Trạng thái |
|---|---|
| Thuế do **server** tính theo `Tenant.tax_percent` (cấu hình ở *Cấu hình tính năng*); `tax_rate` client gửi lên bị bỏ qua | ✅ |
| Chống tạo đơn trùng: POS gửi `client_request_id` cho mỗi lần thanh toán, server trả lại đơn cũ nếu nhận lại cùng mã (unique `tenant + client_request_id`); nút thanh toán khoá khi đang gửi | ✅ |
| Thanh toán bàn khoá dòng bàn (`select_for_update`) → hai máy cùng thanh toán một bàn chỉ tạo 1 đơn | ✅ |
| Tiền khách đưa trong khoảng `0 … MAX_MONEY_AMOUNT` | ✅ |

## 3c. Chống XSS phía trình duyệt
- Template Django tự escape; lỗ hổng chỉ còn ở JS dựng HTML bằng chuỗi (`innerHTML`, template literal).
- Mọi dữ liệu từ server chèn vào HTML phải qua hàm escape **đủ 5 ký tự** `& < > " '` — kể cả khi chèn vào thuộc tính (`alt`, `aria-label`, `src`, `data-*`). Không dùng mẹo `div.textContent → innerHTML` vì không escape dấu nháy.
- Hàm dùng chung: `escapeHtml` (POS `App_Sales/index.html`, bếp `App_Sales/kitchen.html`), `esc` (trang khách `App_Public/_ordering_app.html`).
- Lý do nghiêm trọng: ai cũng tự đăng ký được doanh nghiệp, và trang menu public chạy **cùng origin** với POS / Quản lý / Admin; tên món chứa mã độc có thể chiếm phiên người khác mở trang.

## 4. Cấu hình HTTP / cookie
Áp dụng mọi môi trường:

| Setting | Giá trị |
|---|---|
| `SECURE_CONTENT_TYPE_NOSNIFF` | `True` |
| `SESSION_COOKIE_HTTPONLY` / `CSRF_COOKIE_HTTPONLY` | `True` |
| `SESSION_COOKIE_NAME` / `CSRF_COOKIE_NAME` | `eappfnb_sessionid` / `eappfnb_csrftoken` (riêng project; cookie không phân biệt cổng) |
| `SECURE_REFERRER_POLICY` | `same-origin` |
| `X_FRAME_OPTIONS` | `DENY` |
| CSRF middleware | Bật |

Chỉ khi `ENVIRONMENT=prod`:

| Setting | Giá trị |
|---|---|
| `SECRET_KEY` | Bắt buộc đặt (lỗi nếu còn giá trị mặc định) |
| `ALLOWED_HOSTS` | Bắt buộc đặt |
| `SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE` | `True` |
| `SECURE_SSL_REDIRECT` | `True` (mặc định prod) |
| `SECURE_HSTS_SECONDS` | `31536000` + `INCLUDE_SUBDOMAINS` + `PRELOAD` |
| `SECURE_PROXY_SSL_HEADER` | `X-Forwarded-Proto` (sau Nginx) |
| `CSRF_TRUSTED_ORIGINS` | Đặt theo domain HTTPS |

WebSocket bọc `AllowedHostsOriginValidator` (`Project/asgi.py`): chỉ nhận kết nối có header `Origin` thuộc `ALLOWED_HOSTS` (chống cross-site WebSocket hijacking). Vì vậy production **không được** đặt `ALLOWED_HOSTS=*` (file `.env` dev hiện để `*` nên ở dev không chặn origin).

## 5. Quản lý secret & cấu hình
- Secret đặt trong `Project/.env`, **không commit** (đã có trong `.gitignore`).
- Tạo `SECRET_KEY` mới cho mỗi môi trường: `python scripts/run/print_secret_key.py` hoặc lệnh trong `6_production_env.md` mục 3.
- Không log mật khẩu, token QR, nội dung `.env`.
- Tài khoản DB production dùng user riêng, không dùng `postgres`.

## 6. PWA / cache
- Service worker **không cache HTML động** (tránh lộ nội dung đã đăng nhập khi offline).
- Không cache `/api/`.
- Chi tiết: `phase2/3_pwa.md`.

## 7. Logging & xử lý sự cố
- Lỗi ghi vào `logs/recent-errors.log` (mức theo `LOG_LEVEL`).
- **Nhật ký thao tác** (`App_Core.AuditLog`, `/quanly/audit-log/`): ghi hoàn tiền, xoá đơn, huỷ món, in lại hoá đơn / phiếu bếp, chuyển bàn, từ chối đơn QR, mở / chốt ca, đăng nhập / đăng xuất / đăng nhập sai, và mọi thay đổi món, giá, khuyến mãi, nhân viên, cửa hàng, cấu hình (kèm giá trị cũ → mới; mật khẩu và token QR chỉ ghi *đã thay đổi*). Chỉ ghi thêm, không có giao diện sửa / xoá; manager chỉ xem được tenant của mình. Chi tiết: `docs/setup/phase4/3_audit_log.md`.
- Hoàn tiền chỉ manager làm được, bắt buộc lý do. Hoá đơn in lại có dấu *BẢN IN LẠI (lần N)*.
- 404 được chuyển hướng bởi `NotFoundRedirectMiddleware` (không lộ trang debug); API vẫn trả JSON 404.
- Khi nghi lộ token QR: reset token bàn. Khi nghi lộ mật khẩu: đổi mật khẩu + xoá session (`python manage.py clearsessions` hoặc đổi `SECRET_KEY`).

## 8. Checklist trước khi release
- [ ] `DEBUG=False`, `ENVIRONMENT=prod`.
- [ ] `python manage.py check --deploy` không còn cảnh báo nghiêm trọng.
- [ ] Không có mật khẩu mặc định trên tenant thật.
- [ ] `REAL_ADMIN_PATH` khác `admin`.
- [ ] `ALLOWED_HOSTS` liệt kê domain cụ thể, **không** dùng `*` (WebSocket kiểm tra Origin theo danh sách này).
- [ ] HTTPS + HSTS hoạt động, WebSocket qua `wss://`.
- [ ] Test phân quyền / cô lập tenant pass.

## 9. Việc cần làm (backlog bảo mật)
1. ~~Chống brute-force đăng nhập~~ — xong (BL-002).
2. Rate limit `/api/public/` (Nginx `limit_req` hoặc middleware). Đã có cho `POST /api/public/takeaway/orders/` (10 đơn / 30 phút / IP / tenant); API QR tại bàn chưa có (BL-003).
3. Bắt buộc đổi mật khẩu lần đầu với tài khoản bootstrap (BL-004).
4. Bổ sung Content-Security-Policy (hiện tải Bootstrap/ECharts/Font Awesome từ CDN) — lớp chặn thứ hai cho XSS (BL-007).
