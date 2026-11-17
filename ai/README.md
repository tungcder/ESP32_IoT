# Camera iPhone → laptop YOLOv8n → ESP32

Dùng Safari trên iPhone 13 để truyền video qua **WebRTC trong mạng LAN**.
Ảnh nhận từ iPhone được xoay phải 90° trước khi chạy YOLO và hiển thị laptop.
Hằng ngày: **quét QR → mở Safari → Bật camera trước → Cho phép**.
Không cần ứng dụng RTSP hoặc nhập URL luồng. Không thu âm.

**Lần đầu phải cài và tin cậy chứng chỉ HTTPS trên iPhone.** Safari chỉ cho web
truy cập camera trong ngữ cảnh an toàn; HTTP bằng IP laptop không đáp ứng yêu cầu.
Bỏ qua cảnh báo chứng chỉ không thay thế bước tin cậy.

Chế độ **Auto + AI** tự chạy và né vật cản khi chưa thấy mục tiêu, dừng xác nhận
3 ảnh mới rồi bám khi camera phát hiện mục tiêu. Mất mục tiêu thì dừng; sau
1,5 giây chưa thấy lại và camera vẫn tốt, xe trở về tự né vật cản. Mất camera
hoặc liên lạc thì kết thúc phiên, không tự chạy lại. Sau khi nạp firmware mới,
ghép camera và bấm **Bắt đầu Auto + AI** trên bảng laptop.
Xem [hướng dẫn Auto + AI](../docs/HYBRID_MODE.md).

Ba mode độc lập vẫn có quyền điều khiển riêng: Obstacle Auto chạy trên ESP32, Wi-Fi Manual
nhận lệnh từ web ESP32, AI chạy trên laptop. Chuyển mode sẽ dừng xe và thu hồi
phiên AI cũ. Hai mode cũ tiếp tục dùng được khi laptop tắt. Quét QR, bật camera
hoặc mở bảng AI **chưa làm xe chạy**; cần bấm Bắt đầu bám mục tiêu trên laptop.

## 1. Chuẩn bị laptop (một lần)

### Tìm địa chỉ nhanh khi đổi Wi-Fi

Trên **laptop đang chạy AI**, luôn mở **https://localhost:8090**. Địa chỉ này
không đổi theo Wi-Fi; có thể lưu dấu trang. `localhost` trên iPhone chỉ chính
iPhone, vì vậy iPhone phải dùng QR trong bảng AI.

Sau khi đổi mạng, dừng chương trình AI bằng **Ctrl+C** rồi chạy lại:

```powershell
.\ai\run.ps1
```

Chương trình tự nhận IPv4 của laptop, cập nhật địa chỉ và chứng chỉ HTTPS cho
mạng mới, rồi tạo QR đúng địa chỉ. Chứng chỉ gốc được giữ nguyên nên iPhone
đã tin cậy laptop này không cần cài lại chứng chỉ chỉ vì đổi Wi-Fi.
Nếu VPN hoặc nhiều adapter khiến nhận nhầm mạng, dùng
`.\ai\run.ps1 -LaptopIP IP-WiFi-laptop`.

Trong **Kết nối và hiệu chỉnh**, bấm **Tìm xe trong Wi-Fi**, chọn xe tìm được rồi
bấm **Lưu cấu hình**. Chương trình tìm tối đa 254 địa chỉ gần laptop trong mạng
nội bộ và chỉ đọc `/status`, không gửi lệnh lái. Phải dừng AI trước khi tìm xe.
Nếu có nhiều xe, chương trình hiển thị tất cả để bạn chọn, không tự đổi xe.

Cũng có thể tìm nhanh bằng PowerShell:

```powershell
.\ai\find.ps1
```

Xe cần bật nguồn, đã kết nối cùng mạng và dùng đúng SSID/mật khẩu trong
`include/config.h`. Nếu Wi-Fi chặn thiết bị liên lạc hoặc xe ở ngoài phần mạng
được tìm, lấy IP trong Serial Monitor rồi nhập trực tiếp.

