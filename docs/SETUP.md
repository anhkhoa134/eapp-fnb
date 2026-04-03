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

## 4) Chạy server
```bash
python manage.py runserver 127.0.0.1:8000
```

Realtime QR qua WebSocket:
- Set `REDIS_URL` (mac dinh `redis://127.0.0.1:6379/1`).
- Neu Redis chua san sang, UI se fallback polling 15s.

## 5) Route chính
- POS nhân viên: `/`
- Đơn hàng trong ngày: `/orders/today/`
- Quản lý tenant: `/quanly/`
- Quản lý QR bàn: `/quanly/qr-tables/`
- Đăng nhập: `/accounts/login/`
- Public catalog: `/<public_slug>/`
- Public QR ordering: `/<public_slug>/qr/?table_code=<CODE>&token=<TOKEN>`

## 6) API QR chính
- Staff pending: `/api/pos/qr/orders?store_id=<id>&status=pending`
- Public create: `/api/public/qr/orders`
- Public detail: `/api/public/qr/orders/<id>?table_code=<CODE>&token=<TOKEN>`
- Public update: `PATCH /api/public/qr/orders/<id>/`
- Public cancel: `/api/public/qr/orders/<id>/cancel/`
