# 5) Seed du lieu demo

## Hai luong tao du lieu mau
- Luong 1: `seed_initial_data` (full demo, idempotent, co the chay nhieu lan).
- Luong 2: tao tenant moi trong Django Admin/Jazzmin bang superadmin (auto bootstrap bo co ban, dung cho tenant moi).

## Lenh seed chuan
```bash
python manage.py seed_initial_data --tenant-slug demo --tenant-name "Demo FNB" --reset-passwords --default-password 123456 --seed-qr-pending
```

## Option ho tro
- `--tenant-slug` (default: `demo`)
- `--tenant-name` (default: `Demo FNB`)
- `--default-password` (default: `123456`)
- `--reset-passwords`
- `--seed-qr-pending` / `--no-seed-qr-pending`
- `--skip-qr-pending` (alias cu)

## Du lieu duoc tao
- 1 tenant demo.
- 3 store: CN Trung Tam (default), CN Thu Duc, CN Go Vap.
- 1 manager + 4 staff (co mapping store access).
- 8 category.
- 10 product anh that (Unsplash), co unit/size.
- Topping tenant-level + mapping gia theo product.
- 12 dining table moi store (co `code` + `qr_token`).
- QROrder pending mau neu bat `--seed-qr-pending`.

## Tinh chat idempotent
- Chay nhieu lan an toan.
- Ban ghi ton tai duoc update, khong tao trung.
- Du lieu ngoai bo curated co the bi set `is_active=False`.

## Auto bootstrap khi tao tenant trong Admin/Jazzmin
- Trigger: superadmin tao moi `Tenant` trong admin.
- Du lieu duoc tao tu dong:
  - 1 manager + 2 staff (password mac dinh `123456`)
  - 1 store mac dinh
  - 12 ban (`BAN-01` -> `BAN-12`) co `qr_token`
  - 2 category (`Do an`, `Nuoc uong`)
  - 4 product co 1 unit mac dinh/mon
- Username theo `public_slug` tenant:
  - `<slug>_quanly`
  - `<slug>_nhanvien_1`
  - `<slug>_nhanvien_2`
- Luong nay khong thay the `seed_initial_data` neu can du lieu demo day du (3 store, topping, QR pending,...).

## Tai khoan demo
- Manager: `demo_quanly / 123456`
- Staff: `demo_nhanvien_1 / 123456`
- Staff: `demo_nhanvien_2 / 123456`
- Staff: `demo_nhanvien_3 / 123456`
- Staff: `demo_nhanvien_4 / 123456`
