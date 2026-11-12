# Căn tâm mục tiêu và gọi trực tiếp trong bộ điều khiển robot

Mã nằm trong G:\yolov8n. Chỉ quay để căn bảng mục tiêu vào giữa ảnh; vận tốc tiến luôn bằng 0.

## Các file dùng trong project chính

- robot_ai.py: API ONNX, letterbox, chuẩn hóa RGB, inference, lọc class 11, NMS và gọi hàm điều khiển.
- target_alignment.py: tính tâm, độ lệch, chọn mục tiêu, chống rung và vẽ đường giữa.
- exports/best.onnx: model đã export lại, kèm cấu hình căn tâm trong metadata.

Copy hai file Python và model vào project chính, giữ hai file Python cùng thư mục hoặc thêm thư mục chứa chúng vào Python path. Truyền đường dẫn model vào TargetAI. Không cần PyTorch/Ultralytics cho API ONNX này; môi trường project chính cần numpy, opencv-python và onnxruntime. CUDA của PyTorch không tự cấp GPU cho ONNX Runtime. Môi trường hiện tại đang dùng ONNX Runtime CPU; nếu cần GPU phải cài và kiểm tra runtime/provider CUDA phù hợp riêng.

## Gọi AI từ hàm điều khiển

Khởi tạo TargetAI đúng một lần trước vòng lặp. Đưa frame BGR uint8 nguyên gốc vào; API tự resize/letterbox và xử lý đầu ra.

~~~python
import time
from robot_ai import TargetAI

ai = TargetAI(weights=r"G:\yolov8n\exports\best.onnx")

def robot_control(linear_velocity, angular_velocity):
    # Hàm của project robot: linear m/s, angular rad/s.
    # Đổi dòng dưới thành hàm điều khiển thực của robot.
    set_robot_velocity(linear_velocity, angular_velocity)

def control_step(frame_bgr=None, captured_at=None):
    if frame_bgr is None:
        # Gọi ở MỌI chu kỳ điều khiển khi chưa có ảnh mới.
        # Sau 0.5 giây không có ảnh mới, lệnh tự về STOP.
        return ai.tick(control=robot_control)
    result = ai.process_frame(
        frame_bgr,
        captured_at=captured_at,   # time.monotonic() lúc nhận ảnh, có thể bỏ qua khi xử lý ngay
        control=robot_control,
        draw=True,
    )
    # result.annotated_frame: ảnh BGR có box, đường giữa, tâm và độ lệch.
    # result.alignment: command, error_px, angular_velocity, v.v.
    return result

# Khi kết thúc/thoát vòng lặp:
# ai.stop(control=robot_control)
~~~

set_robot_velocity là tên minh họa, cần thay bằng hàm có thật trong project chính. Callback được gọi ngay trong luồng đang chạy process_frame/tick, không dùng socket hoặc thread điều khiển ngầm. Nếu controller yêu cầu cập nhật motor trong luồng mô phỏng chính, hãy gọi các hàm này tại luồng đó.

Nếu chỉ muốn AI trả dữ liệu rồi tự gọi hàm robot:

~~~python
result = ai.process_frame(frame_bgr, draw=True)
state = result.alignment
set_robot_velocity(state.linear_velocity, state.angular_velocity)
~~~

Khi đọc ảnh lỗi, dùng ai.process_frame(None, control=robot_control) để STOP ngay; khi chỉ chưa có ảnh mới, dùng ai.tick(control=robot_control) để kiểm tra timeout. Gọi ai.stop(control=robot_control) trong finally lúc thoát. Nếu process_frame báo lỗi ảnh/inference, nó gọi STOP trước khi ném lỗi; lỗi callback do controller xử lý.

captured_at phải dùng time.monotonic() trên cùng máy/quá trình, không dùng thời gian mô phỏng, datetime hoặc timestamp iPhone trực tiếp. Không xử lý lặp lại cùng frame như một ảnh mới; giữ thời điểm nhận ban đầu khi ảnh bị xếp hàng. Timeout chỉ có tác dụng khi vòng lặp robot tiếp tục gọi tick/process_frame.

