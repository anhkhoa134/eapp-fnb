# Hướng dẫn Chạy — Môi trường Dev (Local)

## 1. Yêu cầu
- Python 3.10+
- Redis (macOS: `brew install redis`)
- Virtual environment đã tạo tại `../env_10_web/`

## 2. Cấu hình `.env`
File `Project/.env` đã có sẵn. Đảm bảo các dòng sau tồn tại:
```env
ENVIRONMENT=dev
DEBUG=True
DATABASE_URL=sqlite:///db.sqlite3
REDIS_URL=redis://127.0.0.1:6379
```

## 3. Cài đặt phụ thuộc (lần đầu)
```bash
cd /Users/anhkhoa/Downloads/Project_django/eapp-pm
source ../env_10_web/bin/activate
pip install -r requirements.txt
python manage.py migrate
```

## 4. Seed dữ liệu demo (tuỳ chọn)
```bash
python manage.py seed_demo_data
```
Tài khoản demo: `demo / 123456`, `demo1–demo3 / 123456`

## 5. Chạy — 2 terminal song song

**Terminal 1 — Redis:**
```bash
/opt/homebrew/bin/redis-server
```
> Kiểm tra: `redis-cli ping` → `PONG`

**Terminal 2 — Django:**
```bash
cd /Users/anhkhoa/Downloads/Project_django/eapp-pm
source ../env_10_web/bin/activate
python manage.py runserver
```
> Khi `daphne` có trong `INSTALLED_APPS`, `runserver` tự dùng ASGI — WebSocket hoạt động ngay.

Truy cập:
- App: `http://127.0.0.1:8000/app/dashboard/`
- Login: `http://127.0.0.1:8000/auth/login/`
- WebSocket: `ws://127.0.0.1:8000/ws/messages/`

## 6. Kiểm tra nhanh
```bash
python manage.py check
redis-cli ping
```

---

*Tài liệu liên quan: [Deploy production](6_huong_dan_deploy_prod.md)*
