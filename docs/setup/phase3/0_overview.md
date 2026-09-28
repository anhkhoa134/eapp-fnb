# Phase 3 — Vận hành nâng cao

**Thời gian:** 04/2026 – 09/2026 · **Trạng thái:** ✅ Hoàn thành · Roadmap: `docs/setup/4_project_roadmap.md`

## Mục tiêu
Hỗ trợ quán có bếp riêng, chương trình khách hàng thân thiết, và bán phần mềm theo gói (giới hạn + bật/tắt tính năng).

## Phạm vi
| Hạng mục | Cờ tenant | Tài liệu |
|---|---|---|
| Khách hàng, tích điểm, hạng thành viên | `show_customer_feature` | Mục bên dưới |
| Khuyến mãi giảm hoá đơn | `show_promotion_feature` | Mục bên dưới |
| Màn hình bếp `/kitchen/` | `show_kitchen_feature` | `1_kitchen_display.md` |
| Trang Cấu hình tính năng, giới hạn gói | — | `2_feature_settings_and_plan_limits.md` |

## Khách hàng & tích điểm
- Model `Customer` (theo tenant, unique `tenant + phone`): `points_balance`, `total_spent`, `tier`, `last_order_at`.
- Điểm: **1 điểm / 10.000đ** (`LOYALTY_POINT_STEP` trong `App_Sales/services.py`).
- Hạng tính theo `total_spent`, ngưỡng và % giảm cấu hình được qua `CustomerTierSetting` (mặc định):

| Hạng | Tổng chi tiêu tối thiểu | Giảm giá |
|---|---|---|
| Member | 0 | 0% |
| Silver | 5.000.000đ | 3% |
| Gold | 20.000.000đ | 5% |
| VIP | 50.000.000đ | 10% |

- Quản lý tại `/quanly/customers/`; POS chọn khách khi thanh toán.

## Khuyến mãi
- Model `Promotion`: `discount_type` = `percent` | `fixed`, `discount_value`, `min_order_amount`, `max_discount_amount` (trần), `valid_from` / `valid_to`, áp dụng cho nhiều store.
- Quản lý tại `/quanly/promotions/`; POS chỉ hiện khuyến mãi hợp lệ với store + tổng tiền.

## Quy tắc giảm giá khi checkout
- **Không cộng dồn:** hệ thống lấy mức giảm **lớn hơn** giữa ưu đãi hạng và khuyến mãi (`calculate_order_totals`).
- Ghi lại trên `Order`: `discount_amount`, `discount_source` (`none` / `promotion` / `tier`), snapshot hạng và % giảm.
- Thuế tính trên số tiền sau giảm, theo mức `Tenant.tax_percent` cấu hình ở *Cấu hình tính năng* (server tính, làm tròn tới đồng; POS không tự gửi mức thuế). Chi tiết: `2_feature_settings_and_plan_limits.md` mục *Thuế*.
- Tính năng Khách hàng / Khuyến mãi tắt (hoặc ngoài gói): server từ chối `customer_id` / `promotion_id` khi checkout và chặn trang quản lý / API tương ứng (403).

## Tiêu chí hoàn thành
- [x] `App_Sales.tests_kitchen` và test khách hàng / khuyến mãi pass.
- [ ] Kịch bản QA màn hình bếp + khách hàng / khuyến mãi (chưa có trong `phase1/testing/`).
