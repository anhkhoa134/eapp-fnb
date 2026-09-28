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
| `show_recipe_feature` | Tắt | `/quanly/ingredients/…`, `/quanly/recipes/…` trả 403; ẩn mục Định mức NVL (`phase4/5_recipes.md`) |

**Chặn ở server, không chỉ ẩn menu** (từ 28/09/2026). Khách hàng / Khuyến mãi dùng `Tenant.customer_feature_enabled` / `promotion_feature_enabled` = cờ bật **và** gói cho phép (`Tenant.feature_enabled(field)`):
- Khách hàng tắt: `/quanly/customers/…` trả 403, `GET|POST /api/pos/customers/` trả 403, checkout gửi `customer_id` trả 400 *Tính năng khách hàng đang tắt.*
- Khuyến mãi tắt: `/quanly/promotions/…` trả 403, `GET /api/pos/promotions/` trả 403, checkout gửi `promotion_id` trả 400.
- QR bàn / đặt mang đi: xem `Tenant.is_ordering_open()` (bật cờ QR + doanh nghiệp hoạt động + gói còn hạn).

Khi thêm tính năng tuỳ chọn mới: thêm field `show_<x>_feature` vào `Tenant`, thêm vào `TenantFeatureSettingsForm.FEATURE_META`, kiểm tra cờ **ở server** trong mọi view/API (403 khi tắt; tính năng bán theo gói dùng `tenant.feature_enabled('show_<x>_feature')`, trang Quản lý có decorator mẫu `_feature_required` trong `App_Quanly/views.py`), ẩn menu trong `templates/App_Quanly/_sidebar_nav.html` (mục của tính năng tuỳ chọn đặt trong nhóm con `admin-nav-subgroup` dưới *Cấu hình tính năng*, và thêm cờ vào điều kiện hiện nhóm con). Nếu tính năng bán theo gói: thêm `feature_<x>` vào `SubscriptionPlan` và `SubscriptionPlan.TENANT_FEATURE_FIELDS`.

## Tính năng theo gói cước (`SubscriptionPlan`)
- `SubscriptionPlan.TENANT_FEATURE_FIELDS` nối cờ của gói với cờ tenant: `feature_customer` → `show_customer_feature`, `feature_promotion` → `show_promotion_feature`, `feature_qr_order` → `show_qr_order_feature`, `feature_kitchen` → `show_kitchen_feature`, `feature_shift` → `show_shift_feature`, `feature_recipe` → `show_recipe_feature`.
- Gán gói (`Tenant.apply_subscription_plan`, dùng ở Django Admin và khi tự đăng ký) sẽ **tắt** các tính năng gói không có; không tự bật tính năng gói có.
- Trang Cấu hình tính năng khoá công tắc của tính năng ngoài gói (nhãn *Cần nâng cấp gói* → `/quanly/account/#goi-cuoc`); dữ liệu POST cho cờ đó bị bỏ qua.

Gói mẫu (seed ở migration `App_Tenant/0015`, `0016`, `0017`; superadmin sửa được trong admin):

| Tính năng / giới hạn | Miễn phí (mặc định khi tự đăng ký) | Cơ bản | Chuyên nghiệp | Doanh nghiệp |
|---|---|---|---|---|
| Khách hàng, Khuyến mãi, QR bàn | — | ✓ | ✓ | ✓ |
| Màn hình bếp | — | — | ✓ | ✓ |
| Ca làm việc | — | ✓ | ✓ | ✓ |
| Định mức nguyên liệu | — | — | ✓ | ✓ |
| Cửa hàng / nhân viên / bàn / món | 1 / 0 / 5 / 20 | 1 / 5 / 20 / 100 | 3 / 20 / 60 / 500 | không giới hạn |
| Thời hạn | Không hết hạn | 1 năm | 1 năm | 1 năm |

## Giới hạn gói (do superadmin đặt trong Django Admin)
| Field | Mặc định tenant mới (không gán gói) | Ý nghĩa |
|---|---|---|
| `max_stores` | 1 | Số cửa hàng tối đa |
| `max_dining_tables` | 12 | Tổng số bàn (QR/POS) |
| `max_staff_users` | 2 | Số tài khoản nhân viên (không tính quản lý) |
| `max_products` | Không giới hạn | Số món (sản phẩm), kể cả món tạo qua nhập Excel |
| `subscription_starts_on` | Ngày tạo | Ngày bắt đầu gói |
| `subscription_ends_on` | +365 ngày (gói miễn phí: để trống = không hết hạn) | Ngày kết thúc gói (phải ≥ ngày bắt đầu) |

- **Để trống** = không giới hạn. **`0` = không cho tạo** (ví dụ gói Miễn phí `max_staff_users = 0`: chỉ có 1 tài khoản quản lý). Migration `App_Tenant/0015` đã đổi quy ước cũ "0 = không giới hạn" sang để trống.
- Gán gói cho tenant sẽ chép các giới hạn của gói sang tenant.
- Khi vượt giới hạn, trang tạo mới báo: *"Đã đạt giới hạn … Liên hệ quản trị viên nếu cần nâng gói."*
- Manager xem mức sử dụng / giới hạn và thời hạn gói tại `/quanly/account/`.

## Thuế (cùng trang Cấu hình tính năng)
- Field `Tenant.tax_percent` (0–30%, mặc định 0, migration `App_Tenant/0018_tax_percent`). Thẻ **Thuế** ở cuối trang `/quanly/settings/features/`, lưu riêng bằng `POST form_action=tax` (form `TenantTaxSettingsForm`), không đụng tới các công tắc tính năng. Thay đổi được ghi nhật ký thao tác (Doanh nghiệp: *Thuế (%)*).
- Cách tính (`calculate_order_totals`): `thuế = làm tròn tới đồng (tiền sau giảm giá × tax_percent / 100)`, `tổng = tiền sau giảm giá + thuế`. Server luôn dùng mức của tenant, **bỏ qua** `tax_rate` client gửi lên; `Order.tax_rate` lưu mức thuế lúc bán (0.08 = 8%).
- POS hiện dòng *Thuế (x%)* trong modal thanh toán khi mức > 0 (cùng công thức để tổng tiền khớp server). Hoá đơn in *Thuế (x%)*; phiếu tạm tính in tiền món + thuế + tạm tính.
- Nhập 0 nếu giá bán đã gồm thuế hoặc quán không tính thuế riêng.
