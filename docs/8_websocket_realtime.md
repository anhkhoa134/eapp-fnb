# 8) WebSocket realtime QR

## Muc tieu
- POS nhan thay doi don QR theo store theo thoi gian thuc.
- Public QR nhan thay doi trang thai don theo order theo thoi gian thuc.
- Neu WS fail/disconnect, UI fallback polling 15s.

## Endpoint
- POS: `ws://<host>/ws/pos/store/<store_id>/`
- Public QR: `ws://<host>/ws/public/qr/order/<order_id>/?table_code=<CODE>&token=<TOKEN>`

## Event duoc push
- POS:
  - `qr.changed` voi `reason`: `created|updated|approved|rejected|cancelled`
- Public QR:
  - `qr.order.changed` voi `status`: `PENDING|APPROVED|REJECTED|CANCELLED`

## Dieu kien de WS hoat dong
1. Server chay ASGI (`python manage.py runserver ...`, khong dung `--noasgi`).
2. Redis hoat dong theo `REDIS_URL`.
3. Session/quyen hop le:
   - POS: user login + co quyen store.
   - Public: `table_code + token` hop le va order thuoc dung ban.

## Troubleshooting nhanh
- Loi browser:
  - `WebSocket connection ... failed`
- Kiem tra:
  1. `python manage.py help runserver` phai co option `--noasgi` (dau hieu dang dung daphne/channels runserver).
  2. Redis da mo chua (`redis-server`).
  3. URL socket dung host/protocol (`ws://` cho http, `wss://` cho https).
  4. User POS co quyen `store_id` dang mo.
- Ket qua mong doi khi Redis down:
  - Khong realtime WS.
  - UI van cap nhat theo fallback polling 15s.
