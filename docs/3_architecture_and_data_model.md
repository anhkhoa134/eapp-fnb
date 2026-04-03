# 3) Kien truc va data model

## Multi-tenant theo path
- Tenant duoc dinh danh bang `Tenant.public_slug`.
- Public route: `/<public_slug>/`.
- Public QR route: `/<public_slug>/qr/`.
- Reserved slug da chan: `admin`, `accounts`, `api`, `quanly`, `static`, `media`, `favicon.ico`.

## User va phan quyen
- `User.role`: `MANAGER` / `STAFF`.
- Moi tenant toi da 1 manager (`uq_manager_per_tenant`).
- Quyen store theo `UserStoreAccess`.
- Moi user toi da 1 store mac dinh (`uq_default_store_per_user`).

## Catalog
- `Category`, `Product`, `ProductUnit`.
- `Topping` tenant-level.
- `ProductTopping` de dat gia topping theo tung product.
- `StoreCategory` va `StoreProduct` de bat/tat hien thi theo store.

## Sales/QR core models
- `DiningTable(tenant, store, code, qr_token, is_active, display_order)`.
- `QROrder(status=PENDING|APPROVED|REJECTED|CANCELLED, resolved_at, ...)`.
- `QROrderItem` + `QROrderItemTopping` (snapshot).
- `TableCartItem` + `TableCartItemTopping`.
- `Order` + `OrderItem` + `OrderItemTopping`.

## Lifecycle QR
1. Khach goi mon QR (public API) -> `QROrder.PENDING`.
2. Nhan vien duyet -> merge vao table cart, order thanh `APPROVED`.
3. Nhan vien tu choi -> `REJECTED`.
4. Khach huy don pending -> `CANCELLED`.
5. Terminal states: `APPROVED/REJECTED/CANCELLED` (khong cho sua/huy tiep).

## Realtime QR architecture
- ASGI stack: `Django + Channels + Daphne`.
- Channel layer: Redis (`REDIS_URL`).
- WS group:
  - POS theo store: `pos_store_<store_id>`.
  - Public theo order: `public_qr_order_<order_id>`.
- Event mode: WS chi push signal, frontend refetch lai REST API hien co.
- Fallback: khi WS disconnect, frontend polling 15s.

## Quan ly QR ban
- Manager CRUD ban QR trong `/quanly/qr-tables/`.
- Co reset token, tai PNG QR tung ban.
- Co in PDF kho lon theo store (15 ban/trang).
