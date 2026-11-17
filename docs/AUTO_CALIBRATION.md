# Né vật trên nền firmware của Tùng

Thông số nằm trong `include/config.h`. Firmware và Webots đọc cùng cấu hình.

1. Servo giữ 90° khi tiến. Khoảng cách <=50 cm bắt đầu né.
2. Lùi mục tiêu 8 cm rồi dừng để quét bên trái tại 135° và 180°.
3. Cả hai góc trái >50 cm: quay trái mục tiêu 90°.
4. Nếu trái bị chặn, quét bên phải tại 45° và 0°. Cả hai góc phải >50 cm thì quay phải.
5. Nếu cả hai bên bị chặn, lùi thêm mục tiêu 12 cm và quét lại từ trái.

Mất Echo được coi là hướng chưa rõ. Xe chưa có cảm biến phía sau để kiểm tra đường lùi.
Chế độ AI giữ servo ở 90° và dùng bộ điều khiển riêng; không chạy đồng thời với Auto.

## Thông số hiện tại

| Thông số | Giá trị | Tác dụng |
|---|---:|---|
| `MOTOR_SPEED_PERCENT` | 50 | Tiến/lùi PWM 128/255 |
| `MOTOR_TURN_SPEED_PERCENT` | 80 | Quay trái/phải qua nút Manual trên web; PWM 204/255 |
| `AUTO_TURN_SPEED_PERCENT` | 70 | Quay trong Obstacle Auto và phần né vật cản của Auto + AI; PWM 179/255 |
| `AUTO_REVERSE_CM` | 8 | Quãng lùi đầu tiên, ước lượng theo thời gian |
| `AUTO_RETRY_REVERSE_CM` | 12 | Quãng lùi khi hai bên bị chặn |
| `AUTO_REVERSE_MS_PER_CM` | 50 | Lùi đầu 400 ms; lùi lại 600 ms |
| `AUTO_LEFT_90_MS` | 780 | Thời gian quay trái |
| `AUTO_RIGHT_90_MS` | 780 | Thời gian quay phải |

Mức quay Auto hiện là 70% PWM; Manual dùng 80% PWM. Thời gian quay 780 ms
vẫn là giá trị ước lượng cũ ở 50% PWM; cần đo và hiệu chỉnh lại ở 70% để đạt 90°.
Phần né vật cản trong Auto + AI cũng dùng mức quay Auto này.

AI yêu cầu tiến ở 45% PWM và quay ở 58–62% PWM, phù hợp giới hạn riêng của firmware.
Trên xe thật, firmware bù lệch động cơ ở đầu ra AI: khi đi thẳng, trái 45%, phải 50%;
khi quay, trái 53–57%, phải 58–62%. Mức bù khi tiến và khi quay đều là 5 điểm phần trăm; lần lượt được đặt tại
`AI_FORWARD_RIGHT_BOOST_PERCENT` và `AI_TURN_LEFT_REDUCTION_PERCENT` trong `include/config.h`.
Mức bù cũng áp dụng khi Auto + AI đang bám mục tiêu. Phần tự né vật cản vẫn dùng mức Auto.
AI dừng tiến khi khoảng cách <=50 cm và chỉ tiếp tục khi >55 cm.
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
