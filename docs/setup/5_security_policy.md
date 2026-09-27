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
| Reserved slug không được dùng làm `public_slug` (`admin`, `accounts`, `api`, `quanly`, `static`, `media`, `favicon.ico`) | ✅ |
| Media upload tách thư mục theo tenant (`media/tenant_<id>/`) | ✅ |

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
| Giới hạn số lần đăng nhập sai / chống brute-force | ⚠️ chưa có |
| Tài khoản bootstrap/seed dùng mật khẩu mặc định `123456` — bắt buộc đổi trước khi bàn giao tenant thật | ⚠️ quy trình thủ công |

## 3. Token QR bàn
| Quy tắc | Trạng thái |
|---|---|
| `qr_token` sinh bằng `secrets.token_urlsafe(24)` | ✅ |
| Manager reset token khi lộ, in lại QR | ✅ |
| Đơn QR ở trạng thái terminal (`APPROVED/REJECTED/CANCELLED`) không cho sửa/huỷ/duyệt lại | ✅ |
| Rate limit API public tạo đơn QR | ⚠️ chưa có |

## 4. Cấu hình HTTP / cookie
Áp dụng mọi môi trường:

| Setting | Giá trị |
|---|---|
| `SECURE_CONTENT_TYPE_NOSNIFF` | `True` |
| `SESSION_COOKIE_HTTPONLY` / `CSRF_COOKIE_HTTPONLY` | `True` |
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
- [ ] HTTPS + HSTS hoạt động, WebSocket qua `wss://`.
- [ ] Test phân quyền / cô lập tenant pass.

## 9. Việc cần làm (backlog bảo mật)
1. Chống brute-force đăng nhập (ví dụ `django-axes` hoặc rate limit ở Nginx cho `/accounts/login/`).
2. Rate limit `/api/public/` (Nginx `limit_req` hoặc middleware). Đã có cho `POST /api/public/takeaway/orders/` (10 đơn / 30 phút / IP / tenant); API QR tại bàn chưa có (BL-003).
3. Bắt buộc đổi mật khẩu lần đầu với tài khoản bootstrap.
4. Bổ sung Content-Security-Policy (hiện tải Bootstrap/ECharts/Font Awesome từ CDN).
