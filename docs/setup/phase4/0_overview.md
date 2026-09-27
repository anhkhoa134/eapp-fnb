# Phase 4 — Kế hoạch (chưa làm)

**Trạng thái:** 📋 Chưa lên lịch · Roadmap: `docs/setup/4_project_roadmap.md`

## Mục tiêu
Đủ nghiệp vụ vận hành cửa hàng hằng ngày.

Danh sách đầy đủ, ưu tiên và checklist nghiệm thu: `docs/backlog/1_backlog.md` (các BL-xxx gắn Phase 4).

## Hạng mục ứng viên
| Hạng mục | Mô tả sơ bộ | Ghi chú |
|---|---|---|
| Tồn kho (inventory) | Nguyên liệu / thành phẩm, trừ kho khi bán, nhập kho | Cần định mức nguyên liệu theo `ProductUnit` |
| Ca làm việc (shift) | Mở / chốt ca, tiền đầu ca, bàn giao | Gắn `Order` với ca |
| Hoàn tiền (refund) | Huỷ / hoàn đơn đã thanh toán, lý do, người duyệt | Ảnh hưởng doanh thu dashboard, điểm khách hàng |
| CI/CD | Pipeline test + deploy tự động | Xem `docs/setup/6_production_env.md` mục 13 |
| Bảo mật | Chống brute-force, rate limit API public | Xem `docs/setup/5_security_policy.md` mục 9 |

## Khi bắt đầu phase
1. Chốt phạm vi + tiêu chí hoàn thành vào file này.
2. Thêm tài liệu chi tiết `1_<chu_de>.md`, `2_<chu_de>.md`, … vào `phase4/`.
3. Cập nhật `1_features.md`, `4_project_roadmap.md`, `3_file_structure.md`.
