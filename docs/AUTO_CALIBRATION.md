# Né vật ở mức điều khiển 50%

Thông số nằm trong `include/config.h`. Firmware và Webots đọc cùng cấu hình.

1. Servo giữ 90° khi tiến. Khoảng cách <=40 cm (tính từ mặt cảm biến) bắt đầu né.
2. Lùi mục tiêu 20 cm rồi dừng ngắn để quét 45° và 0° (bên trái).
3. Cả hai góc trái >40 cm: rẽ trái mục tiêu 90° rồi tiến tiếp.
4. Nếu trái bị chặn, quét 135° và 180° (bên phải). Cả hai góc phải >40 cm:
   rẽ phải mục tiêu 90° rồi tiến tiếp.
5. Nếu cả hai bên bị chặn: lùi thêm mục tiêu 30 cm, rồi quét lại từ trái.
   Chu trình tiếp tục cho tới khi có hướng đi hoặc người dùng ra lệnh STOP/Manual.

Xe vẫn dừng ngắn để servo ổn định và đo. AUTO không có thời hạn tự kết thúc.
Timeout 500 ms chỉ áp dụng điều khiển tay. Mất Echo được coi là hướng chưa rõ,
không được tính là hướng trống; cảm biến lỗi liên tục sẽ gây chu trình lùi/quét
lặp lại. Xe chưa có cảm biến phía sau để kiểm tra đường lùi.

## Hiệu chỉnh quãng đường và góc quay

Xe chưa có encoder/IMU nên chưa thể đảm bảo đúng 20 cm, 30 cm hoặc 90°.
Các giá trị dưới đây là ước lượng ban đầu theo thời gian, chưa đo trên xe thật:

| Thông số | Giá trị ban đầu | Tác dụng |
|---|---:|---|
| `MOTOR_SPEED_PERCENT` | 50 | PWM 128/255, không phải vận tốc đo được |
| `AUTO_REVERSE_MS_PER_CM` | 50 | Lùi 20 cm: 1000 ms; lùi 30 cm: 1500 ms |
| `AUTO_LEFT_90_MS` | 780 | Thời gian quay trái tại chỗ |
| `AUTO_RIGHT_90_MS` | 780 | Thời gian quay phải tại chỗ |

Đo trên cùng mặt sàn, cùng nguồn pin và tải sử dụng thực tế:

- Nếu lệnh lùi 20 cm chỉ lùi được D cm: giá trị mới = giá trị cũ × 20 / D.
- Nếu lệnh quay 90° chỉ quay được A độ: thời gian mới = thời gian cũ × 90 / A.
- Hiệu chỉnh trái và phải riêng, làm tròn kết quả về số nguyên, nạp lại rồi đo lại.
- Nếu motor không quay tại PWM 50%, xử lý nguồn/ma sát trước; không dùng công thức
  khi D hoặc A bằng 0. Thay tốc độ, pin, tải hoặc mặt sàn cần hiệu chỉnh lại.

Webots dùng bánh bán kính 4 cm, khoảng cách hai bánh 20 cm, lệnh 5 rad/s.
Theo mô hình lý tưởng, các thời gian trên tương ứng gần 20/30 cm và 90°;
ma sát và trượt vẫn có thể làm sai lệch. Đây không phải đo kiểm trên robot thật.
