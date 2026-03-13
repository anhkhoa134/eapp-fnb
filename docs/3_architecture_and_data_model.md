# 3) Kien truc va data model

## Multi-tenant theo path
- Tenant duoc dinh danh bang `Tenant.public_slug`.
- Route public: `/<public_slug>/`.
- Reserved slug duoc chan: `admin`, `accounts`, `api`, `quanly`, `static`, `media`, `favicon.ico`.

## User va phan quyen
- `User.role`: `MANAGER` hoac `STAFF`.
- Moi tenant toi da 1 manager (`uq_manager_per_tenant`).
- Staff/manager duoc cap quyen store qua `UserStoreAccess`.
- Moi user co toi da 1 store mac dinh (`uq_default_store_per_user`).

## Store
- `Store` thuoc `Tenant`.
- Moi tenant co toi da 1 store mac dinh (`uq_default_store_per_tenant`).
- Slug store auto-generate unique trong tenant.

## Catalog
- `Category(tenant, ...)`
- `Product(tenant, category, image_url, is_active, ...)`
- `ProductUnit(product, name, price, is_active, display_order)`
- `Topping(tenant, name, slug, is_active, display_order)`
- `ProductTopping(product, topping, price, is_active, display_order)`
  - unique `(product, topping)`
- Mapping hien thi theo store:
  - `StoreCategory(store, category, is_visible)`
  - `StoreProduct(store, product, is_available, custom_price)`

## Sales va snapshot
- `DiningTable(tenant, store, code, qr_token, is_active)`
- `QROrder` + `QROrderItem` + `QROrderItemTopping`
- `TableCartItem` + `TableCartItemTopping`
- `Order` + `OrderItem` + `OrderItemTopping`

Snapshot duoc luu tai thoi diem thao tac:
- Ten mon, don vi, gia, topping, so luong.
- Dam bao lich su don khong bi anh huong khi catalog thay doi sau nay.

## Lifecycle chinh
1. Khach tao don QR pending theo `table_code + token`.
2. Nhan vien duyet QR -> merge vao table cart.
3. Table checkout -> tao `Order/OrderItem/OrderItemTopping`.
4. Cart cua ban duoc xoa sau khi thanh toan thanh cong.
