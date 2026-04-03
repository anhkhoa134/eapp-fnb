# 1) Tong quan project eApp FnB

## Muc tieu
- Xay dung he thong POS multi-tenant theo path-based tenancy.
- Nhan vien thao tac ban hang tai `/`.
- Quan ly thao tac CRUD + dashboard tai `/quanly/`.
- Khach xem catalog public tai `/<public_slug>/`.
- Khach dat mon QR full flow tai `/<public_slug>/qr/?table_code=...&token=...`.

## Cong nghe
- Python 3.10
- Django 5.0
- Django Channels (ASGI/WebSocket)
- Bootstrap 5.3
- SQLite mac dinh, co cau hinh PostgreSQL qua env.
- Redis cho realtime WebSocket channel layer.

## Kien truc app
- `App_Core`: tien ich dung chung, context processor, seed command.
- `App_Accounts`: custom user, login/logout, password change.
- `App_Tenant`: tenant, store, user-store access.
- `App_Catalog`: category, product, unit, topping, mapping theo store.
- `App_Sales`: POS APIs, table cart, QR approve/reject, checkout.
- `App_Quanly`: dashboard, order history, CRUD, quan ly QR ban + in QR.
- `App_Public`: public catalog, public QR ordering UI + public QR APIs.

## Trang thai hien tai
- Da co: POS takeaway/table, topping full-stack, QR flow staff, QR flow khach (create/edit/cancel/status), quan ly QR ban (PNG/PDF 15 ban/trang).
- QR realtime da dung WebSocket cho POS + Public QR, co fallback polling 15s khi WS mat ket noi.
- Superadmin tao tenant trong Django Admin/Jazzmin se tu bootstrap du lieu mac dinh:
  1 quan ly, 2 nhan vien, 1 store, 12 ban co QR token, 2 category, 4 product co unit.
- Chua lam: inventory, shift, refund.

## Danh sach tai lieu theo thu tu
1. `docs/1_project_overview.md`
2. `docs/2_setup_and_run.md`
3. `docs/3_architecture_and_data_model.md`
4. `docs/4_routes_permissions_api.md`
5. `docs/5_seed_demo_data.md`
6. `docs/6_testing_and_smoke.md`
7. `docs/7_qr_public_and_qr_admin.md`
8. `docs/8_websocket_realtime.md`
