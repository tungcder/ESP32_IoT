# Điều khiển robot Webots bằng web

## Cách chạy

Trong PowerShell tại thư mục project, chạy một lệnh:

```powershell
.\simulation\run.ps1
```

Script tìm Webots trong `WEBOTS_HOME`, `C:\Program Files\Webots` hoặc `G:\Webots`,
mở đúng world và bật Real-time. Nếu PowerShell chặn chạy script, dùng lệnh gọi
trực tiếp `webots.exe` bên dưới; không cần thay đổi ExecutionPolicy toàn máy.

Hoặc mở thủ công:

1. Mở Webots, chọn **File → Open World** và mở
   `G:\ESP32_IoT\simulation\webots\worlds\esp32_car.wbt`.
2. Chọn chạy **Real-time**. Console sẽ hiện
   `Webots controller ready: http://127.0.0.1:8081`.
3. Mở **http://127.0.0.1:8081** trên trình duyệt.
4. Giữ nút mũi tên để lái xe 3D; thả nút hoặc bấm nút vuông để dừng.

Trên máy này đã có Webots R2025a tại `G:\Webots`. Có thể mở world bằng PowerShell:

```powershell
& 'G:\Webots\msys64\mingw64\bin\webots.exe' --mode=realtime 'G:\ESP32_IoT\simulation\webots\worlds\esp32_car.wbt'
```

Nếu Webots không tìm thấy Python, vào **Tools → Preferences → Python command**
và chọn `C:\Python314\python.exe` (hoặc Python 3 tương thích trên máy).
Controller chỉ dùng thư viện chuẩn Python, không cần pip install.
Không chạy trực tiếp `esp32_car.py`: Webots phải khởi chạy controller.

Nếu cổng 8081 đang bị một world khác sử dụng, có thể chạy bản riêng ở cổng 8082:

```powershell
.\simulation\run.ps1 -Port 8082
```

Sau đó mở `http://127.0.0.1:8082`. Cổng VPN đã cấu hình vẫn trỏ về 8081;
thay cổng mô phỏng sẽ không tự thay đổi cấu hình Tailscale.
Trên máy có Webots ở chỗ khác, truyền `-WebotsPath 'D:\Webots\msys64\mingw64\bin\webots.exe'`.

## Truy cập từ máy khác qua VPN Tailscale

Máy chạy Webots đã có Tailscale, IP VPN hiện tại là **100.100.187.94**.
Đã cấu hình chuyển tiếp TCP chạy nền từ cổng VPN 8081 đến web local
`127.0.0.1:8081`. Controller tiếp tục chỉ lắng nghe trên localhost.

Trên máy tính hoặc điện thoại khác:

1. Cài Tailscale từ https://tailscale.com/download và kết nối cùng tailnet với
   máy chạy Webots, hoặc được quản trị viên cấp quyền truy cập máy này.
   Không cần chia sẻ mật khẩu tài khoản giữa các máy.
2. Đảm bảo chính sách mạng Tailscale cho phép truy cập TCP 8081 của máy chủ.
3. Mở **http://100.100.187.94:8081** trên trình duyệt.

Các máy có thể dùng Wi-Fi khác nhau hoặc mạng di động. Chỉ máy chủ cần chạy
Webots; các máy còn lại dùng trình duyệt. Giữ máy chủ bật và world chạy Real-time.
Tắt Webots thì web local dừng, dù cấu hình VPN vẫn còn.

Lệnh bật chia sẻ trên máy chủ, nếu cần cấu hình lại (PowerShell với quyền phù hợp):

```powershell
& 'C:\Program Files\Tailscale\tailscale.exe' serve --bg --tcp=8081 tcp://127.0.0.1:8081
```

Kiểm tra hoặc tắt riêng chia sẻ cổng này:

```powershell
& 'C:\Program Files\Tailscale\tailscale.exe' serve status
& 'C:\Program Files\Tailscale\tailscale.exe' serve --tcp=8081 off
```

IP trên là IP Tailscale của máy chủ, không phải IP Wi-Fi. Mạng hiện tại chưa bật
MagicDNS nên dùng IP trực tiếp. Đây là chia sẻ trong VPN, không phải đường dẫn
công khai trên Internet; không cần mở port router hoặc dùng Tailscale Funnel.