Cho laptop, iPhone và ESP32 vào cùng mạng LAN. ESP32 dùng Wi-Fi 2,4 GHz;
iPhone/laptop có thể dùng 5 GHz nếu router cho các thiết bị liên lạc nhau.
Tránh Wi-Fi khách có client/AP isolation. Tắt VPN nếu QR chọn nhầm IP.

Cài Python 3.12 và PlatformIO nếu máy chưa có. Mở PowerShell:

```powershell
cd G:\ESP32_IoT
powershell -ExecutionPolicy Bypass -File .\ai\setup.ps1
```

Script tạo môi trường `ai/.venv`, cài requirements, tạo CA riêng và chứng chỉ
HTTPS cho IP LAN hiện tại. Không tự cài trust hay thay đổi tường lửa.
Nếu tự chọn sai IP, tìm IPv4 của adapter Wi-Fi trong `ipconfig` rồi chạy:

```powershell
powershell -ExecutionPolicy Bypass -File .\ai\setup.ps1 -LaptopIP 192.168.1.242
```

`192.168.1.242` chỉ là ví dụ: dùng IP Wi-Fi laptop thực tế.
Có thể truyền `-Python 'C:\duong-dan\python.exe'` khi cần tạo venv bằng Python khác.

### Tin cậy HTTPS trên Windows

Chạy lệnh sau **một lần trên chính laptop này**, sau khi script setup thành công:

```powershell
Import-Certificate -FilePath .\ai\.certs\iphone-root.cer -CertStoreLocation Cert:\CurrentUser\Root
```

Lệnh cài CA vào tài khoản Windows hiện tại. Hoặc mở file `.cer`, chọn Install
Certificate → Current User → Place all certificates in the following store →
Trusted Root Certification Authorities. Chỉ cài chứng chỉ do chính project trên
laptop của bạn tạo ra. Khi không dùng nữa có thể xóa CA tên
**ESP32 Robot Camera Local CA** trong `certmgr.msc`.

### Tường lửa

Đặt Wi-Fi tin cậy ở Windows thành **Private network**. Khi Windows hỏi quyền
Python, cho phép mạng Private cho `ai\.venv\Scripts\python.exe`.
Web dùng TCP **8090** (HTTPS), TCP **8091** (cài chứng chỉ); video WebRTC dùng
**UDP động** trực tiếp giữa iPhone và Python trên laptop.

Nếu không có hộp thoại hoặc có web nhưng không có video: mở Windows Defender
Firewall → Allow an app through firewall → Change settings → Allow another app,
thêm đúng Python của venv, bật Private. Nếu chính sách máy chặn UDP, cần rule
inbound cho chương trình Python đó, protocol UDP, scope Local subnet, profile
Private trong Advanced settings. Không cần mở cổng trên router hoặc tắt tường lửa.

## 2. Chạy server và cài iPhone (một lần)

```powershell
cd G:\ESP32_IoT
powershell -ExecutionPolicy Bypass -File .\ai\run.ps1
```

Giữ cửa sổ này mở. Server in ra URL HTTPS laptop và URL cài chứng chỉ.
Mở **https://localhost:8090** trên Chrome/Edge laptop sau khi đã cài CA Windows.
Trang phải mở không có cảnh báo chứng chỉ. Nếu browser đang mở trước khi cài CA,
đóng và mở lại browser.

Trên dashboard, mở **Cài đặt iPhone lần đầu → Mở QR và hướng dẫn cài HTTPS**:

1. Dùng Camera iPhone quét **QR cài đặt** (HTTP cổng 8091), mở bằng Safari.
2. Đối chiếu SHA-256 hiển thị với dashboard hoặc terminal laptop.
3. Bấm **Tải chứng chỉ công khai** và cho phép tải cấu hình nếu iOS hỏi.
4. Vào **Cài đặt → Đã tải về hồ sơ → Cài đặt**. Nếu không thấy, vào
   **Cài đặt chung → VPN & Quản lý thiết bị**, chọn chứng chỉ vừa tải và cài.
   Nhập mật mã iPhone khi được yêu cầu.
