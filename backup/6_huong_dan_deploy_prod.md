# Hướng dẫn Deploy — Production (VPS / Cloud)

## 1. Yêu cầu server
- Ubuntu 22.04+ (hoặc Debian 12+)
- Python 3.10+
- PostgreSQL 14+
- Redis 7+
- Nginx
- Systemd

---

## 2. Tạo user và thư mục dự án
```bash
# Tạo thư mục dự án (theo cấu hình hiện tại của bạn)
sudo mkdir -p /opt/Project_Django
git clone <repo-url> /opt/Project_Django/eapp-pm
cd /opt/Project_Django/eapp-pm
```

---

## 3. Cài đặt Python dependencies
```bash
python3 -m venv /opt/Project_Django/env_10_web
source /opt/Project_Django/env_10_web/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
# Package bắt buộc: channels[daphne], channels-redis, psycopg2-binary, gunicorn, uvicorn
pip install daphne channels channels-redis redis
```

---

## 4. Cấu hình `.env` Production
Tạo file `Project/.env`:
```bash
nano /opt/Project_Django/eapp-pm/Project/.env
```

```env
ENVIRONMENT=prod
DEBUG=False

# Tạo secret key: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
SECRET_KEY=<chuoi-ky-tu-ngau-nhien-manh>

# PostgreSQL
DATABASE_URL=postgres://eapppm_user:matkhau@127.0.0.1:5432/eapppm_db

# Domain
ALLOWED_HOSTS=pm.eapp.vn,www.pm.eapp.vn
CSRF_TRUSTED_ORIGINS=https://pm.eapp.vn,https://www.pm.eapp.vn

# Admin path ẩn
REAL_ADMIN_PATH=your-custom-admin-path

# HTTPS (đặt False nếu Nginx xử lý SSL, True nếu Django tự redirect)
SECURE_SSL_REDIRECT=False

# HSTS
SECURE_HSTS_SECONDS=31536000

# Redis
REDIS_URL=redis://127.0.0.1:6379

# Log
LOG_LEVEL=INFO
```

---

## 5. Cài và cấu hình PostgreSQL
```bash
sudo apt install postgresql postgresql-contrib -y
sudo -u postgres psql

-- Trong psql:
CREATE DATABASE eapppm_db;
CREATE USER eapppm_user WITH PASSWORD 'matkhau';
ALTER ROLE eapppm_user SET client_encoding TO 'utf8';
ALTER ROLE eapppm_user SET default_transaction_isolation TO 'read committed';
GRANT ALL PRIVILEGES ON DATABASE eapppm_db TO eapppm_user;
\q
```

```bash
# Chạy migration
source /opt/Project_Django/env_10_web/bin/activate
cd /opt/Project_Django/eapp-pm
python manage.py migrate
python manage.py collectstatic --noinput
```

---

## 6. Cài và cấu hình Redis
```bash
sudo apt install redis-server -y

# Cấu hình Redis bind localhost only
sudo nano /etc/redis/redis.conf
# Đảm bảo dòng: bind 127.0.0.1 ::1
# Đảm bảo dòng: supervised systemd

sudo systemctl enable redis-server
sudo systemctl start redis-server
redis-cli ping  # → PONG
```

---

## 7. Systemd — Gunicorn (HTTP), socket activation

**Làm bước này trước:** Gunicorn (WSGI) phục vụ **HTTP** (trang web, API). Sau đó có thể bật Nginx chỉ với `location /` (mục 9). **WebSocket** (`/ws/…`) cần thêm **Daphne** (mục 8) và block `location /ws/` trên Nginx.

Thiết lập dưới đây khớp với bản lưu trong `backup/production.md`: **socket unit** tạo sẵn `/run/gunicorn-eapp-pm.sock`, service Gunicorn `Requires` socket đó (không tự tạo socket khi bind).

### 7.1 Socket unit

```bash
sudo nano /etc/systemd/system/gunicorn-eapp-pm.socket
```

```ini
[Unit]
Description=gunicorn socket for eapp-pm

[Socket]
ListenStream=/run/gunicorn-eapp-pm.sock

[Install]
WantedBy=sockets.target
```

### 7.2 Service unit

```bash
sudo nano /etc/systemd/system/gunicorn-eapp-pm.service
```

