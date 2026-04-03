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
- `DEBUG=true|false`
- `SECRET_KEY=...`
- `ALLOWED_HOSTS=127.0.0.1,localhost`
- `DB_ENGINE=sqlite|postgres`
- `REDIS_URL=redis://127.0.0.1:6379/1` (WebSocket Channels)

Neu `DB_ENGINE=postgres`, can them:
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`

## Migrate va seed
```bash
python manage.py migrate
python manage.py seed_initial_data --reset-passwords --default-password 123456 --seed-qr-pending
```

## Chay server
```bash
python manage.py runserver 127.0.0.1:8000
```

Luu y realtime QR:
- Can Redis chay theo `REDIS_URL` de WebSocket hoat dong day du.
- Neu Redis down, UI tu fallback sang polling 15s.

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
