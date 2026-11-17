# Đặc tả use case phần AI của xe robot ESP32 IoT

Nội dung mô tả các chức năng hiện có trong project. Camera iPhone cung cấp hình ảnh, laptop chạy YOLOv8n để nhận diện mục tiêu và ESP32 điều khiển xe. Các tỷ lệ PWM bên dưới là mức điều khiển động cơ, không phải vận tốc đo được.

## UC_AI01: Nhận diện và bám mục tiêu bằng AI

**Tác nhân:** Người sử dụng.

**Tiền điều kiện:** Xe, laptop và iPhone liên lạc được trong cùng mạng LAN; camera iPhone đã ghép nối và đang truyền hình; mô hình YOLOv8n sẵn sàng; bảng điều khiển AI kết nối được ESP32 có firmware hỗ trợ AI; chưa có phiên AI hoạt động. Ảnh và kết quả AI còn mới trong giới hạn 0,5 giây.

**Thao tác của tác nhân:** Đưa vật thuộc lớp **target** đã được huấn luyện vào hình camera, nhấn **Chỉ bám mục tiêu** trên bảng điều khiển laptop.

**Luồng xử lý của hệ thống:**

1. Kiểm tra mô hình, độ mới của hình ảnh và khả năng kết nối xe. Nếu chưa đáp ứng, thông báo nguyên nhân và từ chối bắt đầu.
2. Thiết lập phiên điều khiển AI, dừng chuyển động trước đó và chờ ESP32 xác nhận xe đã dừng.
3. Xử lý các khung hình mới bằng YOLOv8n, xác định vị trí mục tiêu và hiển thị khung nhận diện trên laptop.
4. Xác nhận mục tiêu ổn định qua **3 khung hình mới** trước khi cho phép bám. Nếu chưa phát hiện được mục tiêu, xe đứng yên chờ.
5. Khi tâm mục tiêu nằm trong vùng **35–65% chiều rộng ảnh** và khoảng cách phía trước cho phép, xe tiến thẳng với **lệnh PWM 45%** (động cơ trái **45%**, phải **50%**). Nếu tâm vượt vùng này, thực hiện căn hướng theo UC_AI02; nếu khoảng cách không phù hợp, xử lý theo UC_AI03.
6. Nếu mất nhận diện nhưng camera vẫn có ảnh mới, xe dừng tại chỗ và chờ; khi mục tiêu xuất hiện lại, xác nhận qua 3 ảnh mới trước khi tiếp tục.
7. Khi người dùng nhấn **Dừng Auto + AI / AI**, hệ thống yêu cầu xe dừng và kết thúc quyền điều khiển của phiên hiện tại.

**Kết quả và hậu điều kiện:** Xe bám theo vị trí mục tiêu khi đủ điều kiện nhận diện và khoảng cách. Trong chế độ chỉ bám, xe đứng yên khi chưa thấy hoặc mất mục tiêu. Sau khi kết thúc phiên, người dùng phải chủ động nhấn bắt đầu để bám lại.

## UC_AI02: Tự căn hướng khi mục tiêu lệch khỏi vùng cho phép

**Tác nhân:** Người sử dụng.

**Tiền điều kiện:** Phiên AI đang bám mục tiêu, hoặc Auto + AI đang ở giai đoạn bám; mục tiêu đã được xác nhận; camera và kết quả xử lý còn mới; số đo khoảng cách hợp lệ và không bị giữ dừng do khoảng cách.

**Thao tác của tác nhân:** Dịch chuyển mục tiêu sang trái hoặc phải để tâm mục tiêu vượt khỏi hai đường biên trên hình camera.

**Luồng xử lý của hệ thống:**

1. Phát hiện tâm mục tiêu nằm ngoài vùng **35–65% chiều rộng ảnh**, chuyển sang bước dừng trước khi căn hướng.
2. Gửi lệnh dừng, chờ ESP32 xác nhận xe dừng ít nhất **150 ms** và nhận thêm một khung hình mới trước khi xoay.
3. Cho xe xoay tại chỗ về phía mục tiêu: mục tiêu lệch trái thì quay trái, lệch phải thì quay phải.
4. Điều chỉnh lệnh quay trong khoảng **58–62% PWM**, giảm dần khi tâm mục tiêu tiến gần vùng giữa. Sau bù lệch, động cơ trái chạy **53–57% PWM**, động cơ phải **58–62% PWM**.
5. Khi tâm mục tiêu vào vùng **40–60% chiều rộng ảnh**, dừng quay và xác nhận vị trí qua **3 khung hình mới liên tiếp**.
6. Khi xác nhận thành công, đánh giá lại khoảng cách rồi tiếp tục tiến thẳng. Nếu phải đổi chiều quay, xe dừng và chờ xác nhận trước khi đổi chiều.
7. Nếu mất mục tiêu trong lúc căn hướng, xe dừng; chế độ chỉ bám chờ mục tiêu xuất hiện lại, còn Auto + AI xử lý theo UC_AI04.

**Kết quả và hậu điều kiện:** Xe căn hướng về mục tiêu, sau đó tiếp tục bám khi điều kiện cho phép. Trong bước căn hướng, xe xoay tại chỗ; việc trở lại tiến thẳng chỉ diễn ra sau khi đã dừng quay và xác nhận vị trí.

## UC_AI03: Giữ khoảng cách và dừng an toàn trong quá trình bám

**Tác nhân:** Người sử dụng.

**Tiền điều kiện:** Xe đang bám mục tiêu bằng AI độc lập hoặc trong chế độ Auto + AI; cảm biến HC-SR04 được đưa về hướng trước ở góc 90°.

