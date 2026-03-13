# 1) Tong quan project eApp FnB

## Muc tieu
- Xay dung he thong POS multi-tenant theo path-based tenancy.
- Nhan vien thao tac ban hang tai `/`.
- Quan ly thao tac CRUD va dashboard tai `/quanly/`.
- Khach xem menu public theo tenant tai `/<public_slug>/`.

## Cong nghe
- Python 3.10
- Django 5.0
- Bootstrap 5.3
- DB mac dinh SQLite, co san cau hinh PostgreSQL qua env.

## Kien truc app
- `App_Core`: tien ich dung chung, context processor, seed command.
- `App_Accounts`: user custom, login/logout, doi mat khau.
- `App_Tenant`: tenant, store, quyen truy cap store theo user.
- `App_Catalog`: danh muc, san pham, don vi, topping, mapping theo store.
- `App_Sales`: POS API, table cart, QR order, checkout.
- `App_Quanly`: dashboard, lich su don, CRUD category/product/topping/staff.
- `App_Public`: catalog public va API tao QR order cho khach.

## Scope hien tai (v1.1)
- Da co: POS takeaway + table, topping full-stack, QR approve/reject, order history, dashboard.
- Chua lam: inventory, shift, refund.

## Danh sach tai lieu theo thu tu
1. `docs/1_project_overview.md`
2. `docs/2_setup_and_run.md`
3. `docs/3_architecture_and_data_model.md`
4. `docs/4_routes_permissions_api.md`
5. `docs/5_seed_demo_data.md`
6. `docs/6_testing_and_smoke.md`