5. Vào **Cài đặt → Cài đặt chung → Giới thiệu → Cài đặt tin cậy chứng nhận**,
   bật **tin cậy hoàn toàn** cho **ESP32 Robot Camera Local CA**.
   Tên menu có thể thay đổi theo ngôn ngữ/phiên bản iOS.
6. Quay lại Safari. Dùng QR camera ở bước tiếp theo. Trang HTTPS cần mở được
   không có cảnh báo; nếu chưa được, kiểm tra lại trust và IP laptop.

Chỉ file chứng chỉ công khai `.cer` được tải về. HTTP 8091 chỉ cung cấp hướng dẫn
và chứng chỉ; không nhận camera hoặc điều khiển xe.
CA có quyền xác thực HTTPS trên các thiết bị đã cài: giữ kín `ai/.certs/ca-key.pem`
và `server-key.pem`, không gửi thư mục `.certs` cho người khác. Khi thôi dùng,
xóa cấu hình/chứng chỉ và tắt trust trên iPhone.

## 3. Kết nối camera hằng ngày

1. Chạy `ai/run.ps1`, mở **https://localhost:8090** trên laptop.
2. iPhone và laptop cùng Wi-Fi. Trong **Ghép nối iPhone**, quét QR camera bằng
   Camera iPhone rồi mở Safari. Không dùng browser nhúng của ứng dụng nhắn tin.
3. Bấm **Bật camera trước** → chọn **Cho phép** khi Safari hỏi quyền camera.
   Nếu iOS hỏi mạng cục bộ, cho phép ứng dụng liên quan truy cập LAN.
4. Trên iPhone phải có hình camera; thông báo **Laptop đã nhận … khung hình**
   phải tăng. Dashboard laptop hiển thị video và kết quả YOLOv8n.
5. Luồng gửi giới hạn 15 FPS, cạnh dài tối đa 640 px và bitrate mục tiêu tối đa
   500 kbit/s nếu Safari hỗ trợ; ưu tiên giữ nhịp hình khi mạng yếu. Laptop chờ
   ảnh AI mới qua HTTPS (mỗi lần tối đa 250 ms), chỉ một yêu cầu ảnh đang chạy,
   nhận xong chờ ngay ảnh tiếp theo; không tích hàng đợi ảnh cũ. Ảnh quá cũ bị bỏ.
   Hai đường biên và đường tâm được vẽ giống nhau trên cả ảnh YOLO và ảnh
   camera dự phòng, theo ngưỡng trong model. Web giải mã xong mới vẽ khung
   hình lên canvas; bỏ lỡ một ảnh không làm chớp tắt hình còn mới. Ảnh quá
   0,5 giây bị ẩn. Đường chỉ được vẽ lên bản sao hiển thị, không vào đầu vào YOLO.
   Khi model đã sẵn sàng, bỏ bước nén JPEG camera dự phòng; kết quả điều khiển
   được cập nhật trước khi nén ảnh hiển thị (JPEG chất lượng 70). OpenCV dùng
   một luồng để tránh tranh CPU với ONNX và giải mã WebRTC. AI được đánh thức
   ngay khi có ảnh mới, không đợi chu kỳ kiểm tra 10 ms. Mỗi bước lấy ảnh mới
   nhất và bỏ ảnh trung gian khi xử lý không kịp. Màn hình hiển thị tốc độ camera,
   AI và hiển thị thực tế; tuổi kết quả tính từ lúc laptop nhận, chưa gồm trễ
   chụp trên iPhone. Nhật ký chỉ truyền sự kiện mới và vẽ lại khi có thay đổi.
6. Giữ Safari ở trang camera, màn hình bật. Web yêu cầu giữ sáng nếu iOS hỗ trợ;
   nếu máy vẫn ngủ, chỉnh Tự động khóa phù hợp rồi khôi phục sau buổi thử.

