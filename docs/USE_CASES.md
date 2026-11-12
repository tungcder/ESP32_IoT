# Đặc tả 10 use case của hệ thống xe robot ESP32 IoT

Nội dung dựa trên chức năng và cấu hình hiện tại của project: điều khiển thủ công qua Wi-Fi, tự tránh vật cản và bám mục tiêu bằng camera iPhone kết hợp YOLOv8n trên laptop. Các mức phần trăm tốc độ bên dưới là mức điều khiển động cơ bằng PWM, không phải vận tốc đo được của xe.

## UC01: Kết nối và thiết lập giao diện điều khiển

**Tác nhân:** Người sử dụng.

**Tiền điều kiện:** Xe được cấp nguồn; thông tin Wi-Fi trên ESP32 đã được cấu hình đúng; mạng hỗ trợ kết nối 2,4 GHz cho ESP32. Thiết bị điều khiển và xe có thể liên lạc trong cùng mạng LAN.

**Thao tác của tác nhân:** Khởi động xe, lấy địa chỉ IP của ESP32 rồi mở địa chỉ đó trên trình duyệt. Khi sử dụng AI, mở bảng điều khiển AI trên laptop, nhập địa chỉ ESP32 và nhấn **Lưu cấu hình**.

**Luồng xử lý của hệ thống:**

1. Khởi tạo động cơ, đèn, cảm biến siêu âm và servo; đưa xe về chế độ **Wi-Fi Manual**, động cơ dừng.
2. ESP32 kết nối Wi-Fi và cung cấp giao diện điều khiển tại địa chỉ IP của xe.
3. Giao diện lấy trạng thái hiện tại và hiển thị chế độ lái, trạng thái chuyển động, tình trạng kết nối.
4. Nếu người dùng cấu hình bảng AI, hệ thống kiểm tra định dạng địa chỉ, lưu cấu hình và đọc trạng thái từ ESP32.
5. Nếu chưa kết nối được, hệ thống hiển thị lỗi để người dùng kiểm tra địa chỉ IP, nguồn xe và mạng. Nếu AI đang hoạt động, hệ thống yêu cầu dừng AI trước khi thay đổi cấu hình.

**Kết quả và hậu điều kiện:** Người dùng truy cập được giao diện và xem trạng thái xe. Việc mở giao diện hoặc lưu cấu hình không tự khởi động chức năng bám mục tiêu.

## UC02: Điều khiển xe thủ công qua Wi-Fi

**Tác nhân:** Người sử dụng.

**Tiền điều kiện:** Giao diện đã kết nối ESP32; xe ở chế độ **Wi-Fi Manual**.

**Thao tác của tác nhân:** Nhấn giữ nút Tiến, Lùi, Trái, Phải hoặc phím mũi tên tương ứng; thả nút hoặc nhấn **Dừng** để dừng xe.

**Luồng xử lý của hệ thống:**

1. Giao diện gửi lệnh theo hướng người dùng chọn; khi giữ nút, lệnh được gửi lặp lại mỗi 250 ms.
2. ESP32 kiểm tra chế độ điều khiển và tính hợp lệ của lệnh trước khi thực hiện.
3. Xe tiến hoặc lùi với mức PWM 50%; quay trái hoặc phải với mức PWM 50% theo cấu hình hiện tại.
4. Khi người dùng thả nút, nhấn Dừng hoặc rời cửa sổ điều khiển trong lúc giữ nút, giao diện gửi lệnh dừng.
5. Nếu xe đang di chuyển mà không nhận thêm lệnh trong hơn 500 ms, ESP32 tự dừng động cơ và ghi nhật ký.

**Kết quả và hậu điều kiện:** Xe thực hiện hướng di chuyển đã chọn, dừng khi kết thúc thao tác hoặc hết thời gian nhận lệnh và tiếp tục ở chế độ Manual.

## UC03: Tự động di chuyển và tránh vật cản

**Tác nhân:** Người sử dụng.

**Tiền điều kiện:** Xe hoạt động bình thường; cảm biến HC-SR04 và servo đã được lắp đặt, hiệu chỉnh; người dùng truy cập được giao diện điều khiển.

**Thao tác của tác nhân:** Chọn **Obstacle Auto** để xe tự di chuyển và tránh vật cản.

**Luồng xử lý của hệ thống:**

