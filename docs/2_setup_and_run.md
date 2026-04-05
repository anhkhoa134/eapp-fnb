# 2) Setup và chạy local

## Điều kiện
- Python 3.10
- Virtualenv: `/Users/anhkhoa/Downloads/Project_django/env_10_web`
- Source: `/Users/anhkhoa/Downloads/Project_django/eapp-fnb`

## Kích hoạt môi trường
```bash
cd /Users/anhkhoa/Downloads/Project_django/eapp-fnb
source /Users/anhkhoa/Downloads/Project_django/env_10_web/bin/activate
pip install -r requirements.txt
```

Ghi chú: `requirements.txt` gồm Django và `openpyxl` (import Excel danh mục/sản phẩm trên trang Quản lý).

## Cấu hình env
File env được đọc tại `Project/.env`.

Biến quan trọng:
- `ENVIRONMENT=dev|prod`
- `DEBUG=true|false`
- `SECRET_KEY=...`
- `ALLOWED_HOSTS=127.0.0.1,localhost`
- `REAL_ADMIN_PATH=admin`
- `REDIS_URL=redis://127.0.0.1:6379` (WebSocket Channels)

Nếu dùng PostgreSQL, cần thêm:
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`

Rule DB theo settings:
- `ENVIRONMENT=prod`: bắt buộc dùng `POSTGRES_*`.
- `ENVIRONMENT=dev`: nếu để trống `POSTGRES_DB` thì dùng SQLite mặc định.

## Migrate và seed
```bash
python manage.py migrate
python manage.py seed_initial_data --reset-passwords --default-password 123456 --seed-qr-pending
```

## Tạo tenant nhanh trên Jazzmin (superadmin)
- Vào Django Admin/Jazzmin, tạo mới `Tenant`.
- Ngay khi tạo tenant mới, hệ thống tự bootstrap bộ dữ liệu cơ bản:
  - 1 manager + 2 staff (password mặc định: `123456`)
  - 1 store mặc định
  - 12 bàn (`BAN-01` → `BAN-12`) có `qr_token`
  - 2 category + 4 product có `ProductUnit`
- Username được tạo theo `public_slug`:
  - `<slug>_quanly`
  - `<slug>_nhanvien_1`
  - `<slug>_nhanvien_2`
- Luồng này phù hợp cho tenant mới cần bộ dữ liệu tối thiểu.
- Nếu cần dữ liệu demo đầy đủ (3 store, 8 category, 10 product, topping, QR pending), dùng `seed_initial_data`.

## Chạy server
```bash
python manage.py runserver 127.0.0.1:8000
```

Lưu ý realtime QR:
- Cần Redis chạy theo `REDIS_URL` để WebSocket hoạt động đầy đủ.
- Nếu Redis down, UI tự fallback sang polling 15s.
- Không dùng `--noasgi`, nếu không WebSocket sẽ bị fail.

Lệnh mở Redis local (nếu chưa có service):
```bash
redis-server
```

## URL chính
- POS: `http://127.0.0.1:8000/`
- Login: `http://127.0.0.1:8000/accounts/login/`
- Quản lý: `http://127.0.0.1:8000/quanly/`
- Đơn hôm nay: `http://127.0.0.1:8000/orders/today/`
- Public catalog: `http://127.0.0.1:8000/demo/`
- Public QR ordering: `http://127.0.0.1:8000/demo/qr/?table_code=<CODE>&token=<TOKEN>`

## Tài khoản demo
- Manager: `demo_quanly / 123456`
- Staff: `demo_nhanvien_1 / 123456`
