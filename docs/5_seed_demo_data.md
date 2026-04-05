# 5) Seed dữ liệu demo

## Hai luồng tạo dữ liệu mẫu
- Luồng 1: `seed_initial_data` (full demo, idempotent, có thể chạy nhiều lần).
- Luồng 2: tạo tenant mới trong Django Admin/Jazzmin bằng superadmin (auto bootstrap bộ cơ bản, dùng cho tenant mới).

## Lệnh seed chuẩn
```bash
python manage.py seed_initial_data --tenant-slug demo --tenant-name "Demo FNB" --reset-passwords --default-password 123456 --seed-qr-pending
```

## Tùy chọn hỗ trợ
- `--tenant-slug` (default: `demo`)
- `--tenant-name` (default: `Demo FNB`)
- `--default-password` (default: `123456`)
- `--reset-passwords`
- `--seed-qr-pending` / `--no-seed-qr-pending`
- `--skip-qr-pending` (alias cũ)

## Dữ liệu được tạo
- 1 tenant demo.
- 3 store: CN Trung Tâm (default), CN Thủ Đức, CN Gò Vấp.
- 1 manager + 4 staff (có mapping store access).
- 8 category.
- 10 product ảnh thật (Unsplash), có unit/size.
- Topping tenant-level + mapping giá theo product.
- 12 dining table mỗi store (có `code` + `qr_token`).
- QROrder pending mẫu nếu bật `--seed-qr-pending`.

## Tính chất idempotent
- Chạy nhiều lần an toàn.
- Bản ghi tồn tại được update, không tạo trùng.
- Dữ liệu ngoài bộ curated có thể bị set `is_active=False`.

## Auto bootstrap khi tạo tenant trong Admin/Jazzmin
- Trigger: superadmin tạo mới `Tenant` trong admin.
- Dữ liệu được tạo tự động:
  - 1 manager + 2 staff (password mặc định `123456`)
  - 1 store mặc định
  - 12 bàn (`BAN-01` → `BAN-12`) có `qr_token`
  - 2 category (`Đồ ăn`, `Nước uống`)
  - 4 product có 1 unit mặc định/món
- Username theo `public_slug` tenant:
  - `<slug>_quanly`
  - `<slug>_nhanvien_1`
  - `<slug>_nhanvien_2`
- Luồng này không thay thế `seed_initial_data` nếu cần dữ liệu demo đầy đủ (3 store, topping, QR pending,…).

## Tài khoản demo
- Manager: `demo_quanly / 123456`
- Staff: `demo_nhanvien_1 / 123456`
- Staff: `demo_nhanvien_2 / 123456`
- Staff: `demo_nhanvien_3 / 123456`
- Staff: `demo_nhanvien_4 / 123456`
