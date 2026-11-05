# Chỉnh giá bán trong giỏ hàng

Quản lý → Cấu hình tính năng → **Cho phép chỉnh giá khi bán hàng** (mặc định tắt).
Có thể bật thêm **Bắt buộc nhập lý do chỉnh giá**. Chỉ quản lý thay đổi được cấu hình.

Trong giỏ, bấm biểu tượng chỉnh giá cạnh đơn giá, nhập giá và lý do, rồi **Lưu giá**.
Đây là giá cho **một món gồm topping**, không thay đổi giá danh mục. Nút **Giá gốc**
khôi phục giá hiện tại theo cửa hàng và topping. Số lượng, thuế, khuyến mãi,
ưu đãi khách hàng và hoá đơn được tính theo giá bán đã lưu.

- Giỏ bàn lưu giá ngay trên server; tăng số lượng, ghi chú, chuyển/tách/gộp bàn
  và chia hoá đơn giữ giá và người chỉnh. Món mới thêm không gộp vào dòng đã chỉnh giá.
- Giỏ mang về cũng gọi server khi lưu/khôi phục giá để ghi nhật ký ngay. Giá được
  ký bởi server, ràng buộc với doanh nghiệp, cửa hàng, đơn vị món và topping;
  không tin giá gốc hoặc tên người chỉnh gửi từ trình duyệt. Chứng thực có hạn 7 ngày.
- Khi đưa giỏ mang về vào bàn hoặc chuyển bàn thành mang về, giữ thông tin người
  chỉnh; người thu tiền có thể khác người chỉnh giá.
- Tắt tính năng chặn chỉnh giá mới và thanh toán dòng còn giá chỉnh. Nhân viên
  vẫn có thể khôi phục giá gốc. Lịch sử chỉnh giá và đơn đã thanh toán được giữ lại.
- **Nhật ký thao tác → Chỉnh giá bán** ghi người thao tác, thời gian, cửa hàng,
  giá trước/sau và lý do, kể cả khôi phục. Giá không được lưu nếu không ghi được
  nhật ký. Lịch sử đơn hiển thị giá gốc, người chỉnh cuối cùng, thời gian và lý do.

Triển khai: chạy `python manage.py migrate` để thêm các trường cấu hình/snapshot
và loại nhật ký mới. Không có migration thay đổi giá hay bật tính năng cho dữ liệu cũ.

Kiểm thử: `python manage.py test App_Sales.tests_price_override`.
