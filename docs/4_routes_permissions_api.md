# 4) Route, permission, API contracts

## Web routes
- `GET /` -> trang POS staff/manager (login required).
- `GET /orders/today/` -> don hang trong ngay (login required).
- `GET /quanly/*` -> khu quan ly (manager only).
- `GET /accounts/login/` -> login.
- `POST /accounts/logout/` -> logout.
- `GET /<public_slug>/` -> public catalog.

## Luu y bao mat
- `GET /accounts/logout/` bi chan (`405 Method Not Allowed`).
- QR public endpoint bat buoc `table_code + token` hop le.
- API POS chi thao tac tren store user duoc cap quyen.

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
- `GET qr/orders/?store_id=&status=pending|approved|rejected`
- `POST qr/orders/<order_id>/approve/`
- `POST qr/orders/<order_id>/reject/`

## Public API (`/api/public/`)
- `POST qr/orders/`
  - Payload chinh:
    - `table_code`
    - `token`
    - `note`
    - `items[]` gom `product_id`, `unit_id`, `quantity`, `note`, `topping_ids[]`

## Quanly URLs
- Canonical topping URL: `/quanly/toppings/`
- Legacy URL `/quanly/product-toppings/` redirect ve `/quanly/toppings/`

## Payment method
- `cash`: can validate tien khach dua >= tong don.
- `card`: neu `customer_paid <= 0` backend auto gan bang `total_amount`.