QR có hiệu lực 10 phút và dùng cho một kết nối; server tự tạo mã tiếp theo khi
ghép nối thành công. Một lần chỉ nhận một camera. Muốn đổi máy, bấm **Ngắt camera**
trên laptop, rồi quét QR mới. Hết hạn thì bấm **Tạo QR mới**.
Nhấn Dừng camera, khóa màn hình, chuyển ứng dụng hoặc mất luồng sẽ dừng phiên AI;
kết nối lại không tự cho xe chạy tiếp. Gián đoạn ngắn không tự đóng camera:
server chờ tối đa 10 giây để có hình hợp lệ trở lại; timestamp được đồng bộ lại
sau khi luồng ổn định và ảnh tồn đọng bị loại. Lỗi tạm thời khi hỏi trạng thái
không tắt camera. Ngưỡng dừng phiên AI khi ảnh/kết quả quá 0,5 giây vẫn giữ nguyên.

## 4. Kết nối ESP32 và thử thực tế

Firmware phải hỗ trợ giao thức AI của project. Bản tích hợp AI trên nền code Tùng
nhận lệnh tiến 50% PWM và quay AI 64–70% PWM. Cần nạp lại firmware để ESP32
chấp nhận mức quay AI mới; Auto và nút quay Manual trên web dùng mức quay 80% PWM.
Tiến/lùi vẫn 50% PWM. Mức quay Auto đã thay đổi nên cần hiệu chỉnh lại thời gian
quay trái/phải trên xe thật để đạt góc mong muốn:

```powershell
pio run -e esp32dev
pio run -e esp32dev -t upload
pio device monitor -b 115200
```

Lấy IP ESP32 từ Serial Monitor hoặc router. Tại dashboard laptop, nhập
**Địa chỉ ESP32 hoặc Webots**, ví dụ `http://192.168.1.100`, bấm **Lưu cấu hình**.
Mặc định đang trỏ Webots `http://127.0.0.1:8081`; cần thay bằng IP xe thật.
Trình duyệt laptop chỉ gọi HTTPS laptop; Python gọi HTTP ESP32 trong LAN.
Từ web ESP32 cũng có thể chọn AI, điền `https://IP-laptop:8090` rồi mở bảng AI.
Nếu dùng firmware cũ chỉ có Auto/Manual (commit `6a65192`), hai nút Auto/Manual
trên bảng laptop vẫn gửi lệnh và đọc lại trạng thái xác nhận rồi mở web ESP32.
Firmware cũ không chạy AI; muốn bám mục tiêu phải nạp firmware hỗ trợ AI.
Khi không kết nối được xe, kiểm tra IP trong Serial Monitor, điền **Địa chỉ ESP32**
và bấm **Lưu cấu hình** trước khi chuyển mode. IP web laptop và IP ESP32 là hai địa chỉ khác nhau.

Thử theo thứ tự:

1. **Chỉ thử camera:** chưa bấm Bắt đầu. Quét QR, cho phép camera; di chuyển
   iPhone và kiểm tra hình laptop thay đổi theo. Kiểm tra log nhận hình,
   model sẵn sàng và ESP32 đã kết nối. Xe phải chưa chạy.
2. **Thử khi bánh nhấc khỏi sàn:** gắn chắc iPhone trên xe, camera trước hướng
   phía trước, HC-SR04 hướng trước. Đưa đúng vật lớp `target` model đã học
   vào hình, bấm **Bắt đầu bám mục tiêu**. Quan sát lệnh và chuyển động
   ESP32 xác nhận trong log; kiểm tra trái/phải đúng hướng trước khi chạy sàn.
3. **Dừng 20 cm:** thử chậm trên sàn thoáng, đưa vật phía trước gần cảm biến.
   Xe dừng tiến khi sonar <=20 cm, chỉ tiến lại khi >25 cm. Đối chiếu số đo
   dashboard với thước, điều chỉnh tốc độ nếu cần.
4. **Vùng cho phép và căn tâm:** khi tâm mục tiêu còn trong hai line 35–65%, xe
   giữ hướng tiến. Đưa tâm vượt line trái/phải: xe dừng, chờ xác nhận STOPPED
   ít nhất 150 ms và ảnh mới, rồi xoay tại chỗ. Xe tiếp tục căn ngay cả khi tâm
   đã vào lại vùng cho phép; đến 40–60% thì dừng quay, xác nhận 3 ảnh mới rồi tiến.