```ini
[Unit]
Description=gunicorn daemon for eapp-pm
Requires=gunicorn-eapp-pm.socket
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/Project_Django/eapp-pm
EnvironmentFile=/opt/Project_Django/eapp-pm/Project/.env
Environment="PATH=/opt/Project_Django/env_10_web/bin"
ExecStart=/opt/Project_Django/env_10_web/bin/gunicorn \
--access-logfile - \
--error-logfile - \
--workers 3 \
--timeout 300 \
--bind unix:/run/gunicorn-eapp-pm.sock \
Project.wsgi:application

[Install]
WantedBy=multi-user.target
```

### 7.3 Kích hoạt

```bash
sudo systemctl daemon-reload
sudo systemctl enable gunicorn-eapp-pm.socket
sudo systemctl start gunicorn-eapp-pm.socket
sudo systemctl enable gunicorn-eapp-pm.service
sudo systemctl start gunicorn-eapp-pm.service
sudo systemctl status gunicorn-eapp-pm.service
```

> **Triển khai chỉ HTTP:** Có thể dùng Nginx chỉ với `location /` proxy tới `unix:/run/gunicorn-eapp-pm.sock` (như ví dụ tối giản trong `backup/production.md`, không cần `location /ws/`). Khi bật chat/WebSocket, bổ sung Daphne (mục 8) và block `location /ws/` ở mục 9.

---

## 8. Systemd — Daphne (ASGI + WebSocket)

**Sau Gunicorn (mục 7):** **HTTP** vẫn do Gunicorn xử lý; **Daphne** chạy **ASGI** cho **WebSocket**. Nginx proxy `/ws/` sang socket Daphne (cấu hình đầy đủ ở mục 9). Cần **Redis** (mục 6) cho channel layer.

Tạo file service:
```bash
sudo nano /etc/systemd/system/daphne-eapp-pm.service
```

```ini
[Unit]
Description=eapp-pm — Daphne ASGI Server (WebSocket)
After=network.target redis-server
Requires=redis-server

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/Project_Django/eapp-pm
Environment="DJANGO_SETTINGS_MODULE=Project.settings"
EnvironmentFile=/opt/Project_Django/eapp-pm/Project/.env
Environment="PATH=/opt/Project_Django/env_10_web/bin"
ExecStart=/opt/Project_Django/env_10_web/bin/daphne \
    -u /run/daphne-eapp-pm.sock \
    --proxy-headers \
    Project.asgi:application
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=daphne-eapp-pm

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable daphne-eapp-pm
sudo systemctl start daphne-eapp-pm
sudo systemctl status daphne-eapp-pm
```

> Tùy chọn (socket-activated cho Daphne)
> Nếu bạn muốn systemd tạo unix socket trước bằng unit `.socket`, bạn có thể tạo file:
> ```bash
> sudo nano /etc/systemd/system/daphne-eapp-pm.socket
> ```
> ```ini
> [Socket]
> ListenStream=/run/daphne-eapp-pm.sock
> ```
> Sau đó trong `daphne-eapp-pm.service`, bạn cần đổi `ExecStart` để Daphne đọc file descriptor từ systemd (thường dùng `--fd 3`). Nếu bạn chưa chắc, hãy dùng `.service` như ở trên trước để đảm bảo `/ws/messages/` hoạt động ổn định.

---

## 9. Cấu hình Nginx (HTTP + WebSocket)

Đặt **sau** mục 7 (Gunicorn); block `location /ws/` chỉ có ý nghĩa khi đã bật Daphne (mục 8).

```bash
sudo apt install nginx -y
sudo nano /etc/nginx/sites-available/eapp-pm
```

```nginx
server {
    listen 80;
    server_name pm.eapp.vn www.pm.eapp.vn;

    access_log /var/log/nginx/eapp-pm.log;

    location = /favicon.ico { access_log off; log_not_found off; }

    location /static/ {
        alias /opt/Project_Django/eapp-pm/staticfiles/;
    }

    location /media/ {
        alias /opt/Project_Django/eapp-pm/media/;
    }

    # WebSocket — cần header Upgrade + proxy sang Daphne (ASGI)
    location /ws/ {
        proxy_pass http://unix:/run/daphne-eapp-pm.sock;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }

    # HTTP — tất cả request còn lại (WSGI) qua Gunicorn
    location / {
        include proxy_params;
        proxy_pass http://unix:/run/gunicorn-eapp-pm.sock;

        proxy_set_header X-Forwarded-Host $server_name;
        proxy_set_header X-Real-IP $remote_addr;
        add_header P3P 'CP="ALLDSP COR PSAa PSDa OURNOR ONL UNI COM NAV"';

        proxy_connect_timeout 300;
        proxy_send_timeout 300;
        proxy_read_timeout 300;
    }

    client_max_body_size 20M;
}
```