## Quy ước

- Đường giữa: x = chiều rộng ảnh / 2.
- Tâm bảng: trung điểm bounding box class 11.
- error_px = tâm bảng - tâm ảnh: âm ở trái, dương ở phải.
- error_normalized = error_px / chiều rộng ảnh (toàn bộ chiều rộng).
- TURN_LEFT: angular_velocity dương; TURN_RIGHT: âm; STOP: 0.
- linear_velocity luôn 0.0 m/s.
- Camera phải hướng về trước, ảnh không bị mirror. Nếu ảnh bị lật ngang cần sửa ảnh hoặc ánh xạ chiều quay tương ứng.

Cấu hình mặc định hiện tại: biên ±15%, vùng dừng căn tâm ±10%. Ví dụ ảnh rộng 640: hai đường cam ở x = 224 px và 416 px, đường giữa ở x = 320 px. Bắt đầu yêu cầu căn khi tâm thực vượt một đường cam; kết thúc yêu cầu quay khi tâm thực về trong 64 px so với giữa ảnh. Khi đang STOP, vùng giữa hai ngưỡng không làm robot quay lại. Nếu tâm thực vào vùng dừng, dừng ngay để tránh quay vượt do bộ lọc còn giữ sai số cũ.

Dùng tâm chưa làm mượt để quyết định bắt đầu/dừng và chiều quay. EMA alpha 0.4 chỉ làm mượt độ lớn tốc độ quay, không trì hoãn lệnh lúc vượt ngưỡng. Tốc độ quay tỷ lệ với độ lệch, giới hạn 0.08 đến 0.6 rad/s. Khi tâm đổi sang phía đối diện, xóa độ trễ dấu của bộ lọc. Khi mất mục tiêu, ảnh cũ quá 0.5 giây hoặc frame trùng/sai thứ tự, trả STOP.

Khi có nhiều bảng, chọn bảng có confidence cao nhất lúc bắt đầu, sau đó ưu tiên bảng còn chồng lấp với vị trí trước. Đây là liên kết bounding box đơn giản, không phải bộ tracker nhận dạng danh tính; khi bảng mất/đổi cảnh có thể chọn lại.

Nếu robot vi sai cần vận tốc từng bánh, bộ điều khiển chuyển (v, w) thành:
- tốc độ góc bánh trái = (v - w * khoảng_cách_hai_bánh / 2) / bán_kính_bánh
- tốc độ góc bánh phải = (v + w * khoảng_cách_hai_bánh / 2) / bán_kính_bánh

Các kích thước tính bằng mét, tốc độ bánh rad/s. Kiểm tra chiều motor theo mô hình robot thực tế.

## Thay đổi cấu hình và export

Các tham số ở config.yaml/alignment. main.py và phone_camera.py đọc trực tiếp mỗi lần khởi động.

~~~powershell
cd G:\yolov8n
.\.venv\Scripts\python.exe -B export_onnx.py --force
~~~

Bản export giữ graph YOLO phát hiện 12 lớp; class target vẫn là 11. Không train lại. Ngưỡng căn tâm được ghi vào metadata ONNX, TargetAI tự đọc nếu không truyền cấu hình riêng. Vẽ ảnh, smoothing và gọi controller thực thi trong Python; chỉ chép ONNX sẽ không tự điều khiển robot.

Có thể ghi đè cấu hình khi khởi tạo:

~~~python
from target_alignment import AlignmentConfig
ai = TargetAI(
    weights="best.onnx",
    alignment=AlignmentConfig(start_threshold=0.15, stop_threshold=0.10),
)
~~~

## Xem thử trên YOLO hiện tại

~~~powershell
cd G:\yolov8n
.\.venv\Scripts\python.exe -B main.py --source 0
~~~

main.py tự vẽ đường giữa, tâm, đoạn nối và lệnh. Có --no-alignment để tắt overlay. Ảnh/video lưu bởi main.py cũng có overlay; dữ liệu gốc không bị sửa.

