# 8) WebSocket realtime QR

## Mục tiêu
- POS nhận thay đổi đơn QR theo store theo thời gian thực.
- Public QR nhận thay đổi trạng thái đơn theo order theo thời gian thực.
- Nếu WS fail/disconnect, UI fallback polling 15s.

## Endpoint
- POS: `ws://<host>/ws/pos/store/<store_id>/`
- Public QR: `ws://<host>/ws/public/qr/order/<order_id>/?table_code=<CODE>&token=<TOKEN>`

## Event được push
- POS:
  - `qr.changed` với `reason`: `created|updated|approved|rejected|cancelled`
- Public QR:
  - `qr.order.changed` với `status`: `PENDING|APPROVED|REJECTED|CANCELLED`

## Điều kiện để WS hoạt động
1. Server chạy ASGI (`python manage.py runserver ...`, không dùng `--noasgi`).
2. Redis hoạt động theo `REDIS_URL`.
3. Session/quyền hợp lệ:
   - POS: user login + có quyền store.
   - Public: `table_code + token` hợp lệ và order thuộc đúng bàn.

## Troubleshooting nhanh
- Lỗi browser:
  - `WebSocket connection ... failed`
- Kiểm tra:
  1. `python manage.py help runserver` phải có option `--noasgi` (dấu hiệu đang dùng daphne/channels runserver).
  2. Redis đã mở chưa (`redis-server`).
  3. URL socket đúng host/protocol (`ws://` cho http, `wss://` cho https).
  4. User POS có quyền `store_id` đang mở.
- Kết quả mong đợi khi Redis down:
  - Không realtime WS.
  - UI vẫn cập nhật theo fallback polling 15s.
