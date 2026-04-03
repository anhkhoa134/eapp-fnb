# 4) Route, permission, API contracts

## Web routes
- `GET /` -> POS (staff/manager, login required).
- `GET /orders/today/` -> don hom nay (staff/manager, login required).
- `GET /quanly/*` -> manager only.
- `GET /accounts/login/` -> login.
- `POST /accounts/logout/` -> logout.
- `GET /<public_slug>/` -> public catalog.
- `GET /<public_slug>/qr/?table_code=&token=` -> public QR ordering UI.

## Security notes
- `GET /accounts/logout/` => 405.
- Public QR APIs bat buoc `table_code + token` hop le.
- POS APIs chi thao tac tren store user duoc cap quyen.
- POS WebSocket can login + co quyen store.
- Public WebSocket can `table_code + token` hop le va order thuoc dung ban.

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

## Public API (`/api/public/`)
- `POST qr/orders/` -> tao don pending.
- `GET qr/orders/<order_id>/?table_code=&token=` -> lay trang thai + items.
- `PATCH qr/orders/<order_id>/` -> cap nhat don pending (replace items + note).
- `POST qr/orders/<order_id>/cancel/` -> huy don pending (`CANCELLED`).

## WebSocket routes
- `GET ws://<host>/ws/pos/store/<store_id>/`
- `GET ws://<host>/ws/public/qr/order/<order_id>/?table_code=&token=`

## Quanly API-like routes (server-rendered)
- `GET|POST /quanly/qr-tables/`
- `GET|POST /quanly/qr-tables/<id>/edit/`
- `POST /quanly/qr-tables/<id>/delete/`
- `POST /quanly/qr-tables/<id>/reset-token/`
- `GET /quanly/qr-tables/<id>/png/`
- `GET /quanly/qr-tables/print-pdf/?store=<id>`

## Payment rule
- `cash`: `customer_paid >= total_amount`.
- `card`: neu `customer_paid <= 0` backend set bang `total_amount`.
