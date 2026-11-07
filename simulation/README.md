# Mô phỏng robot ESP32

Toàn bộ mã mô phỏng đang sử dụng nằm trong thư mục `simulation/`.
Backend hiện tại là Webots; cấu hình Wokwi cũ đã được gỡ bỏ.

## Khởi chạy

Tại thư mục project `G:\ESP32_IoT`, chạy PowerShell:

```powershell
.\simulation\run.ps1
```

Mở **http://127.0.0.1:8081** để điều khiển xe trong Webots.
Nếu cổng 8081 đang được world khác dùng, đóng world đó hoặc chọn cổng khác:

```powershell
.\simulation\run.ps1 -Port 8082
```

Khi dùng cổng 8082, mở **http://127.0.0.1:8082**.

## Cấu trúc

```text
simulation/
  README.md                    Hướng dẫn chung
  run.ps1                      Lệnh khởi chạy Webots
  webots/
    README.md                  Hướng dẫn Webots và VPN Tailscale
    worlds/
      esp32_car.wbt            Xe, sàn, vật cản, động cơ và cảm biến
    controllers/esp32_car/
      esp32_car.py             Kết nối HTTP với robot Webots
      autopilot.py             Logic tránh vật cản trong mô phỏng
      panel.html               Thông tin cảm biến và bước AUTO trong mô phỏng
    tests/
      test_controller.py       Kiểm tra controller và HTTP
      test_controls.js         Kiểm tra giao diện chung của firmware và Webots
```

Controller dùng lại giao diện trong `src/web_page.cpp` và các giá trị trong
`include/config.h`. Hai file đó cũng phục vụ firmware ESP32 thật nên vẫn giữ
trong `src/` và `include/`. Các thư mục firmware không chứa mã Webots.

Chi tiết chạy, kiểm tra và kết nối máy khác qua VPN nằm trong
[hướng dẫn Webots](webots/README.md).