**Thao tác của tác nhân:** Cho xe bám mục tiêu; khi khoảng cách phía trước giảm, quan sát phản ứng dừng. Người dùng có thể nhấn **Dừng khẩn cấp** khi cần kết thúc ngay việc điều khiển.

**Luồng xử lý của hệ thống:**

1. Cập nhật khoảng cách phía trước từ cảm biến siêu âm trong quá trình bám.
2. Khi khoảng cách **nhỏ hơn hoặc bằng 50 cm**, dừng xe và chuyển sang trạng thái giữ khoảng cách.
3. Nếu khoảng cách tăng nhưng **chưa lớn hơn 55 cm**, xe tiếp tục đứng yên để hạn chế chạy–dừng liên tục quanh ngưỡng.
4. Khi khoảng cách **lớn hơn 55 cm**, kiểm tra lại mục tiêu và hướng xe để tiếp tục bám hoặc căn hướng.
5. Nếu cảm biến không có Echo hoặc số đo ngoài khoảng hợp lệ **2–400 cm**, xe dừng chờ. Chỉ xem xét di chuyển tiếp khi số đo hợp lệ trở lại và thỏa điều kiện khoảng cách.
6. Nếu ảnh hoặc kết quả AI cũ quá **0,5 giây**, hệ thống kết thúc phiên do lỗi và yêu cầu xe dừng. Nếu ESP32 không nhận lệnh hợp lệ trong hơn **500 ms**, ESP32 tự dừng và thu hồi phiên điều khiển.
7. Nếu người dùng nhấn **Dừng khẩn cấp**, khi nhận yêu cầu, ESP32 dừng động cơ, thu hồi phiên AI và chuyển về **Wi-Fi Manual**; giao diện hiển thị kết quả xác nhận hoặc lỗi liên lạc.

**Kết quả và hậu điều kiện:** Xe tạm dừng khi khoảng cách hoặc số đo không phù hợp; phiên vẫn có thể tiếp tục nếu chỉ đang giữ khoảng cách hoặc chờ cảm biến. Nếu phiên đã kết thúc do lỗi hoặc dừng khẩn cấp, người dùng phải chủ động bắt đầu lại. Trong lúc bám AI, xe không tự lùi để tăng khoảng cách.

*Lưu ý:* Cảm biến đo vật gần nhất phía trước, chưa xác định đó có phải mục tiêu YOLO hay không. Mốc 50 cm là ngưỡng xử lý số đo, không bảo đảm khoảng cách dừng thực tế chính xác 50 cm.

## UC_AI04: Tự di chuyển tránh vật cản kết hợp bám mục tiêu (Auto + AI)

**Tác nhân:** Người sử dụng.

**Tiền điều kiện:** Camera và mô hình AI sẵn sàng; ảnh và kết quả xử lý còn mới trong giới hạn 0,5 giây; ESP32 kết nối được và có firmware hỗ trợ Auto + AI; cảm biến siêu âm, servo và động cơ hoạt động; chưa có phiên AI hoạt động.

**Thao tác của tác nhân:** Nhấn **Bắt đầu Auto + AI** trên bảng điều khiển laptop; đưa mục tiêu vào hoặc ra khỏi vùng quan sát để hệ thống tự chuyển hành vi.

**Luồng xử lý của hệ thống:**

1. Thiết lập phiên Auto + AI và xác nhận xe dừng trước khi bắt đầu.
2. **Tìm mục tiêu:** khi chưa phát hiện mục tiêu, ESP32 cho xe tự di chuyển và tránh vật cản; laptop tiếp tục nhận hình và chạy nhận diện.
3. **Xác nhận mục tiêu:** khi có ứng viên, dừng xe, xác nhận mục tiêu ổn định qua **3 khung hình mới liên tiếp** và chờ xác nhận xe dừng ít nhất **150 ms**.
4. **Chuyển sang bám:** giữ xe dừng, đưa cảm biến về góc **90°**, chờ ít nhất **300 ms**, có số đo hợp lệ và ảnh mục tiêu mới trước khi cho phép di chuyển.
5. **Bám mục tiêu:** tiến, căn hướng và giữ khoảng cách theo UC_AI01, UC_AI02 và UC_AI03. Vật phía trước ở gần chỉ làm xe giữ dừng theo khoảng cách, không tự chuyển sang tránh vật cản vì đó có thể là chính mục tiêu.
6. **Mất mục tiêu:** dừng ngay và chờ. Nếu mục tiêu xuất hiện lại, xác nhận lại trước khi bám; nếu không thấy liên tục **1,5 giây trên các ảnh mới**, trở về hành vi tự tránh vật cản để tiếp tục tìm.
7. Khi trở lại tìm mục tiêu, khởi tạo lại chu trình tránh vật cản từ bước kiểm tra phía trước. Nếu mất hình, kết quả AI quá cũ hoặc lỗi liên lạc, kết thúc phiên; không dùng lỗi camera làm điều kiện tiếp tục tự chạy.
8. Khi người dùng nhấn **Dừng Auto + AI / AI**, yêu cầu xe dừng, kết thúc phiên và đưa xe về **Wi-Fi Manual**.

**Kết quả và hậu điều kiện:** Xe tự chuyển giữa tìm mục tiêu bằng hành vi tránh vật cản và bám mục tiêu bằng AI trong cùng một phiên. Sau khi dừng hoặc kết thúc do lỗi, kết nối lại camera không tự khởi động xe; người dùng phải nhấn bắt đầu lần nữa.
