# 3) Nhật ký thao tác (audit log)

Backlog: BL-013.

## Xem nhật ký
- `GET /quanly/audit-log/` — **manager**, sidebar *Nhật ký thao tác*. Chỉ xem, không sửa / xoá được.
- Lọc: thao tác (từng loại hoặc cả nhóm `group:<n>`), người thao tác, cửa hàng, khoảng ngày, tìm theo nội dung. 30 dòng/trang.
- Thao tác nhạy cảm (hoàn tiền, xoá đơn, in lại hoá đơn, huỷ món, đăng nhập sai, xoá dữ liệu) có nhãn màu cam.
- Superadmin xem mọi tenant trong Django Admin → *Nhật ký thao tác* (không thêm / sửa được).

## Model `App_Core.AuditLog`
`AuditLog(tenant, store, user, username, action, object_type, object_id, object_repr, message, extra (JSON), ip_address, created_at)`
- `username` lưu bản sao để vẫn đọc được khi tài khoản bị xoá.
- `extra.changes`: danh sách `{field, old, new}` cho thao tác sửa dữ liệu.

## Loại thao tác
| Nhóm | `action` | Ghi khi |
|---|---|---|
| Bán hàng | `order.refund` | Hoàn tiền (số tiền, hình thức, lý do) |
| | `order.delete` | Manager xoá đơn (lưu mã, tổng tiền, hình thức thanh toán trước khi xoá) |
| | `order.reprint` | In hoá đơn từ lần thứ 2 |
| | `cart.void` | Xoá / giảm số lượng món trong giỏ bàn (ghi rõ *đã báo bếp* nếu có) |
| | `table.move` | Chuyển giỏ sang bàn khác |
| | `qr.reject` | Từ chối đơn QR (kèm lý do) |
| | `kitchen.reprint` | In phiếu bếp từ lần thứ 2 |
| Ca làm việc | `shift.open`, `shift.close` | Mở ca (tiền đầu ca), chốt ca (dự kiến, thực đếm, chênh lệch) |
| Dữ liệu & cấu hình | `object.create`, `object.update`, `object.delete` | Thay đổi dữ liệu danh mục (bảng dưới) |
| | `catalog.import` | Nhập Excel danh mục |
| Đăng nhập | `auth.login`, `auth.logout`, `auth.login_failed` | Đăng nhập / đăng xuất / sai mật khẩu (chỉ ghi khi username thuộc một tenant) |

## Ghi tự động thay đổi dữ liệu
`App_Core/audit.py` nối signal `pre_save` / `post_save` / `post_delete` cho các model trong `TRACKED_MODELS`:

Danh mục, Sản phẩm, Đơn vị bán, Topping, Topping của món, Món theo cửa hàng, Khuyến mãi, Khách hàng, Hạng khách hàng, Bàn, Cửa hàng, Doanh nghiệp (gồm cờ tính năng), Tài khoản.

- Sửa: so giá trị cũ / mới từng field, bỏ qua field không đổi; `password`, `qr_token` chỉ ghi *đã thay đổi*. Ví dụ: `Sửa đơn vị bán "Ly": Giá: 30.000 → 35.000`.
- Bỏ qua các field kỹ thuật (`slug`, `display_order`, `last_login`, số liệu tích điểm của khách…) — cấu hình `exclude` / `mask` theo từng model.
- **Chỉ ghi khi thay đổi đến từ request của người đã đăng nhập.** Seed, lệnh quản trị, migration không sinh nhật ký. Request hiện tại được giữ bằng `ContextVar` qua `App_Core.audit.AuditContextMiddleware` (đặt sau `AuthenticationMiddleware` trong `MIDDLEWARE`).
- `bulk_create` / `update()` không qua signal — nhập Excel ghi một dòng tổng `catalog.import`.

## Ghi thủ công
```python
from App_Core.audit import Action, log_action

log_action(Action.ORDER_REFUND, request=request, store_id=order.store_id, obj=order,
           object_type='Đơn bán', message='...', extra={...})
```
- Tự lấy user, tenant, IP từ request (`request` bỏ trống thì dùng request trong `ContextVar`). Không có tenant → không ghi.
- Lỗi khi ghi nhật ký chỉ được log, không làm hỏng thao tác chính.
- Thêm loại mới: thêm vào `AuditLog.Action` (cần migration vì là `choices`) và vào `AUDIT_ACTION_GROUPS` trong `App_Quanly/views.py`.

## Test
`App_Sales.tests_ops.AuditLogTests`: huỷ món + chuyển bàn, sửa giá có diff, không ghi khi không có request, đăng nhập / sai mật khẩu, trang nhật ký chỉ manager và chỉ thấy tenant của mình.
