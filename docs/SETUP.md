# Setup nhanh

## 1) Kích hoạt môi trường
```bash
source /Users/anhkhoa/Downloads/Project_django/env_10_web/bin/activate
```

## 2) Migrate DB
```bash
python manage.py makemigrations
python manage.py migrate
```

## 3) Seed dữ liệu demo
```bash
python manage.py seed_initial_data --reset-passwords --default-password 123456
```

## 4) Chạy server
```bash
python manage.py runserver
```

## 5) Route chính
- POS nhân viên: `/`
- Public tenant: `/demo/` (hoặc `/<public_slug>/`)
- Quản lý tenant: `/quanly/`
- Đăng nhập: `/accounts/login/`
- API products: `/api/pos/products?store_id=<id>`
- API checkout: `/api/pos/checkout`
