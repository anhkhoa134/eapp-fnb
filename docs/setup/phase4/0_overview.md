# Phase 4 — Vận hành cửa hàng hằng ngày

**Thời gian:** 09/2026 – · **Trạng thái:** 🚧 Đang làm · Roadmap: `docs/setup/4_project_roadmap.md`

## Mục tiêu
Đủ nghiệp vụ vận hành cửa hàng hằng ngày: in phiếu, đối soát tiền cuối ca, xử lý hoàn tiền, truy vết thao tác nhạy cảm.

Danh sách đầy đủ, ưu tiên và checklist nghiệm thu: `docs/backlog/1_backlog.md` (các BL-xxx gắn Phase 4).

## Đã làm (27/09/2026)
| Hạng mục | Backlog | Cờ tenant | Tài liệu |
|---|---|---|---|
| In hoá đơn, phiếu tạm tính, phiếu bếp, báo cáo ca (khổ 80/58mm, in từ trình duyệt, đánh dấu in lại) | BL-009 (bước 1) | — (phiếu bếp theo `show_kitchen_feature`) | `1_printing.md` |
| Ca làm việc: mở ca, chốt ca, đối soát tiền mặt | BL-011 | `show_shift_feature` (mặc định tắt, gói *Cơ bản* trở lên) | `2_shifts_and_refunds.md` |
| Hoàn tiền toàn bộ / một phần, doanh thu thuần | BL-012 | — | `2_shifts_and_refunds.md` |
| Nhật ký thao tác | BL-013 | — | `3_audit_log.md` |
| Hộp thoại dùng chung thay `alert` / `confirm` của trình duyệt | — | — | `4_shared_dialog.md` |
| Định mức nguyên liệu, thành phẩm: giá vốn, lãi gộp, tiêu hao theo đơn bán | BL-018 (bước 1) | `show_recipe_feature` (mặc định tắt, gói *Chuyên nghiệp* trở lên) | `5_recipes.md` |

Model / migration mới: `App_Sales.Shift`, `App_Sales.Refund`, `Order.table_name` / `refunded_amount` / `print_count`, `Order.Status.REFUNDED`, `KitchenTicket.print_count` (`App_Sales/0011_shift_refund_print`); `App_Core.AuditLog` (`App_Core/0001_initial`); `Tenant.show_shift_feature`, `SubscriptionPlan.feature_shift` (`App_Tenant/0016_shift_feature`).

## Còn lại
| Hạng mục | Mô tả sơ bộ | Ghi chú |
|---|---|---|
| In trực tiếp máy in nhiệt (ESC/POS) | Không qua hộp thoại in | BL-009 bước 2 |
| Ca làm việc mở rộng | Thu/chi ngoài bán hàng, gắn cứng `Order` với ca, báo cáo ca trên `/quanly/` | BL-011 |
| Hoàn tiền theo món | Chọn món cần hoàn thay vì nhập số tiền | BL-012 |
| Tồn kho (inventory) | Tồn kho theo cửa hàng, trừ kho khi bán, nhập / kiểm kho | BL-018; định mức đã có (`5_recipes.md`) |
| VietQR động | Sinh QR theo số tiền, tự xác nhận chuyển khoản | BL-010 |
| CI/CD | Pipeline test + deploy tự động | Xem `docs/setup/6_production_env.md` mục 14 |
| Bảo mật | Rate limit API public QR, CSP | Xem `docs/setup/5_security_policy.md` mục 9 |

## Tiêu chí hoàn thành (phần đã làm)
- [x] `App_Sales.tests_ops` pass (in, ca, hoàn tiền, nhật ký).
- [x] Định mức: `App_Quanly.tests_recipes` pass (27 test; quyền gói, validation, giá vốn, tiêu hao, bộ lọc).
- [x] Toàn bộ `python manage.py test` pass (300 test, 27/09/2026).
- [ ] Chạy tay các case PRN / SHF / RFD / AUD trong `docs/testing/1_e2e_test_cases.md` trên máy in nhiệt thật.
