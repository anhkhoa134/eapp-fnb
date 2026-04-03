# 2) Setup va chay local

## Dieu kien
- Python 3.10
- Virtualenv: `/Users/anhkhoa/Downloads/Project_django/env_10_web`
- Source: `/Users/anhkhoa/Downloads/Project_django/eapp-fnb`

## Kich hoat moi truong
```bash
cd /Users/anhkhoa/Downloads/Project_django/eapp-fnb
source /Users/anhkhoa/Downloads/Project_django/env_10_web/bin/activate
```

## Cau hinh env
File env duoc doc tai `Project/.env`.

Bien quan trong:
- `ENVIRONMENT=dev|prod`
- `DEBUG=true|false`
- `SECRET_KEY=...`
- `ALLOWED_HOSTS=127.0.0.1,localhost`
- `REAL_ADMIN_PATH=admin`
- `REDIS_URL=redis://127.0.0.1:6379` (WebSocket Channels)

Neu dung PostgreSQL, can them:
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`

Rule DB theo settings:
- `ENVIRONMENT=prod`: bat buoc dung `POSTGRES_*`.
- `ENVIRONMENT=dev`: neu de trong `POSTGRES_DB` thi dung SQLite mac dinh.

## Migrate va seed
```bash
python manage.py migrate
python manage.py seed_initial_data --reset-passwords --default-password 123456 --seed-qr-pending
```

## Tao tenant nhanh tren Jazzmin (superadmin)
- Vao Django Admin/Jazzmin, tao moi `Tenant`.
- Ngay khi tao tenant moi, he thong tu bootstrap bo du lieu co ban:
  - 1 manager + 2 staff (password mac dinh: `123456`)
  - 1 store mac dinh
  - 12 ban (`BAN-01` -> `BAN-12`) co `qr_token`
  - 2 category + 4 product co `ProductUnit`
- Username duoc tao theo `public_slug`:
  - `<slug>_quanly`
  - `<slug>_nhanvien_1`
  - `<slug>_nhanvien_2`
- Luong nay phu hop cho tenant moi can bo du lieu toi thieu.
- Neu can du lieu demo day du (3 store, 8 category, 10 product, topping, QR pending), dung `seed_initial_data`.

## Chay server
```bash
python manage.py runserver 127.0.0.1:8000
```

Luu y realtime QR:
- Can Redis chay theo `REDIS_URL` de WebSocket hoat dong day du.
- Neu Redis down, UI tu fallback sang polling 15s.
- Khong dung `--noasgi`, neu khong WebSocket se bi fail.

Lenh mo Redis local (neu chua co service):
```bash
redis-server
```

## URL chinh
- POS: `http://127.0.0.1:8000/`
- Login: `http://127.0.0.1:8000/accounts/login/`
- Quan ly: `http://127.0.0.1:8000/quanly/`
- Don hom nay: `http://127.0.0.1:8000/orders/today/`
- Public catalog: `http://127.0.0.1:8000/demo/`
- Public QR ordering: `http://127.0.0.1:8000/demo/qr/?table_code=<CODE>&token=<TOKEN>`

## Tai khoan demo
- Manager: `demo_quanly / 123456`
- Staff: `demo_nhanvien_1 / 123456`
