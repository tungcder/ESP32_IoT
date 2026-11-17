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

- Dùng chung giao diện từ `src/web_page.cpp` với firmware robot thật.
- **OBSTACLE AUTO** chỉ hiện trạng thái và nhật ký; **WI-FI MANUAL** hiện nút điều khiển và nhật ký.
- LED trên xe tự hiển thị theo hướng chuyển động; không còn phần điều khiển LED trên web.
- Có thể giữ phím mũi tên để lái; thả phím, nhấn Space/Esc hoặc rời cửa sổ thì dừng.
  Lệnh chuyển động gửi tuần tự, chỉ giữ lệnh chờ mới nhất; chuyển AUTO không gửi
  thêm lệnh dừng cạnh tranh với lệnh bật AUTO.
- Server xử lý nhiều kết nối đồng thời để tab mở sẵn hoặc máy khác không chặn
  lệnh điều khiển. Điều này không cấp quyền lái riêng cho từng người.
- **OBSTACLE AUTO** chạy logic Python tương ứng `src/obstacle_avoid.cpp`:
  xe tiến/lùi ở 50% PWM, quay trái/phải ở 80% PWM; sonar giữ 90° khi tiến. Khoảng cách phía trước <=40 cm
  thì xe lùi mục tiêu 8 cm, dừng ngắn để đo bên trái tại 135° rồi 180°.
  Cả hai góc trái >40 cm thì rẽ trái mục tiêu 90°. Nếu trái bị chặn, đo bên phải
  tại 45° rồi 0°; phải trống thì rẽ phải mục tiêu 90°. Nếu cả hai phía bị chặn,
  lùi thêm mục tiêu 12 cm và quét lại từ trái. Không quay vào hướng đã bị chặn.
  Quãng lùi/góc quay dùng thời gian cấu hình chung với firmware, chưa đo bằng
  encoder. Xem [cách hiệu chỉnh](../../docs/AUTO_CALIBRATION.md).
  Servo về 90° trước khi quay và xe tiếp tục tiến sau khi quay. Đổi tab trình
  duyệt không hủy AUTO; chuyển sang Wi-Fi Manual để dừng AUTO.
- Firmware đọc một mẫu sonar mỗi lần, cách nhau ít nhất 70 ms khi xe tiến.
  Mất Echo được coi là chưa an toàn: xe lùi và quét hướng khác thay vì đứng
  yên mãi. Mô phỏng chưa tái hiện nhiễu Echo thực của HC-SR04.
- Nhật ký trong giao diện hiển thị trạng thái chuyển động và các bước tránh vật cản
  ở cả hai mode; nút **Xóa hiển thị** chỉ xóa log trên trình duyệt.
- Bảng Webots hiển thị khoảng cách, góc cảm biến và bước AUTO.
- Timeout Manual và khoảng cách an toàn đọc từ `include/config.h`.
  Không nhận lệnh Manual quá 500 ms thì dừng; AUTO tiếp tục theo cảm biến.
- Đổi sang AUTO đặt lại quá trình quét, sang Manual đưa sonar về trước. Lệnh
  lái thủ công gửi khi AUTO đang chạy bị từ chối HTTP 409.
- Xe ban đầu hướng +X, bên trái là +Y, trục Z hướng lên. Sàn 4,4 × 4,4 m,
  có tường và ba vật cản. Vật cản màu cam nằm phía trước xe.

Đây là mô phỏng chuyển động và logic Python, không chạy firmware Arduino trên
chip ESP32 và không xác nhận GPIO, mạch L298N hay Wi-Fi thực. Sonar mô phỏng trả
tối đa 200 cm; chưa tái hiện lỗi mất Echo của HC-SR04. Controller hỗ trợ mode AI
và giao thức phiên/lệnh tương ứng firmware để nhận lệnh từ laptop.
[Ứng dụng AI](../../ai/README.md) nhận camera iPhone qua WebRTC và chạy YOLOv8n riêng;
chưa có camera ảo trong world. Đặt địa chỉ xe `http://127.0.0.1:8081` trên web AI.

### Tốc độ quay AI 70–64% PWM

Webots nhận lệnh từ cùng `ai/follower.py` dùng cho xe thật, không có bản sao
thuật toán AI riêng. Vượt line ngoài 35–65%: dừng ít nhất 150 ms rồi quay ở
70% PWM. Khi tâm mục tiêu tiến về vùng dừng 40–60%, tốc độ giảm dần qua 67%
về 64% PWM; vào vùng dừng thì dừng quay, xác nhận 3 ảnh mới rồi tiến 50% PWM.

1. Chạy Webots bằng `simulation/run.ps1`, giữ world ở Real-time.
2. Khởi động lại ứng dụng AI bằng `ai/run.ps1` để nạp tốc độ mới.
3. Trên bảng AI, đặt **Địa chỉ ESP32 hoặc Webots** thành
   `http://127.0.0.1:8081` rồi bấm **Lưu cấu hình**. Nếu chạy Webots với
   `-Port 8082`, dùng cổng 8082 tương ứng.
4. Quét QR bằng iPhone, mở Safari và bật camera trước. Khi có hình mới,
   bấm **Bắt đầu bám mục tiêu**. Dịch mục tiêu sang trái/phải và về vùng giữa.
5. Trên trang web Webots, mục **Thông tin mô phỏng Webots** hiển thị chế độ,
   chuyển động và PWM động cơ để đối chiếu 70% → 67% → 64% → 0%.

Camera iPhone trong phép thử này không tự đổi hướng theo xe 3D; cần dịch
mục tiêu hoặc xoay điện thoại để đưa tâm mục tiêu về vùng giữa. Webots áp dụng
PWM theo tỷ lệ tốc độ bánh xe, chưa mô phỏng đầy đủ quán tính và ma sát của xe thật.

## Vận hành trên Webots

Thử trên Webots: giữ tiến, thả để dừng, kiểm tra các hướng và LED; chọn AUTO
để quan sát quá trình quét tránh vật cản và nhật ký. Trong AUTO, bàn phím và
nút dừng thủ công không gửi lệnh; chuyển về Manual để điều khiển.
Chạy Real-time để thời gian thực của nút web phù hợp với chuyển động mô phỏng.
Khi Pause, xe không chuyển động dù vẫn có thể nhận HTTP; Resume để tiếp tục.
Nếu cổng 8081 bị chiếm, đóng bản controller cũ rồi reset world.
