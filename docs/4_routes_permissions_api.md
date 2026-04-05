# 4) Route, permission, API contracts

## Web routes
- `GET /` → POS (staff/manager, login required).
- `GET /orders/today/` → đơn hôm nay (staff/manager, login required).
- `GET /quanly/*` → manager only.
- `GET /accounts/login/` → login.
- `POST /accounts/logout/` → logout.
- `GET /<public_slug>/` → public catalog.
- `GET /<public_slug>/qr/?table_code=&token=` → public QR ordering UI.
- `GET /manifest.webmanifest` → Web App Manifest (PWA).
- `GET /sw.js` → service worker (PWA).
- `GET /offline/` → trang fallback khi ngoại tuyến (PWA).

Chi tiết: `docs/10_pwa.md`.

## Security notes
- `GET /accounts/logout/` ⇒ 405.
- Public QR APIs bắt buộc `table_code + token` hợp lệ.
- POS APIs chỉ thao tác trên store user được cấp quyền.
- POS WebSocket cần login + có quyền store.
- Public WebSocket cần `table_code + token` hợp lệ và order thuộc đúng bàn.

## POS API (`/api/pos/`)
- `GET products/?store_id=&q=&category=`
- `POST checkout/`
- `GET tables/?store_id=`
- `GET tables/<table_id>/cart/`
- `POST tables/<table_id>/cart/items/`
- `PATCH tables/<table_id>/cart/items/<item_id>/`
- `DELETE tables/<table_id>/cart/items/<item_id>/`
- `POST tables/<table_id>/cart/import-takeaway/`
- `POST tables/<table_id>/checkout/`
- `GET qr/orders/?store_id=&status=pending|approved|rejected|cancelled`
- `POST qr/orders/<order_id>/approve/`
- `POST qr/orders/<order_id>/reject/`

Ghi chú hành vi POS (frontend, `templates/App_Sales/index.html`): chọn bàn khi đang **mang về** có món → `POST .../cart/import-takeaway/` rồi `GET .../cart/`; **Đổi sang mang về** khi đang gắn bàn → `DELETE .../cart/items/<item_id>/` cho từng dòng rồi giữ giỏ trên client dạng mang về.

## Public API (`/api/public/`)
- `POST qr/orders/` → tạo đơn pending.
- `GET qr/orders/<order_id>/?table_code=&token=` → lấy trạng thái + items.
- `PATCH qr/orders/<order_id>/` → cập nhật đơn pending (replace items + note).
- `POST qr/orders/<order_id>/cancel/` → hủy đơn pending (`CANCELLED`).

## WebSocket routes
- `GET ws://<host>/ws/pos/store/<store_id>/`
- `GET ws://<host>/ws/public/qr/order/<order_id>/?table_code=&token=`

## WebSocket message schema
- POS:
  - `{ "type": "qr.changed", "store_id": <id>, "order_id": <id>, "reason": "created|updated|approved|rejected|cancelled", "ts": "<iso>" }`
- Public QR:
  - `{ "type": "qr.order.changed", "order_id": <id>, "status": "PENDING|APPROVED|REJECTED|CANCELLED", "reason": "...", "ts": "<iso>" }`

## Quanly API-like routes (server-rendered)

Tất cả dưới đây yêu cầu **manager** (trừ khi ghi chú khác).

- `GET|POST /quanly/` — dashboard (`GET`: `store`, `period` = `7d` \| `30d` \| `this_month` \| `last_month` \| `this_year` \| `last_year`, hoặc `date_from` / `date_to` khi `period` trống)
- `GET|POST /quanly/stores/` — CRUD cửa hàng (POST tạo; POST edit/delete theo URL riêng)
- `GET|POST /quanly/account/` — cài đặt tài khoản quản lý
- `GET /quanly/orders/`, `POST /quanly/orders/<id>/delete/` — lịch sử đơn
- `GET|POST /quanly/categories/`, `.../products/`, `.../toppings/`, ... — catalog CRUD (xem `App_Quanly/urls.py`)
- `GET|POST /quanly/payment-qr/` — cấu hình QR thanh toán POS theo cửa hàng
- `GET|POST /quanly/staffs/` — quản lý nhân viên
- `GET|POST /quanly/qr-tables/`
- `GET|POST /quanly/qr-tables/<id>/edit/`
- `POST /quanly/qr-tables/<id>/delete/`
- `POST /quanly/qr-tables/<id>/reset-token/`
- `GET /quanly/qr-tables/<id>/png/`
- `GET /quanly/qr-tables/print-pdf/?store=<id>`

## Phân trang (danh sách render server)

- **Kích thước trang:** 20 bản ghi (cùng mức với lịch sử đơn).
- **Partial dùng chung:** `templates/App_Quanly/_list_pagination.html` — liên kết *Trước* / *Sau* và hiển thị `Trang n/tổng`.
- **Quản lý** — tham số GET `page` trên:
  - `/quanly/stores/`, `/quanly/categories/`, `/quanly/products/`, `/quanly/staffs/`, `/quanly/qr-tables/`
  - Trên **QR bàn**, bộ lọc `?store=<id>` được giữ khi chuyển trang.
- **Quản lý → Topping** (`/quanly/toppings/`): hai bảng độc lập:
  - `page` — danh sách topping;
  - `mpage` — bảng gán topping theo sản phẩm;
  - Link phân trang của mỗi bảng giữ tham số của bảng còn lại (ví dụ đổi trang topping không reset trang gán).
- **Đơn trong ngày** `GET /orders/today/?store_id=&page=`:
  - Các chỉ số KPI (tổng đơn, doanh thu, giá trị đơn trung bình) tính trên **toàn bộ** đơn sau khi lọc cửa hàng;
  - Chỉ **bảng chi tiết** theo từng trang.
- **Đã có từ trước (không đổi):** lịch sử đơn `/quanly/orders/`, catalog public (paginator riêng theo app).
- **Dashboard** `/quanly/`: khối **Đơn gần nhất** vẫn giới hạn cố định trên server (không dùng tham số `page`).

## Payment rule
- `cash`: `customer_paid >= total_amount`.
- `card`: nếu `customer_paid <= 0` backend set bằng `total_amount`.
