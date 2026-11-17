# Auto + AI

Camera iPhone gắn trên xe, hướng về phía trước. Laptop xử lý YOLO liên tục;
ESP32 giữ quyền điều khiển động cơ, cảm biến và thuật toán né vật cản.

## Sử dụng

1. Biên dịch và nạp firmware mới bằng PlatformIO vào ESP32.
2. Chạy `ai/run.ps1`, mở `https://localhost:8090` trên laptop.
3. Chọn đúng địa chỉ xe, lưu cấu hình và ghép camera iPhone như trước.
4. Khi model, camera và xe sẵn sàng, bấm **Bắt đầu Auto + AI**.
   Xe có thể tự di chuyển ngay cả khi chưa có mục tiêu trong ảnh.
5. Bấm **Dừng Auto + AI / AI** để kết thúc phiên và trở về Manual.
   **Dừng khẩn cấp** hoặc chọn Manual/Obstacle Auto cũng thu hồi phiên Hybrid.

Nút **Chỉ bám mục tiêu** giữ hành vi AI độc lập: không thấy mục tiêu thì đứng
yên chờ. Chế độ này nhận bbox lớp `target` từ confidence 50% và dùng trung
điểm bbox để căn hướng, không yêu cầu tìm được tâm thật của bảng.
Obstacle Auto độc lập vẫn hoạt động không cần laptop.

**Auto + AI** chỉ chấp nhận mục tiêu có confidence **>80%** và xác minh được
tâm từ các vòng bia đồng tâm. Đúng 80% hoặc chưa xác minh được tâm thì không
vẽ bbox và không bám ứng viên đó. Điều kiện áp dụng cả khi đang bám: mất điều
kiện sẽ vào LOST_HOLD, sau 1,5 giây vắng mục tiêu hợp lệ trên ảnh mới thì về SEARCH.
Nếu chưa bám, xe tiếp tục SEARCH khi không có mục tiêu hợp lệ.

## Hành vi

| Trạng thái | Xử lý |
| --- | --- |
| WAIT_FRAME | Giữ dừng sau khi bắt đầu, chờ ảnh mới đúng chế độ; bỏ kết quả và box của phiên trước |
| SEARCH | ESP32 tự chạy và né vật cản; laptop tiếp tục nhận diện |
| CONFIRM_TARGET | Dừng khi có ứng viên đã xác minh tâm và confidence >80%; xác nhận cùng mục tiêu qua 3 ảnh mới liên tiếp và xác nhận xe dừng ít nhất 150 ms |
| HANDOFF | Giữ dừng, đưa sonar về 90°, chờ ít nhất 300 ms, số đo hợp lệ và ảnh mục tiêu mới |
| TRACK / ALIGN | Dùng thuật toán bám và căn hướng AI hiện có |
| LOST_HOLD | Dừng ngay khi mất mục tiêu; xác nhận lại nếu mục tiêu xuất hiện; nếu vắng liên tục 1,5 giây trên ảnh mới thì trở lại SEARCH |
| FAULT | Kết thúc phiên do mất hình, lỗi AI hoặc liên lạc; cần chủ động bắt đầu lại |

Khi trở lại SEARCH, chu trình né vật cản được khởi tạo lại từ kiểm tra phía
trước; không tiếp tục bước lùi/quay cũ. Sonar không hợp lệ trong lúc Hybrid
đo khoảng cách thì dừng chờ, không coi khoảng trống chưa đo được là đường an toàn.
Khi bám: dừng ở 50 cm, tiếp tục khi lớn hơn 55 cm. Không bật Auto chỉ vì vật
phía trước ở gần, bởi sonar có thể đang đo chính mục tiêu.

Các bước lùi/quay của Auto vẫn ước tính theo thời gian; cần hiệu chỉnh trên xe
thật. Camera và sonar không cung cấp khả năng tránh mọi va chạm ở bên hông/phía sau.

## Phiên điều khiển và giao tiếp

`DriveMode::Hybrid` có hành vi con `HOLD`, `SEARCH`, `TRACK`; chỉ hành vi được
chọn mới được ghi lệnh động cơ. Một phiên duy nhất tồn tại qua các lần đổi
hành vi. Laptop gửi yêu cầu mỗi khoảng 100 ms, kể cả lúc SEARCH.

- `POST /hybrid/claim`: dùng `X-Mode-Epoch` hiện tại, trả `session` và `mode_epoch`.
- `POST /hybrid/command`: gửi form `session`, `seq`, `behavior`, `movement`, `speed`.
  `HOLD` và `SEARCH` chỉ nhận `movement=STOPPED&speed=0`. Với SEARCH, đây là
  tín hiệu duy trì phiên, không phải lệnh dừng thuật toán Auto.
- `POST /ai/release`: kết thúc phiên; Hybrid dừng và trở về Manual.
- `GET /status`: bổ sung `hybrid_supported=true`, `hybrid_state`.
- `POST /api/start` trên laptop: JSON `{"mode":"HYBRID"}`; bỏ `mode` vẫn bắt đầu AI độc lập.

ESP32 từ chối phiên sai, số thứ tự lặp và lệnh của phiên đã thu hồi. Không nhận
lệnh hợp lệ quá 500 ms trong bất kỳ hành vi Hybrid nào: dừng, về Manual và
thu hồi phiên. Ảnh/kết quả AI cũ quá 500 ms: laptop kết thúc phiên. Kết nối lại
không tự tạo phiên mới. Firmware cũ không quảng bá `hybrid_supported` sẽ không
được kích hoạt Hybrid.

## Kiểm tra

`python -m unittest discover -s tests -v` kiểm tra chính sách chuyển hành vi,
hợp đồng Webots và toàn bộ chu trình qua dịch vụ AI. Webots dùng cùng API với
xe thật; bắt đầu Hybrid từ bảng AI khi mô phỏng đang chạy.

Trước khi chạy trên sàn, kiểm tra với bánh xe được nâng khỏi mặt đất:
phát hiện mục tiêu khi đang lùi/quay, che mục tiêu ngắn/dài, rút camera,
ngắt liên lạc laptop, sonar mất Echo, chọn Manual và dừng khẩn cấp.