Mọi máy được VPN cho phép vào cổng này đều có thể gửi lệnh. Nên để một người lái
tại một thời điểm vì hiện chưa có cơ chế giữ quyền điều khiển riêng cho từng máy.
Web chia sẻ các nút điều khiển và trạng thái; cảnh 3D vẫn hiển thị trong Webots
trên máy chủ, chưa có video hoặc streaming 3D sang trình duyệt của máy khác.

## Chức năng

- Dùng giao diện từ `src/web_page.cpp`, giữ nguyên firmware robot thật.
- Điều khiển tiến/lùi/trái/phải/dừng, chế độ LED AUTO/MANUAL và bật/tắt cả bốn LED.
- Có thể giữ phím mũi tên để lái; thả phím, nhấn Space/Esc hoặc rời cửa sổ thì dừng.
  Lệnh chuyển động gửi tuần tự, chỉ giữ lệnh chờ mới nhất; chuyển AUTO không gửi
  thêm lệnh dừng cạnh tranh với lệnh bật AUTO.
- Server xử lý nhiều kết nối đồng thời để tab mở sẵn hoặc máy khác không chặn
  lệnh điều khiển. Điều này không cấp quyền lái riêng cho từng người.
- **OBSTACLE AUTO** chạy logic Python tương ứng `src/obstacle_avoid.cpp`:
  quét phía trước 90° → 60° → 90° → 120° trong lúc tiến; lùi khi gần vật cản,
  quét phải/trái rồi chọn hướng quay. Hai bên bị chặn thì quay phải 900 ms;
  gặp vật cản liên tiếp thì tăng thời gian quay, tối đa 850 ms.
- Sonar được lấy ba mẫu cách nhau tối thiểu 8 ms rồi lấy trung vị. Bản mô phỏng
  giữ giá trị gần trong 1 giây khi mất Echo, theo chính sách trong code C++ mới.
  Việc lấy mẫu không chặn vòng lặp Webots; nhịp mô phỏng 16 ms làm thời gian lấy
  mẫu dài hơn các khoảng delay 8 ms trên firmware. Chưa tái hiện nhiễu Echo thực.
- Bảng bên cạnh hiển thị khoảng cách, trạng thái, LED và 40 sự kiện gần nhất.
  Có nút tạm dừng log, xóa hiển thị và thử mất lệnh.
- Timeout Manual và khoảng cách an toàn đọc từ `include/config.h`.
  Không nhận lệnh Manual quá 500 ms thì dừng; AUTO tiếp tục theo cảm biến.
- Đổi sang AUTO đặt lại quá trình quét, sang Manual đưa sonar về trước.
- Xe ban đầu hướng +X, bên trái là +Y, trục Z hướng lên. Sàn 4,4 × 4,4 m,
  có tường và ba vật cản. Vật cản màu cam nằm phía trước xe.

Đây là mô phỏng chuyển động và logic Python, không chạy firmware Arduino trên
chip ESP32 và không xác nhận GPIO, mạch L298N hay Wi-Fi thực. Sonar mô phỏng trả
tối đa 200 cm; chưa tái hiện lỗi mất Echo của HC-SR04. Chưa tích hợp AI.
Kế hoạch YOLOv8 ONNX nằm riêng tại `G:\robot_IOT\ai_object_navigation_plan.md`.

## Kiểm tra

```powershell
python -m unittest discover -s simulation/webots/tests -v
node --test simulation/webots/tests/test_controls.js
```

Thử trên Webots: giữ tiến, thả để dừng, kiểm tra các hướng và LED; bấm **Thử mất
lệnh** để xe tự dừng; chọn AUTO để quan sát quá trình quét tránh vật cản.
Chạy Real-time để thời gian thực của nút web phù hợp với chuyển động mô phỏng.
Khi Pause, xe không chuyển động dù vẫn có thể nhận HTTP; Resume để tiếp tục.
Nếu cổng 8081 bị chiếm, đóng bản controller cũ rồi reset world.