1. Dừng chuyển động hiện tại, thu hồi phiên AI nếu có, đưa cảm biến về hướng trước ở góc 90° và chuyển sang Auto.
2. Đo khoảng cách phía trước. Nếu số đo hợp lệ và lớn hơn 40 cm, xe tiến.
3. Nếu khoảng cách nhỏ hơn hoặc bằng 40 cm, hoặc không có số đo hợp lệ, xe lùi một đoạn ước tính 8 cm rồi dừng để quét.
4. Quét bên trái tại 135° và 180°. Nếu cả hai số đo đều hợp lệ và lớn hơn 40 cm, xe quay trái xấp xỉ 90° theo thời gian đã hiệu chỉnh.
5. Nếu bên trái chưa thông thoáng, quét bên phải tại 45° và 0°. Nếu cả hai vị trí đều thông thoáng, xe quay phải xấp xỉ 90°.
6. Nếu hai bên đều chưa thông thoáng, xe tiếp tục lùi một đoạn ước tính 12 cm và quét lại. Sau khi quay, xe kiểm tra phía trước và tiếp tục chu trình.

**Kết quả và hậu điều kiện:** Xe hoạt động theo chu trình tự tránh vật cản cho đến khi người dùng đổi chế độ hoặc dừng khẩn cấp. Quãng đường lùi và góc quay được ước tính theo thời gian chạy động cơ.

## UC04: Ghép nối camera iPhone với hệ thống AI

**Tác nhân:** Người sử dụng.

**Tiền điều kiện:** Dịch vụ AI trên laptop đang chạy; iPhone và laptop liên lạc được trong cùng mạng LAN; iPhone đã cài và tin cậy chứng chỉ HTTPS của hệ thống; chưa có camera khác đang kết nối.

**Thao tác của tác nhân:** Quét QR camera trên bảng AI, mở bằng Safari, nhấn **Bật camera trước** và cho phép truy cập camera.

**Luồng xử lý của hệ thống:**

1. Cung cấp mã ghép nối có hiệu lực 10 phút, dùng cho một kết nối.
2. Kiểm tra mã ghép nối và tình trạng camera hiện tại trước khi chấp nhận kết nối.
3. Thiết lập đường truyền WebRTC để nhận video từ camera trước của iPhone.
4. Nhận các khung hình mới, xoay ảnh phù hợp và chuyển cho mô hình YOLOv8n xử lý; hiển thị hình ảnh cùng kết quả nhận diện trên laptop.
5. Sau khi ghép nối thành công, tạo mã tiếp theo. Nếu mã hết hạn hoặc đã sử dụng, người dùng tạo và quét QR mới; muốn đổi camera, người dùng ngắt camera hiện tại trước.

**Kết quả và hậu điều kiện:** Laptop nhận được hình camera iPhone để quan sát và nhận diện. Việc ghép camera chưa kích hoạt phiên AI điều khiển xe.

## UC05: Bắt đầu bám mục tiêu bằng AI

**Tác nhân:** Người sử dụng.

**Tiền điều kiện:** Bảng AI kết nối được ESP32; firmware hỗ trợ AI; mô hình YOLOv8n đã sẵn sàng; camera cung cấp ảnh và kết quả xử lý mới trong giới hạn 0,5 giây; chưa có phiên AI đang hoạt động.

**Thao tác của tác nhân:** Đưa vật thuộc lớp **target** đã được huấn luyện vào hình camera và nhấn **Bắt đầu bám mục tiêu**.

**Luồng xử lý của hệ thống:**

1. Kiểm tra mô hình, độ mới của hình ảnh và trạng thái ESP32; từ chối bắt đầu nếu điều kiện chưa đáp ứng.
2. Yêu cầu quyền điều khiển AI, dừng chuyển động trước đó và chờ ESP32 xác nhận trạng thái dừng.
3. Nhận diện và xác nhận mục tiêu ổn định qua 3 khung hình mới. Nếu chưa thấy mục tiêu, xe đứng yên chờ.
4. Khi tâm mục tiêu nằm trong vùng 35–65% chiều rộng ảnh và điều kiện khoảng cách cho phép, xe tiến thẳng với PWM 50%.
5. Khi mục tiêu lệch khỏi vùng cho phép, khoảng cách không phù hợp hoặc mất mục tiêu, hệ thống xử lý theo UC06, UC07 hoặc UC08.
6. Nếu ESP32 không nhận lệnh AI hợp lệ trong hơn 500 ms, xe tự dừng và thu hồi phiên; lệnh đến muộn không khôi phục được phiên cũ.
7. Khi người dùng nhấn **Dừng AI**, hệ thống kết thúc phiên, yêu cầu xe dừng và thu hồi quyền điều khiển AI.

