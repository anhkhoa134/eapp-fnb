# 5) Seed du lieu demo

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

## Tai khoan demo
- Manager: `demo_quanly / 123456`
- Staff: `demo_nhanvien_1 / 123456`
- Staff: `demo_nhanvien_2 / 123456`
- Staff: `demo_nhanvien_3 / 123456`
- Staff: `demo_nhanvien_4 / 123456`
