# 1) In hoá đơn, phiếu tạm tính, phiếu bếp, báo cáo ca

Backlog: BL-009 (bước 1 — in từ trình duyệt). In thẳng máy in nhiệt ESC/POS (bước 2) chưa làm.

## Cách in
- Mỗi loại phiếu là một trang HTML riêng, khổ giấy nhiệt **80mm** hoặc **58mm**, in bằng hộp thoại in của trình duyệt (`window.print()` + CSS `@media print`).
- Template gốc: `templates/App_Sales/print/_base.html` (thanh công cụ chọn khổ giấy / In / Đóng — ẩn khi in). Khổ giấy lưu ở localStorage `eapp_print_paper` (`80` | `58`).
- `?autoprint=1`: trang tự gọi `window.print()` khi tải xong, in xong gửi `postMessage({type: 'eapp-print-done'})` cho trang cha.
- In không mở tab mới: `static/js/eapp_print.js` → `window.eappPrint(url)` tạo iframe ẩn trỏ tới `url?autoprint=1`, gỡ iframe khi in xong. Các lệnh in được **xếp hàng** (in hoá đơn + phiếu bếp liên tiếp không bị chồng hộp thoại). Nút bất kỳ có `data-print-url="..."` tự gắn hành vi này.
- Các view in dùng `@xframe_options_sameorigin` (dự án mặc định `X-Frame-Options: DENY`), nếu thiếu thì iframe ẩn bị chặn.

> Hộp thoại chọn máy in vẫn hiện mỗi lần in. Muốn in thẳng không hỏi: chạy Chrome trên máy POS / máy bếp với cờ `--kiosk-printing` và đặt máy in nhiệt làm mặc định.

## Các loại phiếu
| Phiếu | URL | Quyền | Nội dung |
|---|---|---|---|
| Hoá đơn | `GET /orders/<order_id>/receipt/` | Staff/manager có quyền store của đơn | Tên, địa chỉ, SĐT cửa hàng; số HĐ, giờ, bàn (`Order.table_name`) hoặc *Mang về*, thu ngân, khách; món + topping + ghi chú; tạm tính, giảm giá (KM / hạng), *Thuế (x%)* khi có, tổng, khách đưa, tiền thừa; các lần hoàn tiền + *Thực thu* |
| Phiếu tạm tính | `GET /tables/<table_id>/bill/` | Staff/manager có quyền bàn | Món trong giỏ bàn, tạm tính (chưa gồm KM / ưu đãi hạng; khi tenant có thuế thì in *Tiền món*, *Thuế (x%)* và tạm tính đã gồm thuế), QR + tài khoản chuyển khoản của cửa hàng |
| Phiếu bếp | `GET /kitchen/tickets/<ticket_id>/print/` | Như trên; 403 khi tắt `show_kitchen_feature` | Tên bàn (chữ lớn), nguồn, giờ gửi, nhân viên, mã đơn; món × SL, topping, ghi chú; món đã huỷ gạch ngang *ĐÃ HUỶ* |
| Báo cáo ca | `GET /shifts/<shift_id>/print/` | Như trên; 403 khi tắt `show_shift_feature` | Xem `2_shifts_and_refunds.md` |

## Đánh dấu in lại
- `Order.print_count`, `KitchenTicket.print_count`: tăng mỗi lần mở trang với `autoprint=1` (xem trước không tính). Nút **In** trên thanh công cụ của trang in cũng tải lại với `autoprint=1` để được đếm.
- Từ lần thứ 2: hoá đơn in dấu **BẢN IN LẠI (lần N)**, phiếu bếp in **IN LẠI (lần N)**, và ghi nhật ký `order.reprint` / `kitchen.reprint` (`3_audit_log.md`).

## Nút In trong giao diện
| Nơi | Điều khiển |
|---|---|
| POS — menu tài khoản, mục *In ấn* | Công tắc **Tự in hoá đơn** (localStorage `eapp_pos_auto_print_receipt`), **Tự in phiếu bếp** (`eapp_pos_auto_print_kitchen`, chỉ khi bật bếp). Mặc định tắt |
| POS — sau thanh toán | Tự in hoá đơn nếu bật; nếu không, toast góc dưới có nút **In hoá đơn** (8 giây). Checkout trả thêm `kitchen_ticket_id` để tự in phiếu bếp |
| POS — giỏ bàn | Nút **In tạm tính**; sau **Báo bếp** tự in phiếu bếp nếu bật |
| Màn hình bếp | Nút máy in trên từng phiếu; công tắc **Tự in phiếu** (`eapp_kitchen_auto_print`) chỉ tự in phiếu **mới** có `print_count = 0`, nên nhiều màn hình bếp không in trùng |
| Đơn trong ngày, Lịch sử đơn | Nút máy in trên từng đơn (Lịch sử đơn: cả trong modal chi tiết) |
| Trang Ca làm việc | **In báo cáo tạm** (ca đang mở), nút in từng ca trong lịch sử; tự in báo cáo ngay sau khi chốt ca |

## Test
`App_Sales.tests_ops.ReceiptPrintTests`: nội dung hoá đơn, đếm lần in + dấu in lại + nhật ký, 403 khi không có quyền store, tên bàn trên hoá đơn tại bàn, phiếu tạm tính, phiếu bếp (kể cả 403 khi tắt bếp).