Với camera iPhone, chạy lại phone_camera.py theo CAMERA_IPHONE.md để nạp mã mới. Trang laptop hiển thị ảnh có đường giữa và trạng thái căn tâm; preview camera thô trên điện thoại vẫn là ảnh gốc. Server chỉ hiển thị/gợi ý lệnh, không tự điều khiển robot. Bộ điều khiển mô phỏng gọi TargetAI trên ảnh camera của nó.

## Xác minh

Đã kiểm tra hướng LEFT/RIGHT, vùng chết/hysteresis, giữ mục tiêu khi confidence thay đổi, mất mục tiêu, timeout và ảnh trùng. Đã đối chiếu đầu ra API ONNX với best.pt ở ảnh vuông/ngang/dọc và kiểm tra callback điều khiển bằng hàm giả, không kết nối motor. Model export qua onnx.checker và ONNX Runtime, giữ metadata lớp và ngưỡng căn tâm.

## Hai đường ngưỡng trực quan

Hai đường màu cam mặc định nằm tại 35% và 65% chiều rộng ảnh; đường giữa màu xanh ở 50%. Tọa độ được tính trên ảnh camera nguyên gốc, không phải ảnh letterbox 640 của model. Ví dụ ảnh 1280 px có đường trái 448, giữa 640 và phải 832.

Tâm nhỏ hơn ngưỡng trái: TURN_LEFT. Tâm lớn hơn ngưỡng phải: TURN_RIGHT. Chạm đúng đường chưa được coi là vượt. Khi đang quay, tiếp tục căn đến vùng dừng +/-10%; khi đang STOP, tâm nằm giữa hai đường không khởi động quay mới. Quyết định dựa trên tâm thực trên mỗi khung mới sau detect/NMS. Callback điều khiển được gọi trước bước vẽ ảnh.

ONNX kèm metadata target_alignment_policy=raw_center_hysteresis_v2. Logic mới và việc vẽ ba đường vẫn chạy trong target_alignment.py; khi đưa model sang project chính, cập nhật cả robot_ai.py và target_alignment.py cùng model. Không chỉ thay model rồi giữ mã căn tâm cũ.

Đã kiểm tra phản ứng ngay ở khung vượt ngưỡng dù smoothing alpha rất nhỏ, giữ hysteresis, đúng dấu quay, các đường vẽ đúng tỷ lệ ở nhiều kích thước, và STOP khi mất/stale ảnh.

## Điều khiển từ ứng dụng iPhone trong ESP32_IoT

`ai/service.py` truyền `AlignmentConfig()` rõ ràng (±15%/±10%), ghi đè metadata căn tâm cũ của ONNX. `ai/follower.py` quyết định chuyển động: giữ hướng trong hai line; vượt line thì dừng, chờ xác nhận STOPPED ít nhất 150 ms và ảnh mới rồi xoay tại chỗ. Khi căn đến vùng tâm, dừng quay, xác nhận 3 ảnh mới liên tiếp rồi tiến lại. Mất mục tiêu thì đứng yên chờ, không quay tìm. API TargetAI ở trên chỉ trả yêu cầu căn tâm; Follower thực hiện chu trình dừng/quay/tiến.

## Ổn định box và liên kết mục tiêu

TargetAI dùng confidence 0,25 để nhận mục tiêu mới, 0,15 để giữ một box khớp vị trí đã theo (IoU >=0,2; diện tích mới bằng 0,5–2 lần box cũ). Liên kết vị trí tồn tại tối đa 250 ms tính từ lần detect thật cuối cùng. Một ảnh mất detect vẫn trả found=False/STOP, không giả lập số đo để lái. Sau khi liên kết hết hạn, vật mới phải đạt ngưỡng nhận mới.

AlignmentResult bổ sung target_id, box_xyxy (box mới đo), display_box_xyxy (box làm mượt để vẽ). Chỉ vẽ box được chọn; chuyển động lớn cập nhật box ngay để tránh kéo bóng. Tâm và ngưỡng điều khiển vẫn dựa trên box mới đo. Follower xác nhận lại khi target_id thay đổi. ID là liên kết ngắn hạn theo vị trí, chưa bảo đảm danh tính của vật sau khi khuất hoặc đổi cảnh.
