# 1) Danh sách tính năng — eApp FnB

## Mục tiêu sản phẩm
Hệ thống POS **multi-tenant** cho F&B (quán cà phê, nhà hàng nhỏ), tenancy theo path (`Tenant.public_slug`).

| Không gian | URL | Người dùng |
|---|---|---|
| POS bán hàng | `/` | Nhân viên, quản lý |
| Đơn trong ngày | `/orders/today/` | Nhân viên, quản lý |
| Màn hình bếp | `/kitchen/` | Nhân viên, quản lý (khi bật tính năng) |
| Ca làm việc | `/shifts/` | Nhân viên, quản lý (khi bật tính năng) |
| Trang in (hoá đơn, tạm tính, phiếu bếp, báo cáo ca) | `/orders/<id>/receipt/`, `/tables/<id>/bill/`, `/kitchen/tickets/<id>/print/`, `/shifts/<id>/print/` | Nhân viên, quản lý |
| Quản lý tenant | `/quanly/` | Quản lý (manager) |
| Menu online (xem menu, đặt mang đi) | `/<public_slug>/` | Khách |
| Gọi món QR | `/<public_slug>/qr/?table_code=&token=` | Khách tại bàn |
| Django Admin / Jazzmin | `/<REAL_ADMIN_PATH>/` | Superadmin |

Chú thích trạng thái: ✅ đã có · 🚧 đang làm · 📋 kế hoạch. Cột **Cờ tenant** là field `Tenant.show_*_feature` bật/tắt tính năng theo từng doanh nghiệp.

## 1. Nền tảng & tài khoản — Phase 1
| Tính năng | Trạng thái | Cờ tenant | Tài liệu |
|---|---|---|---|
| Multi-tenant theo path, chặn reserved slug | ✅ | — | `phase1/2_architecture_and_data_model.md` |
| Custom user, vai trò `MANAGER` / `STAFF`, tối đa 1 manager/tenant | ✅ | — | `phase1/2_architecture_and_data_model.md` |
| Quyền theo cửa hàng (`UserStoreAccess`), store mặc định | ✅ | — | `phase1/3_routes_permissions_api.md` |
| Login / logout (POST) / đổi mật khẩu | ✅ | — | `phase1/3_routes_permissions_api.md` |
| Trang Tài khoản `/quanly/account/` (manager + staff): cập nhật họ tên, email, đổi mật khẩu; manager sửa thêm tên doanh nghiệp | ✅ | — | `phase1/3_routes_permissions_api.md` |
| Superadmin tạo tenant → auto bootstrap dữ liệu tối thiểu | ✅ | — | `phase1/4_seed_demo_data.md` |
| Seed demo idempotent (`seed_initial_data`), phục hồi demo từ admin | ✅ | — | `phase1/4_seed_demo_data.md` |
| Tự đăng ký `/accounts/signup/` → tạo doanh nghiệp gói *Miễn phí* (1 cửa hàng, 1 quản lý, vài bàn); Quên mật khẩu qua email | ✅ | — | `phase3/2_feature_settings_and_plan_limits.md` |
| Gói cước (`SubscriptionPlan`), giới hạn cửa hàng / bàn / nhân viên / món, bảng gói ở trang Tài khoản | ✅ | — | `phase3/2_feature_settings_and_plan_limits.md` |
| Chặn doanh nghiệp ngừng hoạt động / hết hạn gói (POS, API, `/quanly/`, WebSocket; cảnh báo trước 7 ngày) | ✅ | — | `docs/backlog/1_backlog.md` BL-001 |
| Chống brute-force đăng nhập, giới hạn tần suất đăng ký / quên mật khẩu / đặt mang đi | ✅ | — | `5_security_policy.md` |

## 2. POS bán hàng — Phase 1
| Tính năng | Trạng thái | Cờ tenant | Tài liệu |
|---|---|---|---|
| Bán mang về + bán tại bàn (table cart lưu server) | ✅ | — | `phase1/3_routes_permissions_api.md` |
| Chọn size/unit, ghi chú, số lượng | ✅ | — | — |
| Topping theo sản phẩm (giá topping theo product) | ✅ | `show_topping_feature` | — |
| Import giỏ mang về lên bàn, đổi sang mang về, chuyển bàn | ✅ | — | `phase1/3_routes_permissions_api.md` |
| Thanh toán tiền mặt / thẻ, QR thanh toán theo cửa hàng | ✅ | — | `phase1/3_routes_permissions_api.md` |
| Thuế theo mức cấu hình của doanh nghiệp (server tính, POS hiện dòng thuế, in trên hoá đơn / tạm tính) | ✅ | `Tenant.tax_percent` | `phase3/2_feature_settings_and_plan_limits.md` |
| Chống tạo đơn trùng khi bấm đúp / mạng chập chờn (`client_request_id`, khoá bàn khi thanh toán) | ✅ | — | `phase1/3_routes_permissions_api.md` |
| `Order.sale_channel` (tại quán / mang về) | ✅ | — | — |
| Đơn trong ngày (KPI + bảng phân trang) | ✅ | — | — |
| Giao diện mobile (offcanvas giỏ hàng) | ✅ | — | `phase1/testing/trang_ban_hang.md` |