5. **Mất mục tiêu:** giữ camera vẫn gửi hình, đưa vật ra hẳn khung hình.
   Xe đứng yên chờ, không quay tìm và không tự kết thúc theo thời gian.
   Đưa vật lại: xác nhận 3 ảnh mới rồi đánh giá vị trí để tiếp tục.
6. **Mất camera:** khi đang chạy thử với bánh nhấc, bấm Dừng camera hoặc khóa
   iPhone. Phiên AI phải dừng do mất hình, không chuyển sang quay tìm.
7. **Đổi mode:** chuyển Manual hoặc Auto; phiên AI cũ bị thu hồi. Xác minh
   hai mode cũ vẫn điều khiển được. Dùng **Dừng khẩn cấp** khi cần dừng mọi
   mode và đưa xe về Manual.

Mô phỏng Webots hỗ trợ cùng API để thử điều khiển với camera iPhone thật;
không thay thế thử cảm biến, mạch và động cơ thực tế.

## Hành vi và giới hạn

- Model `yolov8n/best.onnx`, lớp `target` ID 11; nạp một lần bằng ONNX Runtime,
  mặc định CPU. Không nhận diện mọi đồ vật thành mục tiêu: dùng đúng lớp đã train.
- Khóa qua 3 ảnh mới ổn định. Khi tâm nằm trong hai line tại 35% và 65%
  chiều rộng ảnh (kể cả chạm biên), tiến thẳng 50% PWM, không chỉnh hướng.
- Vượt biên: gửi STOPPED, chờ xe xác nhận dừng ít nhất 150 ms và lấy ảnh mới
  rồi xoay tại chỗ. Quay tối đa 70% PWM, giảm dần về 64% khi đến gần vùng dừng căn giữa. Căn liên tục
  đến vùng 40–60%, dừng quay và xác nhận 3 ảnh mới liên tiếp trước khi tiến lại.
  Đổi chiều quay cũng qua bước dừng. Không tự lùi.
- Cấu hình chạy của ứng dụng là `AlignmentConfig` (±15%/±10%), dùng chung cho
  đường vẽ và Follower, ghi đè metadata căn tâm cũ trong ONNX; không cần train lại.
- Ổn định detect: mục tiêu mới cần confidence >=0,25; mục tiêu đang theo có
  thể giữ ở >=0,15 khi box vẫn khớp vị trí (IoU >=0,2, tỷ lệ diện tích 0,5–2).
  Lưu liên kết tối đa 250 ms sau lần thấy cuối để tránh nhảy sang vật khác.
  Mỗi mục tiêu có ID tạm; đổi ID phải xác nhận lại qua 3 ảnh mới.
- Chỉ vẽ box của mục tiêu được chọn; làm mượt riêng box hiển thị. Điểm tâm
  và quyết định vượt line vẫn lấy số đo mới chưa làm mượt. Khi mất detect,
  found=False và xe dừng ngay, không dùng box cũ để tiếp tục lái.
- Khi model sẵn sàng, màn hình chỉ lấy ảnh đã xử lý YOLO (tuổi ảnh <=500 ms),
  không xen ảnh camera thô làm box nhấp nháy hoặc ID ảnh vượt trước inference.
- HC-SR04 ở 90° trong AI; dừng tiến <=20 cm, nhả giữ khi >25 cm. Khi được phép tiến, luôn dùng 50% PWM.
  Số đo sai thì dừng tiến. Ngưỡng và thuật toán Auto được giữ riêng.
- Không thấy mục tiêu trên ảnh mới: dừng tại chỗ và chờ mục tiêu xuất hiện.
  Xác nhận lại qua 3 ảnh mới rồi tiếp tục. Không tự quay tìm, không có bộ đếm
  một vòng hoặc chờ 5 giây. Mất luồng camera vẫn kết thúc phiên như dưới đây.