**Kết quả và hậu điều kiện:** Phiên AI điều khiển xe theo vị trí mục tiêu và khoảng cách phía trước. Sau khi dừng AI, muốn bám lại phải nhấn Bắt đầu lần nữa.

## UC06: Tự căn hướng khi mục tiêu lệch khỏi vùng cho phép

**Tác nhân:** Người sử dụng, thông qua mục tiêu đang được xe bám.

**Tiền điều kiện:** Phiên AI đang hoạt động; mục tiêu đã được xác nhận; ảnh còn mới và khoảng cách phía trước cho phép di chuyển.

**Thao tác của tác nhân:** Dịch chuyển mục tiêu sang trái hoặc phải làm tâm mục tiêu vượt khỏi hai đường biên trên hình camera.

**Luồng xử lý của hệ thống:**

1. Phát hiện tâm mục tiêu nằm ngoài vùng 35–65% chiều rộng ảnh.
2. Gửi lệnh dừng; chờ ESP32 xác nhận xe đã dừng ít nhất 150 ms và có thêm khung hình mới trước khi quay.
3. Cho xe xoay tại chỗ về phía mục tiêu: lệch trái thì quay trái, lệch phải thì quay phải.
4. Điều chỉnh PWM quay trong khoảng 40–50%, giảm dần khi mục tiêu tiến gần vùng giữa.
5. Tiếp tục căn đến khi tâm mục tiêu vào vùng 40–60%; dừng quay và xác nhận vị trí này qua 3 khung hình mới liên tiếp.
6. Sau khi xác nhận, đánh giá lại điều kiện rồi tiếp tục tiến. Nếu cần đổi chiều quay, xe thực hiện bước dừng trước khi đổi chiều.

**Kết quả và hậu điều kiện:** Xe căn hướng về mục tiêu rồi trở lại bám thẳng khi các điều kiện cho phép; không vừa tiến vừa quay trong bước căn tâm.

## UC07: Giữ khoảng cách phía trước trong chế độ AI

**Tác nhân:** Người sử dụng, thông qua phiên bám mục tiêu đang hoạt động.

**Tiền điều kiện:** Xe ở chế độ AI; cảm biến siêu âm hướng trước ở góc 90°; hệ thống đang theo dõi mục tiêu.

**Thao tác của tác nhân:** Cho xe bám mục tiêu; mục tiêu hoặc một vật cản phía trước tiến vào vùng gần xe.

**Luồng xử lý của hệ thống:**

1. Liên tục cập nhật khoảng cách phía trước từ cảm biến siêu âm.
2. Khi khoảng cách nhỏ hơn hoặc bằng 20 cm, hệ thống dừng xe và chuyển sang trạng thái giữ khoảng cách.
3. Nếu khoảng cách tăng nhưng chưa lớn hơn 25 cm, xe tiếp tục đứng yên để tránh chạy–dừng liên tục quanh ngưỡng.
4. Khi khoảng cách lớn hơn 25 cm, hệ thống đánh giá lại vị trí mục tiêu để tiếp tục bám hoặc căn hướng.
5. Nếu không có Echo hoặc số đo ngoài khoảng hợp lệ 2–400 cm, hệ thống dừng chờ cảm biến. Chỉ xem xét di chuyển tiếp khi số đo hợp lệ trở lại và thỏa điều kiện khoảng cách.

**Kết quả và hậu điều kiện:** Xe tạm dừng theo số đo phía trước; phiên AI vẫn hoạt động và có thể tiếp tục khi đủ điều kiện. Xe không tự lùi để tăng khoảng cách trong chế độ AI. Số đo này thuộc vật gần nhất phía trước, chưa xác định đó có phải mục tiêu được nhận diện hay không.

## UC08: Chờ và bám lại khi mất mục tiêu

**Tác nhân:** Người sử dụng.

**Tiền điều kiện:** Phiên AI đang hoạt động; camera vẫn cung cấp khung hình mới; mục tiêu đang được xe bám.

**Thao tác của tác nhân:** Đưa mục tiêu ra khỏi khung hình hoặc để mục tiêu bị che khuất, sau đó đưa mục tiêu xuất hiện trở lại.

**Luồng xử lý của hệ thống:**

