# 2) Công nghệ & phiên bản

Phiên bản ghi theo virtualenv đang dùng (`env_10_web`) tại thời điểm cập nhật tài liệu. Khi nâng cấp, sửa bảng này cùng lúc với `requirements.txt`.

## Backend
| Thành phần | Phiên bản | Vai trò | Dùng ở đâu |
|---|---|---|---|
| Python | 3.10 | Runtime | — |
| Django | 5.0.7 | Web framework | Toàn bộ |
| Django Channels | 4.3.0 | ASGI / WebSocket | `App_Sales/consumers.py`, `App_Public/consumers.py`, `Project/routing.py` |
| channels_redis | 4.3.0 | Channel layer Redis | `CHANNEL_LAYERS` trong `Project/settings.py` |
| Daphne | 4.2.1 | ASGI server (dev `runserver` + prod WebSocket) | `INSTALLED_APPS`, systemd prod |
| Gunicorn | 21.2.0 | WSGI server production (HTTP) | systemd prod |
| django-jazzmin | 3.0.1 | Giao diện Django Admin (tuỳ chọn — tự bật nếu cài) | `JAZZMIN_SETTINGS` |
| openpyxl | 3.1.5 | Import Excel danh mục / sản phẩm | `App_Quanly/catalog_excel.py` |
| Pillow | 10.4.0 | Xử lý ảnh sản phẩm, ảnh QR thanh toán | `App_Catalog/product_image_utils.py` |
| qrcode | 8.2 | Sinh ảnh QR bàn (PNG) | `App_Quanly/views.py` |
| reportlab | 4.0.8 | In PDF QR bàn khổ lớn | `App_Quanly/views.py` |
| psycopg2-binary | 2.9.9 | Driver PostgreSQL | Production |

## Hạ tầng dữ liệu
| Thành phần | Phiên bản | Vai trò |
|---|---|---|
| SQLite | (đi kèm Python) | DB mặc định môi trường dev |
| PostgreSQL | 14+ | DB production (bắt buộc khi `ENVIRONMENT=prod`) |
| Redis | 7+ | Channel layer cho WebSocket |

## Frontend (CDN, không có build step)
| Thành phần | Phiên bản | Vai trò |
|---|---|---|
| Bootstrap | 5.3.2 | Layout, component UI |
| Bootstrap Icons | 1.11.1 | Icon |
| Font Awesome | 6.4.2 | Icon trang POS (`App_Sales/index.html`) |
| Apache ECharts | 5.x | Biểu đồ dashboard quản lý |
| SortableJS | 1.15.2 | Kéo thả sắp xếp đơn vị, topping, bàn QR (`App_Quanly/_sortable_script.html`) |
| Vanilla JS | — | POS, gọi món QR, màn hình bếp (template Django + `fetch` + WebSocket) |
| Service Worker / Web App Manifest | — | PWA (`/sw.js`, `/manifest.webmanifest`) |

## Hạ tầng production
| Thành phần | Phiên bản | Vai trò |
|---|---|---|
| Ubuntu / Debian | 22.04+ / 12+ | OS server |
| Nginx | — | Reverse proxy, static/media, proxy `/ws/` |
| systemd | — | Quản lý Gunicorn, Daphne, Redis |
| Certbot (Let's Encrypt) | — | SSL |

Chi tiết: `docs/setup/6_production_env.md`.

## Công cụ phát triển
| Công cụ | Lệnh / ghi chú |
|---|---|
| Test runner | `python manage.py test` (Django `TestCase`, `channels.testing` cho WS) |
| Seed dữ liệu | `python manage.py seed_initial_data` |
| Script nội bộ | `scripts/run/*.py`, `scripts/pipeline.txt` |

## Lưu ý dependency
- `requirements.txt` pin đúng phiên bản bảng trên (`==`). Nâng cấp gói nào thì sửa cả hai nơi.
- Các gói phụ thuộc gián tiếp (`asgiref`, `redis`, `msgpack`, `twisted`, …) do pip tự kéo theo, không khai báo.
- Django 5.0 đã hết hạn hỗ trợ bảo mật (04/2025) — nên lên kế hoạch nâng cấp lên 5.2 LTS (xem `docs/backlog/`).
