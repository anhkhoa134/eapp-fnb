# Setup nhanh

## 1) Kích hoạt môi trường
```bash
cd /Users/anhkhoa/Downloads/Project_django/eapp-fnb
source /Users/anhkhoa/Downloads/Project_django/env_10_web/bin/activate
```

## 2) Migrate DB
```bash
python manage.py migrate
```

## 3) Seed dữ liệu demo
```bash
python manage.py seed_initial_data --reset-passwords --default-password 123456 --seed-qr-pending
```

Tắt seed QR pending:
```bash
python manage.py seed_initial_data --no-seed-qr-pending
```

Tạo tenant nhanh trong Django Admin/Jazzmin (bằng tài khoản superadmin):
- Tạo mới `Tenant` ⇒ hệ thống tự tạo:
  - 1 manager + 2 staff (mật khẩu mặc định `123456`)
  - 1 store mặc định
  - 12 bàn có QR token
  - 2 category + 4 product có unit
- Username theo mẫu: `<slug>_quanly`, `<slug>_nhanvien_1`, `<slug>_nhanvien_2`.

## 4) Chạy server
```bash
python manage.py runserver 127.0.0.1:8000
```

Realtime QR qua WebSocket:
- Set `REDIS_URL` (mặc định `redis://127.0.0.1:6379`).
- Nếu Redis chưa sẵn sàng, UI sẽ fallback polling 15s.
- Không chạy `runserver --noasgi`.

Nếu chạy local Redis thủ công:
```bash
redis-server
```

## 5) Route chính
- POS nhân viên: `/`
- Đơn hàng trong ngày: `/orders/today/` (tùy chọn `?store_id=` lọc cửa hàng, `?page=` phân trang bảng; KPI vẫn theo toàn bộ đơn đã lọc)
- Quản lý tenant: `/quanly/`
- Quản lý QR bàn: `/quanly/qr-tables/`
- Đăng nhập: `/accounts/login/`
- Public catalog: `/<public_slug>/`
- Public QR ordering: `/<public_slug>/qr/?table_code=<CODE>&token=<TOKEN>`
- PWA: manifest `/manifest.webmanifest`, service worker `/sw.js`, trang offline `/offline/` — chi tiết xem `docs/10_pwa.md`

## 6) API QR chính
- Staff pending: `/api/pos/qr/orders?store_id=<id>&status=pending`
- Public create: `/api/public/qr/orders`
- Public detail: `/api/public/qr/orders/<id>?table_code=<CODE>&token=<TOKEN>`
- Public update: `PATCH /api/public/qr/orders/<id>/`
- Public cancel: `/api/public/qr/orders/<id>/cancel/`
