# 2) Setup va chay local

## Dieu kien
- Python 3.10
- Virtualenv da tao san: `/Users/anhkhoa/Downloads/Project_django/env_10_web`
- Thu muc code: `/Users/anhkhoa/Downloads/Project_django/eapp-fnb`

## Kich hoat moi truong
```bash
cd /Users/anhkhoa/Downloads/Project_django/eapp-fnb
source /Users/anhkhoa/Downloads/Project_django/env_10_web/bin/activate
```

## Cau hinh env
File env duoc doc tai `Project/.env`.

Gia tri quan trong:
- `DEBUG=true|false`
- `SECRET_KEY=...`
- `ALLOWED_HOSTS=127.0.0.1,localhost`
- `DB_ENGINE=sqlite` hoac `DB_ENGINE=postgres`

Neu dung postgres, can them:
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`

## Khoi tao database
```bash
python manage.py migrate
```

## Seed du lieu demo
```bash
python manage.py seed_initial_data --reset-passwords --default-password 123456 --seed-qr-pending
```

## Chay server
```bash
python manage.py runserver 127.0.0.1:8000
```

## URL chinh
- POS: `http://127.0.0.1:8000/`
- Quan ly: `http://127.0.0.1:8000/quanly/`
- Login: `http://127.0.0.1:8000/accounts/login/`
- Public demo: `http://127.0.0.1:8000/demo/`
- Don hang trong ngay: `http://127.0.0.1:8000/orders/today/`