- Khi sonar không có Echo (0 cm) hoặc đo ngoài 2–400 cm, AI vào SENSOR_HOLD
  và không tiến. PWM đi thẳng vẫn là 50%; tăng PWM quay không bỏ chặn cảm biến.
  Có số đo hợp lệ trở lại thì tiếp tục, theo ngưỡng dừng 20 cm/nhả giữ >25 cm.
- Không có ảnh/kết quả AI mới trong 0,5 giây: kết thúc phiên do lỗi, không tìm.
  ESP32 cũng hủy phiên sau 500 ms không có lệnh hợp lệ. Không tự tiếp tục phiên cũ.

20 cm là ngưỡng sonar, không bảo đảm khoảng cách dừng vật lý chính xác 20 cm vì
quán tính và trễ. Sonar đo vật phía trước gần nhất, chưa xác minh vật đó chính là
mục tiêu YOLO; không bao phủ hai bên xe khi quay. Khóa lại theo vị trí/lớp, chưa có
nhận dạng danh tính: có thể khóa vật `target` khác nếu có nhiều vật cùng loại.

Luồng giữ ảnh mới nhất và kiểm tra timestamp/PTS để loại ảnh tồn đọng, kết quả
quá hạn không dùng lái xe. Độ trễ chụp thật trên iPhone vẫn cần đo thực tế.

## Khi không kết nối được

| Hiện tượng | Kiểm tra |
| --- | --- |
| QR không mở được | Server còn chạy; IP Wi-Fi laptop đúng; cùng LAN; TCP 8090/8091 được phép; không có client isolation/VPN |
| Safari báo chứng chỉ | Đã cài cấu hình và bật full trust; IP trong QR khớp SAN chứng chỉ; ngày giờ hai máy đúng; không bỏ qua cảnh báo |
| Không hỏi quyền camera | Dùng Safari, trang HTTPS tin cậy; menu trang → Cài đặt trang web → Camera → Cho phép |
| Có hình iPhone nhưng laptop chưa nhận | Cho phép Python venv qua firewall Private, đặc biệt UDP; tắt VPN; không dùng Wi-Fi khách |
| Đã có camera kết nối | Dừng/ngắt camera cũ trên laptop, chờ đóng rồi quét mã mới |
| Quét lại mã cũ bị từ chối | Tạo/quét QR mới; mã dùng một lần và hết hạn sau 10 phút |
| Có video nhưng không bám | Đúng vật `target`, đủ sáng; đã lưu IP ESP32; model sẵn sàng; bấm Bắt đầu |
| AI nhận mục tiêu nhưng không tiến, báo Lỗi cảm biến | Khi phiên AI đang bật, xem Serial `[AI sonar]`. Nếu `no_echo`/0 cm: kiểm tra nguồn HC-SR04, GND chung, TRIG GPIO16, ECHO GPIO17 qua chia áp về 3,3 V, servo hướng trước, vật phẳng ở 30–50 cm. Không bỏ chặn số đo lỗi để ép xe tiến |
| AI dừng vì quá chậm | Kiểm tra Wi-Fi/CPU, đóng tác vụ nặng; theo dõi tuổi ảnh và thời gian inference; tuổi ảnh trên web tính từ lúc laptop nhận, không đo đủ trễ chụp → hiển thị |
| AI kết thúc vì `URLError` / `TimeoutError` | Xem nguyên nhân và thời gian trong log: `timed out` là hết thời gian chờ kết nối/phản hồi HTTP (socket mặc định 300 ms). Thử `ping -n 20 IP-ESP32` khi xe đứng yên; nếu mất gói hoặc trễ cao, kiểm tra Wi-Fi, vị trí router và nguồn xe. Nếu chỉ lỗi khi động cơ chạy, kiểm tra nguồn và nhiễu động cơ. Không tăng watchdog để che lỗi mạng |
| Log báo HTTP 409, phiên hết hạn | ESP32 đã từ chối phiên/lệnh: có thể đã quá 500 ms không nhận lệnh hợp lệ hoặc đã đổi mode. Kiểm tra các lỗi mạng trước đó; phiên cũ không tự chạy lại. Khắc phục kết nối rồi chủ động bấm Bắt đầu |
| Auto/Manual từ dashboard mở lỗi | Kiểm tra địa chỉ HTTP ESP32 trong cấu hình và LAN; có thể mở web ESP32 trực tiếp |

