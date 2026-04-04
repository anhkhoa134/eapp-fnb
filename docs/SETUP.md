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

Tao tenant nhanh trong Django Admin/Jazzmin (bang tai khoan superadmin):
- Tao moi `Tenant` => he thong tu tao:
  - 1 manager + 2 staff (mat khau mac dinh `123456`)
  - 1 store mac dinh
  - 12 ban co QR token
  - 2 category + 4 product co unit
- Username theo mau: `<slug>_quanly`, `<slug>_nhanvien_1`, `<slug>_nhanvien_2`.

## 4) Chạy server
```bash
python manage.py runserver 127.0.0.1:8000
```

Realtime QR qua WebSocket:
- Set `REDIS_URL` (mac dinh `redis://127.0.0.1:6379`).
- Neu Redis chua san sang, UI se fallback polling 15s.
- Khong chay `runserver --noasgi`.

Neu chay local Redis thu cong:
```bash
redis-server
```

## 5) Route chính
- POS nhân viên: `/`
- Đơn hàng trong ngày: `/orders/today/`
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
