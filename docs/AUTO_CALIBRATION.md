# Né vật trên nền firmware của Tùng

Thông số nằm trong `include/config.h`. Firmware và Webots đọc cùng cấu hình.

1. Servo giữ 90° khi tiến. Khoảng cách <=40 cm bắt đầu né.
2. Lùi mục tiêu 8 cm rồi dừng để quét bên trái tại 135° và 180°.
3. Cả hai góc trái >40 cm: quay trái mục tiêu 90°.
4. Nếu trái bị chặn, quét bên phải tại 45° và 0°. Cả hai góc phải >40 cm thì quay phải.
5. Nếu cả hai bên bị chặn, lùi thêm mục tiêu 12 cm và quét lại từ trái.

Mất Echo được coi là hướng chưa rõ. Xe chưa có cảm biến phía sau để kiểm tra đường lùi.
Chế độ AI giữ servo ở 90° và dùng bộ điều khiển riêng; không chạy đồng thời với Auto.

## Thông số giữ nguyên từ commit d431f59

| Thông số | Giá trị | Tác dụng |
|---|---:|---|
| `MOTOR_SPEED_PERCENT` | 50 | Tiến/lùi PWM 128/255 |
| `MOTOR_TURN_SPEED_PERCENT` | 50 | Giới hạn quay trái/phải |
| `AUTO_REVERSE_CM` | 8 | Quãng lùi đầu tiên, ước lượng theo thời gian |
| `AUTO_RETRY_REVERSE_CM` | 12 | Quãng lùi khi hai bên bị chặn |
| `AUTO_REVERSE_MS_PER_CM` | 50 | Lùi đầu 400 ms; lùi lại 600 ms |
| `AUTO_LEFT_90_MS` | 780 | Thời gian quay trái |
| `AUTO_RIGHT_90_MS` | 780 | Thời gian quay phải |

AI yêu cầu tiến ở 50% PWM và quay ở 40–50% PWM, phù hợp giới hạn của firmware.
AI dừng tiến khi khoảng cách <=20 cm và chỉ tiếp tục khi >25 cm.
Không có số đo hợp lệ thì AI chờ tại chỗ. Mất lệnh quá 500 ms thì firmware dừng và thu hồi phiên AI.

## Hiệu chỉnh trên xe thật

Xe chưa có encoder/IMU nên các quãng đường và góc quay đều là ước lượng.
Đo trên cùng mặt sàn, cùng nguồn pin và tải sử dụng thực tế:

- Với quãng lùi mục tiêu L cm nhưng đo được D cm: hệ số mới = hệ số cũ × L / D.
- Với góc quay mục tiêu 90° nhưng đo được A độ: thời gian mới = thời gian cũ × 90 / A.
- Hiệu chỉnh trái và phải riêng, nạp lại rồi đo lại. Không dùng công thức khi D hoặc A bằng 0.
- Thay tốc độ, pin, tải hoặc mặt sàn cần hiệu chỉnh lại.

Webots dùng bánh bán kính 4 cm, khoảng cách hai bánh 20 cm và tốc độ bánh 5 rad/s ở 50%.
Mô phỏng không thay thế đo kiểm trên robot thật.