**Khi laptop đổi IP/mạng:** dừng server (Ctrl+C), chạy lại setup với `-LaptopIP`
đúng rồi chạy server lại. Giữ nguyên `.certs`: CA được giữ, chỉ cấp lại chứng chỉ
server nên iPhone không cần cài CA lại. Chứng chỉ server có hạn 365 ngày; chạy lại
setup để gia hạn. CA có hạn 10 năm. Nếu xóa/mất CA, phải cài CA mới ở hai thiết bị.
Có thể đặt DHCP reservation cho laptop trên router để IP ổn định.
Nếu đổi cổng, truyền cùng `-Port` cho setup và run; cổng cài đặt = cổng HTTPS + 1.

## Cấu trúc và dữ liệu

- `ai/setup.ps1`, `ai/https_setup.py`: môi trường Python và HTTPS LAN.
- `ai/server.py`: HTTPS dashboard/signaling, HTTP chỉ để tải CA công khai.
- `ai/webrtc.py`: một camera WebRTC, direct LAN ICE, không dùng STUN/TURN ngoài.
- `ai/service.py`: nhận ảnh mới nhất, inference, vòng điều khiển và log độc lập.
- `ai/follower.py`: chu trình giữ hướng/dừng/căn tâm/chờ mục tiêu; `ai/robot_client.py`: API xe.
- `ai/web/`: dashboard laptop, trang camera Safari, hướng dẫn cài iPhone.
- `ai/config.local.json`, `ai/.certs/`, `ai/.venv/`, `ai/logs/`: dữ liệu cục bộ,
  được bỏ qua Git. Không đưa khóa CA/server lên repository.
- Log `.jsonl` theo lần chạy, 500 sự kiện gần nhất trên web. Tải log lấy toàn bộ
  lần chạy; Xóa hiển thị chỉ ẩn trên trình duyệt. Không lưu video lên đĩa.
- QR chỉ cấp phiên gửi camera. Trang điều khiển dành cho LAN tin cậy, chưa thiết
  kế công khai Internet; không port-forward server ra Internet.

ESP32 dùng `mode_epoch` và session để chặn lệnh cũ sau khi đổi mode:

| API ESP32 | Dữ liệu |
| --- | --- |
| GET `/status` | Mode, epoch, boot ID, chuyển động, khoảng cách AI, log |
| GET `/driveauto`, `/drivemanual` | Header `X-Mode-Epoch` hiện tại |
| POST `/ai/claim` | Header epoch; nhận session ngẫu nhiên, một chủ AI |
| POST `/ai/command` | Form session, seq tăng dần, movement FORWARD/LEFT/RIGHT/STOPPED, speed 0–70 khi quay (AI dùng 64–70), 0–50 khi tiến/dừng |
| POST `/ai/release` | Hủy đúng session, không dừng mode khác |
| POST `/estop` | Dừng tất cả, thu hồi AI, về Manual |

Giao diện ESP32 đã gửi epoch tự động. `src/ai_control.cpp` giữ watchdog và chặn
động cơ theo sonar ngay trên xe, độc lập kết nối camera/laptop.

## Áp dụng bản cập nhật

Sau khi cập nhật code, dừng server cũ bằng Ctrl+C rồi chạy lại `ai/run.ps1`.
Tải lại trang laptop và quét QR mới trên iPhone (đóng trang camera cũ), để cả
server lẫn Safari dùng cấu hình truyền hình mới. Không cần nạp lại ESP32 cho
những thay đổi truyền hình này. Tối ưu này không thay thế việc khắc phục mất
gói Wi-Fi; watchdog ảnh/lệnh 500 ms và yêu cầu chủ động bắt đầu lại vẫn giữ nguyên.
