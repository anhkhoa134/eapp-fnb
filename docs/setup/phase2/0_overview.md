# Phase 2 — Gọi món QR + Realtime + PWA

**Thời gian:** 03/2026 – 04/2026 · **Trạng thái:** ✅ Hoàn thành · Roadmap: `docs/setup/4_project_roadmap.md`

## Mục tiêu
Khách tự gọi món bằng QR tại bàn, nhân viên nhận và duyệt đơn tức thì, người dùng cài app lên màn hình chính.

## Phạm vi
- `DiningTable` có `code` + `qr_token`; `QROrder` với vòng đời `PENDING → APPROVED | REJECTED | CANCELLED`.
- Trang khách `/<public_slug>/qr/`: tạo / sửa / huỷ đơn pending.
- Tab **Đơn QR** trên POS: duyệt (merge vào giỏ bàn) / từ chối (có lý do).
- Quản lý bàn QR: CRUD, reset token, PNG, in PDF A3 15 bàn/trang.
- WebSocket (Channels + Redis) cho POS và khách; fallback polling 15s.
- PWA: manifest, service worker, trang offline, icon iOS/Android.

Cờ tenant: `show_qr_order_feature`.

## Tài liệu trong phase
| File | Nội dung |
|---|---|
| `1_qr_public_and_qr_admin.md` | Luồng gọi món QR của khách + quản lý bàn QR |
| `2_websocket_realtime.md` | Endpoint, event, điều kiện chạy, troubleshooting WS |
| `3_pwa.md` | Manifest, service worker, trang offline, kiểm thử PWA |

Route/API/model của phase này được ghi chung trong `phase1/2_architecture_and_data_model.md` và `phase1/3_routes_permissions_api.md`.

## Tiêu chí hoàn thành
- [x] `App_Sales.tests_ws`, `App_Public.tests_ws` pass.
- [x] Smoke C, D, E trong `phase1/6_smoke_ui_checklist.md` pass (kể cả khi tắt Redis).