```bash
sudo ln -s /etc/nginx/sites-available/eapp-pm /etc/nginx/sites-enabled/
sudo nginx -t          # kiểm tra config
sudo systemctl reload nginx
```

---

## 10. HTTPS với Let's Encrypt (Certbot)
```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d pm.eapp.vn -d www.pm.eapp.vn
# Certbot tự sửa nginx config thêm SSL, tự renew
sudo systemctl enable certbot.timer
```

> Lưu ý: Sau khi Certbot tạo thêm `server` cho HTTPS (port 443), hãy đảm bảo block HTTPS cũng có `location /ws/` proxy sang Daphne (giống phần `server` ở port 80). Nếu thiếu, `wss://.../ws/messages/` sẽ không connect được.

Sau khi có SSL, cập nhật `.env`:
```env
SECURE_SSL_REDIRECT=True
```

---

## 11. Tóm tắt các lệnh quản lý service

```bash
# Xem trạng thái (HTTP trước, WebSocket sau)
sudo systemctl status gunicorn-eapp-pm
sudo systemctl status daphne-eapp-pm
sudo systemctl status redis-server
sudo systemctl status nginx

# Xem log realtime
sudo journalctl -u gunicorn-eapp-pm -f
sudo journalctl -u daphne-eapp-pm -f

# Restart sau khi deploy code mới
cd /opt/Project_Django/eapp-pm
git pull
source /opt/Project_Django/env_10_web/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart gunicorn-eapp-pm
sudo systemctl restart daphne-eapp-pm
sudo systemctl reload nginx

# Restart Redis
sudo systemctl restart redis-server

# Kiểm tra endpoint HTTP (ít nhất để biết Nginx/Gunicorn chạy đúng)
redis-cli ping                          # → PONG
python manage.py check                  # → no issues
curl -I http://127.0.0.1/app/dashboard/  # → 302 hoặc 200
```

---

## 12. Kiểm tra WebSocket sau deploy

**Cách 1 — Python (dùng `websockets`, không cần Node.js):**
```bash
pip install websockets

python3 - <<'EOF'
import asyncio, websockets, sys

async def test():
    url = "wss://pm.eapp.vn/ws/messages/"
    try:
        async with websockets.connect(url) as ws:
            print(f"✓ Kết nối thành công: {url}")
            print(f"  State: {ws.state.name}")
    except Exception as e:
        print(f"✗ Lỗi: {e}", file=sys.stderr)

asyncio.run(test())
EOF
```

**Cách 2 — `curl` kiểm tra HTTP upgrade header:**
```bash
# Server phải trả 101 Switching Protocols (upgrade thành công)
curl -i \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  https://pm.eapp.vn/ws/messages/

# Kết quả mong đợi: HTTP/1.1 101 Switching Protocols
```

**Cách 3 — Browser DevTools Console (không cần cài gì):**
```javascript
// Mở F12 → Console, dán đoạn sau (cần đang đăng nhập):
let ws = new WebSocket("wss://pm.eapp.vn/ws/messages/")
ws.onopen  = () => console.log("✓ WS connected")
ws.onclose = (e) => console.log("WS closed — code:", e.code, e.reason)
ws.onerror = (e) => console.error("WS error", e)
```

---

## 13. Sơ đồ kiến trúc Production

```
Internet
    │
    ▼
[Nginx :443/80]  ──/static/──►  staticfiles/ (disk)
    │
    ├── /*     ──► [Gunicorn unix:/run/gunicorn-eapp-pm.sock]  ──► Django Views (HTTP / WSGI)
    │                    │
    └── /ws/*  ──► [Daphne unix:/run/daphne-eapp-pm.sock]     ──► WebSocket Consumer
                         │
                    [Redis :6379]  ──► Channel Layer (WS groups)
                    [PostgreSQL]   ──► Database
```

---

*Tài liệu liên quan: [Chạy dev (local)](5_huong_dan_deploy_dev.md)*

