# CHƯƠNG 1. GIỚI THIỆU ĐỀ TÀI

## 1.1. Vấn đề cần giải quyết

Xe robot điều khiển từ xa phụ thuộc vào việc người dùng liên tục quan sát và gửi lệnh. Để xe tự di chuyển và bám một mục tiêu, hệ thống cần kết hợp thông tin khoảng cách với dữ liệu nhận diện. Cảm biến siêu âm đo được vật cản nhưng không phân biệt mục tiêu; camera cung cấp thông tin hình ảnh nhưng chịu ảnh hưởng của ánh sáng và độ trễ. Bài toán vì vậy cần giải quyết cả việc phối hợp dữ liệu, chuyển chế độ điều khiển và xử lý khi mất kết nối hoặc dữ liệu không còn hợp lệ.

Đề tài xây dựng xe robot sử dụng ESP32 tích hợp điều khiển qua Wi-Fi, tránh vật cản và bám mục tiêu bằng thị giác máy tính. ESP32 điều khiển động cơ và đọc cảm biến; camera iPhone gửi hình đến laptop để xử lý bằng YOLOv8n. Hệ thống phân định quyền điều khiển giữa các chế độ, giám sát thời hạn lệnh và cung cấp giao diện theo dõi trạng thái. Mô hình là cơ sở thực hành tích hợp phần cứng nhúng, truyền thông không dây và xử lý ảnh trong cùng một hệ thống.

## 1.2. Mục tiêu đề tài

Thiết kế mô hình trên ESP32-WROOM-32, lập trình firmware bằng C++ với Arduino và PlatformIO, kết hợp ứng dụng Python trên laptop. Các mục tiêu kỹ thuật gồm:

- **Điều khiển xe và quản lý chế độ:** điều khiển động cơ qua L298N bằng PWM, hỗ trợ tiến, lùi, quay và dừng. Tổ chức các chế độ Wi-Fi Manual, Obstacle Auto, AI và Auto + AI; chỉ cơ chế được cấp quyền mới điều khiển động cơ.

- **Tự động tránh vật cản:** dùng HC-SR04 gắn trên servo SG90 để đo phía trước và quét hai bên. Với ngưỡng 50 cm, xe thực hiện lùi, quét và chọn hướng quay khi bị chặn. Chế độ Obstacle Auto chạy độc lập trên ESP32, không cần laptop.

- **Nhận diện và bám mục tiêu:** truyền hình iPhone qua WebRTC, chạy YOLOv8n dạng ONNX trên laptop để phát hiện lớp target. Xác nhận mục tiêu qua 3 ảnh mới trước khi bám, dừng để căn hướng khi lệch; giữ dừng khi khoảng cách không lớn hơn 50 cm và chỉ tiếp tục khi lớn hơn 55 cm.

- **Phối hợp Auto + AI:** tự tránh vật cản khi chưa thấy mục tiêu, dừng xác nhận rồi chuyển sang bám. Nếu mất mục tiêu liên tục 1,5 giây trên ảnh mới, trở lại tìm kiếm bằng hành vi tránh vật cản. Chuyển hành vi phải qua bước dừng và chờ cảm biến ổn định.

- **Giám sát và xử lý an toàn:** cung cấp web điều khiển, ghép camera bằng QR, xem trạng thái và tải nhật ký. Hỗ trợ dừng khẩn cấp, thu hồi phiên cũ và giám sát thời hạn lệnh 500 ms. Kết thúc phiên AI hoặc Auto + AI khi ảnh hay kết quả xử lý quá 0,5 giây.

- **Mô phỏng và kiểm thử:** xây dựng mô hình Webots tương thích giao diện điều khiển xe thật; kiểm tra chuyển trạng thái, giao tiếp và phản ứng trước lỗi. Kết hợp thử nghiệm phần cứng để đánh giá khả năng tránh vật cản và bám mục tiêu.

## 1.3. Phạm vi và giới hạn

**Phạm vi:** đề tài tập trung vào mô hình xe chạy trong nhà, trên mặt sàn tương đối bằng phẳng và trong điều kiện thử nghiệm được kiểm soát. Phần cứng gồm ESP32-WROOM-32, L298N, động cơ một chiều, HC-SR04, SG90 và đèn báo. Phần mềm gồm firmware, giao diện web, ứng dụng xử lý ảnh trên laptop và mô phỏng Webots. iPhone gắn trên xe cung cấp hình ảnh; các thiết bị trao đổi dữ liệu trong mạng LAN, ghép camera qua HTTPS và truyền video bằng WebRTC.

**Giới hạn:** hệ thống chỉ bám lớp target của mô hình hiện có, chưa bảo đảm giữ đúng danh tính khi có nhiều vật cùng loại. Nhận diện phụ thuộc ánh sáng, che khuất và góc camera; điều khiển còn phụ thuộc laptop và mạng. Ngưỡng 0,5 giây dùng để giám sát độ mới dữ liệu, không bảo đảm độ trễ toàn tuyến hoặc thời gian thực cứng. Sau lỗi kết thúc phiên, người dùng phải chủ động bắt đầu lại.

Sonar đo vật gần nhất phía trước, chưa xác định đó có phải mục tiêu và không bao quát đầy đủ hai bên, phía sau xe. Quãng lùi và góc quay ước tính theo thời gian, chưa có phản hồi encoder nên cần hiệu chỉnh trên xe thật. Ngưỡng 50 cm không bảo đảm khoảng cách dừng vật lý chính xác do quán tính và độ trễ.

Đề tài chưa bao gồm xây dựng bản đồ, định vị hay lập kế hoạch đường đi toàn cục. Giao diện phục vụ LAN tin cậy, chưa có xác thực và phân quyền đầy đủ để công khai trên Internet. Mô phỏng hỗ trợ kiểm tra logic; hiệu quả vận hành cần được đánh giá bằng thử nghiệm thực tế.
