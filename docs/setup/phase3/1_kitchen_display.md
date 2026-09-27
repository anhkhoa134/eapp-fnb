# 1) Màn hình bếp (Kitchen Display)

## Bật tính năng
- Cờ `Tenant.show_kitchen_feature` (mặc định **tắt**). Manager bật tại `/quanly/settings/features/`.
- Khi tắt: `GET /kitchen/` trả 403, POS không hiện nút **Báo bếp**.

## Màn hình
- URL: `GET /kitchen/` (staff/manager, login required), template `templates/App_Sales/kitchen.html`.
- Chọn store trong số store user có quyền.
- Hai chế độ: phiếu **đang chờ** (`scope=active`) và phiếu **đã xong hôm nay** (`scope=done`).

### Thanh công cụ (làm lại 27/09/2026, phong cách POS)
| Điều khiển | Mô tả |
|---|---|
| Trạng thái kết nối | Chấm xanh nhấp nháy + *"Đang cập nhật trực tiếp"*; khi mất WebSocket: *"Tự làm mới mỗi 15 giây"* |
| Cửa hàng | Ô chọn dạng pill có icon (chỉ hiện khi user có > 1 store) |
| Đang chờ / Đã xong hôm nay | Cụm nút chọn (segmented); số đếm chuyển đỏ khi còn món |
| Chuông, Tự in phiếu | Nút bật/tắt dạng chip có icon + công tắc nhỏ; lưu ở localStorage (`eapp_kitchen_sound_enabled`, `eapp_kitchen_auto_print`) |
| Toàn màn hình | Nút icon, đổi icon khi đang toàn màn hình |
| Về POS | Nút chính màu mint |

Trên thẻ phiếu:
- Nút theo trạng thái món: **▶ Bắt đầu** (viền cam), **✓ Xong** (mint), **Hoàn tác** (xám).
- Nút **Xong cả phiếu** nền gradient.
- Thời gian chờ ≥ 60 phút hiển thị dạng `1g05'`.

## Model
- `KitchenTicket(tenant, store, table, table_name, source, order, qr_order, created_by, completed_at)`
  - `source`: `TABLE` (tại bàn) · `QR` (gọi món QR) · `TAKEAWAY` (mang về).
- `KitchenTicketItem(ticket, table_cart_item, product, snapshot_product_name, snapshot_unit_name, toppings_text, quantity, note, status, started_at, done_at)`
  - `status`: `PENDING` (chờ làm) → `PREPARING` (đang làm) → `DONE` (đã xong) · `CANCELLED` (đã huỷ).
- `TableCartItem.kitchen_sent_quantity`: số lượng đã báo bếp của mỗi dòng giỏ bàn.

## Khi nào tạo phiếu bếp
| Sự kiện | `source` |
|---|---|
| Bấm **Báo bếp** ở giỏ bàn (chỉ phần số lượng chưa gửi) | `TABLE` |
| Nhân viên duyệt đơn QR tại bàn | `QR` |
| Nhân viên duyệt đơn mang đi đặt từ menu online (`table_name = "Mang đi · <tên khách>"`) | `TAKEAWAY` |
| Thanh toán đơn mang về (không tạo nếu là đơn mang đi online đã báo bếp lúc duyệt — chỉ gắn `order` vào phiếu cũ) | `TAKEAWAY` |
| Thanh toán bàn còn món chưa báo bếp | `TABLE` |

## Đồng bộ khi giỏ bàn thay đổi
Logic trong `App_Sales/kitchen.py`:
- Giảm số lượng / xoá món đã báo → huỷ phần bếp chưa làm xong (`sync_kitchen_on_quantity_decrease`).
- Đổi ghi chú / topping món đã báo → huỷ phần chưa xong để báo bếp lại (`sync_kitchen_on_item_modified`).
- Chuyển bàn → phiếu đang mở chuyển theo bàn mới (`move_open_tickets_to_table`).
- Phiếu tự hoàn tất khi mọi món ở trạng thái đóng (`refresh_ticket_completion`).

## API (`/api/pos/`)
- `POST tables/<table_id>/kitchen/send/` → 201 + `ticket_id`, hoặc 200 + `ticket_id: null` khi không có món mới.
- `GET kitchen/tickets/?store_id=&scope=active|done`
- `POST kitchen/items/<item_id>/status/` — body `{ "status": "PENDING|PREPARING|DONE" }`
- `POST kitchen/tickets/<ticket_id>/complete/` — xong cả phiếu.

## Realtime
- Dùng chung kênh WebSocket POS: `ws://<host>/ws/pos/store/<store_id>/`.
- Event: `{ "type": "kitchen.changed", "store_id", "ticket_id", "reason": "created|status|done|cancelled|moved", "message", "ts" }`.
- Push sau khi transaction commit (`transaction.on_commit`).

## In phiếu bếp
- Nút máy in trên từng phiếu → `GET /kitchen/tickets/<id>/print/`; công tắc **Tự in phiếu** chỉ in phiếu mới chưa in lần nào (`KitchenTicket.print_count = 0`).
- POS có công tắc **Tự in phiếu bếp** (in sau Báo bếp / thanh toán mang về).
- Chi tiết: `docs/setup/phase4/1_printing.md`.

## Test
```bash
python manage.py test App_Sales.tests_kitchen
```
