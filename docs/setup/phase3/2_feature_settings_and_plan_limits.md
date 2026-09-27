# 2) Cấu hình tính năng & giới hạn gói

## Cờ tính năng (`Tenant.show_*_feature`)
Manager bật/tắt tại `GET|POST /quanly/settings/features/` (form `TenantFeatureSettingsForm`). Superadmin cũng sửa được trong Django Admin.

| Field | Mặc định | Khi tắt |
|---|---|---|
| `show_store_feature` | Tắt | Ẩn mục Cửa hàng, `/quanly/stores/` trả 403; chỉ tắt được khi còn tối đa 1 cửa hàng đang hoạt động |
| `show_customer_feature` | Bật | Ẩn mục Khách hàng, POS không cho chọn khách khi thanh toán |
| `show_promotion_feature` | Bật | Ẩn mục Khuyến mãi và phần chọn khuyến mãi ở POS |
| `show_topping_feature` | Bật | Ẩn Topping trong Quản lý và POS |
| `show_qr_order_feature` | Bật | Ẩn QR bàn / gọi món QR |
| `show_kitchen_feature` | Tắt | `/kitchen/` trả 403, ẩn nút Báo bếp, không in được phiếu bếp |
| `show_shift_feature` | Tắt | `/shifts/`, báo cáo ca, API `shifts/current/` trả 403; ẩn mục Ca làm việc (sidebar, POS, Đơn trong ngày). Ca đang mở được giữ nguyên |

Khi thêm tính năng tuỳ chọn mới: thêm field `show_<x>_feature` vào `Tenant`, thêm vào `TenantFeatureSettingsForm.FEATURE_META`, kiểm tra cờ trong view/API (403 khi tắt), ẩn menu trong `templates/App_Quanly/_sidebar_nav.html` (mục của tính năng tuỳ chọn đặt trong nhóm con `admin-nav-subgroup` dưới *Cấu hình tính năng*, và thêm cờ vào điều kiện hiện nhóm con). Nếu tính năng bán theo gói: thêm `feature_<x>` vào `SubscriptionPlan` và `SubscriptionPlan.TENANT_FEATURE_FIELDS`.

## Tính năng theo gói cước (`SubscriptionPlan`)
- `SubscriptionPlan.TENANT_FEATURE_FIELDS` nối cờ của gói với cờ tenant: `feature_customer` → `show_customer_feature`, `feature_promotion` → `show_promotion_feature`, `feature_qr_order` → `show_qr_order_feature`, `feature_kitchen` → `show_kitchen_feature`, `feature_shift` → `show_shift_feature`.
- Gán gói (`Tenant.apply_subscription_plan`, dùng ở Django Admin và khi tự đăng ký) sẽ **tắt** các tính năng gói không có; không tự bật tính năng gói có.
- Trang Cấu hình tính năng khoá công tắc của tính năng ngoài gói (nhãn *Cần nâng cấp gói* → `/quanly/account/#goi-cuoc`); dữ liệu POST cho cờ đó bị bỏ qua.

| Tính năng | Miễn phí | Cơ bản | Chuyên nghiệp | Doanh nghiệp |
|---|---|---|---|---|
| Khách hàng, Khuyến mãi, QR bàn | — | ✓ | ✓ | ✓ |
| Màn hình bếp | — | — | ✓ | ✓ |
| Ca làm việc | — | ✓ | ✓ | ✓ |

## Giới hạn gói (do superadmin đặt trong Django Admin)
| Field | Mặc định gói mới | Ý nghĩa |
|---|---|---|
| `max_stores` | 1 | Số cửa hàng tối đa |
| `max_dining_tables` | 12 | Tổng số bàn (QR/POS) |
| `max_staff_users` | 2 | Số tài khoản nhân viên (không tính quản lý) |
| `subscription_starts_on` | Ngày tạo | Ngày bắt đầu gói |
| `subscription_ends_on` | +365 ngày | Ngày kết thúc gói (phải ≥ ngày bắt đầu) |

- Giá trị `0` = không giới hạn.
- Khi vượt giới hạn, trang tạo mới báo: *"Đã đạt giới hạn … Liên hệ quản trị viên nếu cần nâng gói."*
- Manager xem mức sử dụng / giới hạn và thời hạn gói tại `/quanly/account/`.
