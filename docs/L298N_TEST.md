# Test riêng hai kênh L298N

Chọn môi trường PlatformIO `l298n_test` để nạp `src/l298n_test.cpp`.
Sau khi khởi động, ESP32 chờ 2 giây, chạy kênh A (OUT1–OUT2) trong 2 giây,
dừng 1 giây, rồi chạy kênh B (OUT3–OUT4) trong 2 giây và dừng hẳn.
Nhấn EN/RST để chạy lại một lần. Kê cả bốn bánh khỏi mặt đất trước khi thử.
Bản test không dùng Wi-Fi, cảm biến hoặc servo.

| ESP32 | L298N |
|---|---|
| GPIO13 | ENA |
| GPIO14 | ENB |
| GPIO27 | IN1 |
| GPIO26 | IN2 |
| GPIO25 | IN3 |
| GPIO33 | IN4 |
| GND | GND |

Motor A nối OUT1–OUT2; motor B nối OUT3–OUT4. Nếu ENA/ENB đang được nối
bằng jumper hoặc dây ngắn trên module, giữ nguyên và không cần nối GPIO13/14.
Nếu muốn nối ENA/ENB với ESP32, tháo jumper/dây nối trước và chỉ nối chân
tín hiệu ENA/ENB (không nối chân 5V) tới GPIO13/14.

Tốc độ test và firmware Wi-Fi được đặt bằng PWM trên các chân IN tại
`Config::MOTOR_SPEED_PERCENT` trong `include/config.h`. Giá trị hiện tại 50%,
tương ứng PWM làm tròn 128/255. Ở mức này motor có thể không thắng được ma sát
để khởi động dưới tải; cần kiểm tra thực tế với nguồn và motor đang dùng.
Kê bánh xe khỏi mặt bàn trước khi nạp hoặc reset. Chiều quay thực tế phụ thuộc
vào cách nối hai dây của từng motor.

Nếu 3 pin 18650 mắc nối tiếp, điện áp có thể đạt 12,6 V khi sạc đầy.
Dùng nguồn phù hợp với điện áp định mức của motor. PWM giới hạn mức điều khiển
trung bình, không giới hạn dòng điện tức thời.

Kiểm tra cổng CH340 hiện tại bằng `pio device list`, rồi thay `COMx` bên dưới:

```powershell
pio run -e l298n_test -t upload --upload-port COMx
pio device monitor --port COMx --baud 115200
```

Mở Serial Monitor có thể làm board reset và chạy test lại. Đóng monitor trước
khi nạp firmware. Để quay về điều khiển web, nạp lại môi trường `esp32dev`:

```powershell
pio run -e esp32dev -t upload --upload-port COMx
```