## 3. Quản lý (`/quanly/`) — Phase 1
| Tính năng | Trạng thái | Cờ tenant | Tài liệu |
|---|---|---|---|
| Dashboard doanh thu (lọc store + khoảng thời gian, ECharts) | ✅ | — | `phase1/3_routes_permissions_api.md` |
| Lịch sử đơn, xoá đơn (ghi nhật ký), in lại hoá đơn, hoàn tiền | ✅ | — | `phase4/2_shifts_and_refunds.md` |
| CRUD danh mục / sản phẩm / unit, import Excel | ✅ | — | — |
| CRUD topping + gán topping theo sản phẩm | ✅ | `show_topping_feature` | — |
| CRUD cửa hàng (nhiều chi nhánh) | ✅ | `show_store_feature` (mặc định tắt) | — |
| Quản lý nhân viên, reset mật khẩu nhân viên | ✅ | — | — |
| Phân trang server-rendered 20 dòng/trang | ✅ | — | `phase1/3_routes_permissions_api.md` |

## 4. Gọi món QR, realtime, PWA — Phase 2
| Tính năng | Trạng thái | Cờ tenant | Tài liệu |
|---|---|---|---|
| Khách gọi món QR: tạo / sửa / huỷ đơn pending | ✅ | `show_qr_order_feature` | `phase2/1_qr_public_and_qr_admin.md` |
| Nhân viên duyệt / từ chối đơn QR (có lý do từ chối) | ✅ | `show_qr_order_feature` | `phase2/1_qr_public_and_qr_admin.md` |
| Menu online: khách đặt món mang đi (tên + SĐT), theo dõi trạng thái đơn | ✅ | `show_qr_order_feature` | `phase2/4_online_takeaway_ordering.md` |
| POS: duyệt đơn mang đi → báo bếp; mục *Mang đi · chờ khách tới lấy*, nút **Thu tiền** | ✅ | `show_qr_order_feature` | `phase2/4_online_takeaway_ordering.md` |
| Giao diện gọi món khách làm lại (dùng chung QR + mang đi, hiệu ứng theo POS) | ✅ | — | `phase2/4_online_takeaway_ordering.md` |
| Quản lý bàn QR: CRUD, reset token, PNG, in PDF A3 15 bàn/trang | ✅ | `show_qr_order_feature` | `phase2/1_qr_public_and_qr_admin.md` |
| Realtime WebSocket (POS + khách), fallback polling 15s | ✅ | — | `phase2/2_websocket_realtime.md` |
| PWA: manifest, service worker, trang offline | ✅ | — | `phase2/3_pwa.md` |

## 5. Vận hành nâng cao — Phase 3
| Tính năng | Trạng thái | Cờ tenant | Tài liệu |
|---|---|---|---|
| Khách hàng, tích điểm, hạng thành viên (Member/Silver/Gold/VIP) | ✅ | `show_customer_feature` | `phase3/0_overview.md` |
| Khuyến mãi giảm hoá đơn (% / số tiền, trần giảm) | ✅ | `show_promotion_feature` | `phase3/0_overview.md` |
| Màn hình bếp: báo bếp, phiếu bếp, trạng thái món (thanh công cụ làm lại 27/09/2026) | ✅ | `show_kitchen_feature` (mặc định tắt) | `phase3/1_kitchen_display.md` |
| Trang Cấu hình tính năng (công tắc tính năng, chặn ở server) + mức thuế + giới hạn gói (store/bàn/nhân viên/món) | ✅ | — | `phase3/2_feature_settings_and_plan_limits.md` |

## 6. Vận hành hằng ngày — Phase 4
| Tính năng | Trạng thái | Cờ tenant | Tài liệu |
|---|---|---|---|
| In hoá đơn, phiếu tạm tính, phiếu bếp, báo cáo ca (khổ 80/58mm, tự in, đánh dấu in lại) | ✅ | — | `phase4/1_printing.md` |
| In thẳng máy in nhiệt (ESC/POS) | 📋 | — | `phase4/0_overview.md` |
| Ca làm việc: mở ca, chốt ca, đối soát tiền mặt, báo cáo ca | ✅ | `show_shift_feature` (mặc định tắt, gói *Cơ bản* trở lên) | `phase4/2_shifts_and_refunds.md` |
| Hoàn tiền toàn bộ / một phần (manager), doanh thu thuần | ✅ | — | `phase4/2_shifts_and_refunds.md` |
| Nhật ký thao tác `/quanly/audit-log/` | ✅ | — | `phase4/3_audit_log.md` |
| Hộp thoại dùng chung thay `alert` / `confirm` | ✅ | — | `phase4/4_shared_dialog.md` |
| Định mức nguyên liệu, thành phẩm: giá vốn, lãi gộp từng món, tiêu hao theo đơn bán | ✅ | `show_recipe_feature` (mặc định tắt, gói *Chuyên nghiệp* trở lên) | `phase4/5_recipes.md` |
| Quản lý tồn kho (inventory) | 📋 | — | `phase4/0_overview.md` |

## Mục lục tài liệu
```
docs/setup/
├── 1_features.md                 ← file này
├── 2_tech_stack.md
├── 3_file_structure.md
├── 4_project_roadmap.md
├── 5_security_policy.md
├── 6_production_env.md
├── phase1/                       Nền tảng POS + Quản lý
├── phase2/                       Gọi món QR + Menu online mang đi + Realtime + PWA
├── phase3/                       Vận hành nâng cao
└── phase4/                       Vận hành hằng ngày (đang làm)
```
Cây đầy đủ: `docs/setup/3_file_structure.md`.
