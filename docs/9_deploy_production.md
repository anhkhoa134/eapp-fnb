# Hướng Dẫn Deploy Production (VPS/Cloud)

## 1. Yêu cầu server
- Ubuntu 22.04+ (hoặc Debian 12+)
- Python 3.10+
- PostgreSQL 14+
- Redis 7+
- Nginx
- Systemd

## 2. Clone source và tạo virtualenv
```bash
sudo mkdir -p /opt/Project_Django
git clone <repo-url> /opt/Project_Django/eapp-fnb
cd /opt/Project_Django/eapp-fnb

python3 -m venv /opt/Project_Django/env_10_web
source /opt/Project_Django/env_10_web/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 3. Cấu hình `.env` production
Tạo file `/opt/Project_Django/eapp-fnb/Project/.env`:
```env
ENVIRONMENT=prod
DEBUG=False
SECRET_KEY=<secret-key-random-strong>

POSTGRES_DB=eappfnb_db
POSTGRES_USER=eappfnb_user
POSTGRES_PASSWORD=<db-password>
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432

ALLOWED_HOSTS=pos.example.com,www.pos.example.com
CSRF_TRUSTED_ORIGINS=https://pos.example.com,https://www.pos.example.com
REAL_ADMIN_PATH=secure-admin-portal
SECURE_SSL_REDIRECT=False
SECURE_HSTS_SECONDS=31536000
LOG_LEVEL=INFO
REDIS_URL=redis://127.0.0.1:6379
```

Tạo `SECRET_KEY`:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## 4. Cài PostgreSQL
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib -y
sudo -u postgres psql
```

Trong `psql`:
```sql
CREATE DATABASE eappfnb_db;
CREATE USER eappfnb_user WITH PASSWORD '<db-password>';
GRANT ALL PRIVILEGES ON DATABASE eappfnb_db TO eappfnb_user;
\q
```

## 5. Cài Redis
```bash
sudo apt install redis-server -y
sudo systemctl enable redis-server
sudo systemctl start redis-server
redis-cli ping
```

Kỳ vọng: `PONG`.

## 6. Migrate và collect static
```bash
cd /opt/Project_Django/eapp-fnb
source /opt/Project_Django/env_10_web/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check
```

## 7. Systemd Gunicorn (HTTP)
Tạo `/etc/systemd/system/gunicorn-eapp-fnb.socket`:
```ini
[Unit]
Description=gunicorn socket for eapp-fnb

[Socket]
ListenStream=/run/gunicorn-eapp-fnb.sock

[Install]
WantedBy=sockets.target
```

Tạo `/etc/systemd/system/gunicorn-eapp-fnb.service`:
```ini
[Unit]
Description=gunicorn daemon for eapp-fnb
Requires=gunicorn-eapp-fnb.socket
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/Project_Django/eapp-fnb
EnvironmentFile=/opt/Project_Django/eapp-fnb/Project/.env
Environment="PATH=/opt/Project_Django/env_10_web/bin"
ExecStart=/opt/Project_Django/env_10_web/bin/gunicorn \
--access-logfile - \
--error-logfile - \
--workers 3 \
--timeout 300 \
--bind unix:/run/gunicorn-eapp-fnb.sock \
Project.wsgi:application

[Install]
WantedBy=multi-user.target
```

Kích hoạt:
```bash
sudo systemctl daemon-reload
sudo systemctl enable gunicorn-eapp-fnb.socket
sudo systemctl start gunicorn-eapp-fnb.socket
sudo systemctl enable gunicorn-eapp-fnb.service
sudo systemctl start gunicorn-eapp-fnb.service
sudo systemctl status gunicorn-eapp-fnb.service
```

## 8. Systemd Daphne (WebSocket)
Tạo `/etc/systemd/system/daphne-eapp-fnb.service`:
```ini
[Unit]
Description=eapp-fnb daphne asgi server
After=network.target redis-server
Requires=redis-server

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/Project_Django/eapp-fnb
Environment="DJANGO_SETTINGS_MODULE=Project.settings"
EnvironmentFile=/opt/Project_Django/eapp-fnb/Project/.env
Environment="PATH=/opt/Project_Django/env_10_web/bin"
ExecStart=/opt/Project_Django/env_10_web/bin/daphne \
    -u /run/daphne-eapp-fnb.sock \
    --proxy-headers \
    Project.asgi:application
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Kích hoạt:
```bash
sudo systemctl daemon-reload
sudo systemctl enable daphne-eapp-fnb
sudo systemctl start daphne-eapp-fnb
sudo systemctl status daphne-eapp-fnb
```

## 9. Nginx (HTTP + WS)
Tạo `/etc/nginx/sites-available/eapp-fnb`:
```nginx
server {
    listen 80;
    server_name pos.example.com www.pos.example.com;

    location /static/ {
        alias /opt/Project_Django/eapp-fnb/staticfiles/;
    }

    location /media/ {
        alias /opt/Project_Django/eapp-fnb/media/;
    }

    location /ws/ {
        proxy_pass http://unix:/run/daphne-eapp-fnb.sock;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400s;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/gunicorn-eapp-fnb.sock;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
        proxy_read_timeout 300;
    }
}
```

Kích hoạt:
```bash
sudo ln -s /etc/nginx/sites-available/eapp-fnb /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## 10. SSL (Let's Encrypt)
```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d pos.example.com -d www.pos.example.com
sudo systemctl enable certbot.timer
```

Sau khi bật SSL, sửa `.env`:
```env
SECURE_SSL_REDIRECT=True
```

Sau đó restart services:
```bash
sudo systemctl restart gunicorn-eapp-fnb
sudo systemctl restart daphne-eapp-fnb
sudo systemctl reload nginx
```

## 11. Kiểm tra sau deploy
```bash
sudo systemctl status gunicorn-eapp-fnb
sudo systemctl status daphne-eapp-fnb
sudo systemctl status redis-server
sudo systemctl status nginx

redis-cli ping
cd /opt/Project_Django/eapp-fnb
source /opt/Project_Django/env_10_web/bin/activate
python manage.py check
```

Kiểm tra WebSocket bằng browser console (sau khi login POS):
```javascript
const ws = new WebSocket("wss://pos.example.com/ws/pos/store/1/");
ws.onopen = () => console.log("WS POS connected");
ws.onclose = (e) => console.log("WS closed", e.code, e.reason);
ws.onerror = (e) => console.log("WS error", e);
```

## 12. Quy trình deploy bản mới
```bash
cd /opt/Project_Django/eapp-fnb
git pull
source /opt/Project_Django/env_10_web/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check
sudo systemctl restart gunicorn-eapp-fnb
sudo systemctl restart daphne-eapp-fnb
sudo systemctl reload nginx
```
