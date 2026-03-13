# 5) Seed du lieu demo

## Lenh seed chuan
```bash
python manage.py seed_initial_data --tenant-slug demo --tenant-name "Demo FNB" --reset-passwords --default-password 123456 --seed-qr-pending
```

## Option ho tro
- `--tenant-slug`: mac dinh `demo`.
- `--tenant-name`: mac dinh `Demo FNB`.
- `--default-password`: mat khau mac dinh cho tai khoan seed.
- `--reset-passwords`: reset lai password tai khoan da ton tai.
- `--seed-qr-pending` / `--no-seed-qr-pending`: bat/tat seed don QR pending.
- `--skip-qr-pending`: alias cu, tuong duong tat seed QR pending.

## Du lieu duoc tao (compact-plus)
- 1 tenant demo.
- 3 cua hang:
  - CN Trung Tam (default)
  - CN Thu Duc
  - CN Go Vap
- User:
  - 1 manager: `demo_quanly`
  - 4 staff: `demo_nhanvien_1..4`
- 8 danh muc.
- 10 san pham mau co anh that (Unsplash), co unit gia theo size.
- Topping tenant-level + mapping gia theo tung san pham.
- 12 ban moi cua hang (`code` + `qr_token`).
- Don QR pending mau (neu bat option seed QR pending).

## Tinh chat idempotent
- Lenh seed co the chay nhieu lan.
- Du lieu ton tai duoc update thay vi tao trung.
- Mot so ban ghi cu khong nam trong bo curated se duoc dat `is_active=False`.

## Tai khoan demo
- Manager: `demo_quanly / 123456`
- Staff: `demo_nhanvien_1 / 123456`
- Staff: `demo_nhanvien_2 / 123456`
- Staff: `demo_nhanvien_3 / 123456`
- Staff: `demo_nhanvien_4 / 123456`