1. Phát hiện không còn nhận diện được mục tiêu trên ảnh mới và gửi lệnh dừng xe.
2. Chuyển sang trạng thái mất mục tiêu; tiếp tục xử lý ảnh để chờ mục tiêu xuất hiện, không tự quay tìm và không dùng vị trí cũ để lái.
3. Khi mục tiêu xuất hiện trở lại, xác nhận ổn định qua 3 khung hình mới.
4. Kiểm tra khoảng cách và vị trí mục tiêu để tiếp tục tiến hoặc căn hướng.
5. Nếu camera vẫn có ảnh mới nhưng chưa thấy mục tiêu, xe tiếp tục đứng yên chờ. Nếu ảnh hoặc kết quả AI quá 0,5 giây, hệ thống kết thúc phiên do lỗi; kết nối lại không tự khởi động phiên cũ.

**Kết quả và hậu điều kiện:** Xe có thể bám lại sau khi xác nhận mục tiêu xuất hiện trở lại. Nếu phiên đã kết thúc vì mất hình, người dùng phải nhấn Bắt đầu để chạy lại. Khi có nhiều vật cùng lớp target, hệ thống chưa bảo đảm nhận đúng danh tính vật ban đầu.

## UC09: Dừng khẩn cấp và thu hồi quyền điều khiển

**Tác nhân:** Người sử dụng.

**Tiền điều kiện:** Xe đã được cấp nguồn; giao diện còn gửi được yêu cầu đến ESP32. Xe có thể đang ở Manual, Auto hoặc AI.

**Thao tác của tác nhân:** Nhấn **Dừng khẩn cấp** trên bảng AI hoặc **DỪNG KHẨN CẤP · MỌI MODE** trên giao diện ESP32.

**Luồng xử lý của hệ thống:**

1. Gửi yêu cầu dừng khẩn cấp đến ESP32.
2. Khi nhận yêu cầu, ESP32 dừng động cơ và thu hồi phiên AI hiện tại nếu có.
3. Chuyển xe về **Wi-Fi Manual**, đưa servo về góc 90°.
4. Vô hiệu hóa quyền điều khiển của phiên AI cũ và các lệnh dùng trạng thái chế độ đã lỗi thời.
5. Trả kết quả xác nhận và ghi sự kiện dừng khẩn cấp. Nếu không nhận được xác nhận, giao diện báo lỗi thay vì kết luận xe đã dừng.

**Kết quả và hậu điều kiện:** Sau khi ESP32 xác nhận, xe dừng ở chế độ Manual; phiên AI cũ mất quyền điều khiển. Muốn xe chạy tiếp, người dùng phải chủ động gửi lệnh hoặc kích hoạt chế độ mong muốn.

## UC10: Theo dõi trạng thái và xem nhật ký hoạt động

**Tác nhân:** Người sử dụng.

**Tiền điều kiện:** Người dùng mở được giao diện ESP32 hoặc bảng AI; dịch vụ tương ứng đang hoạt động.

**Thao tác của tác nhân:** Quan sát trạng thái, xem nhật ký; nhấn **Xóa hiển thị** khi cần làm gọn màn hình hoặc **Tải log** trên bảng AI để lưu nhật ký.

**Luồng xử lý của hệ thống:**

1. Định kỳ lấy và hiển thị chế độ lái, trạng thái chuyển động và tình trạng kết nối của xe.
2. Trên bảng AI, bổ sung trạng thái camera, mô hình, hành vi bám mục tiêu, khoảng cách phía trước và chuyển động ESP32 đã xác nhận.
3. Hiển thị các sự kiện như chuyển chế độ, tránh vật cản, căn hướng, mất mục tiêu và dừng do lỗi.
4. Khi người dùng nhấn Xóa hiển thị, ẩn các sự kiện đã xem trên trình duyệt; nhật ký AI đã lưu vẫn được giữ.
5. Khi người dùng nhấn Tải log trên bảng AI, cung cấp tệp JSONL chứa nhật ký của toàn bộ lần chạy dịch vụ hiện tại.
6. Nếu mất kết nối, cập nhật tình trạng lỗi để người dùng biết dữ liệu không còn được xác nhận mới.

**Kết quả và hậu điều kiện:** Người dùng theo dõi được hoạt động và nguyên nhân thay đổi hành vi của xe, đồng thời tải được nhật ký AI để kiểm tra. Thao tác xem, ẩn hoặc tải nhật ký không làm thay đổi chuyển động của xe.
