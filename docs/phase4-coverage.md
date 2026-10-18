# Coverage Phase 4

Phase 4 bổ sung adapter v2 cho các command đọc đã có trong CLI. V1 vẫn là mặc định. Bảng dưới đây phân biệt fixture, capture và kết quả smoke live v2 trên HN đã ghi ở phần cuối tài liệu. HTTP/body 200 không tự xác nhận payload có dữ liệu nghiệp vụ; positive fee/survey vẫn còn trong [TODO live](../tasks/todo.md#kiểm-chứng-live-còn-mở-trước-khi-phát-hành). Trạng thái operation đã triển khai nằm trong [ma trận route v2](v2-contracts.md#ma-trận-route-v2).

| Nhóm command | Operation v1 | Operation v2 | Trạng thái sau Phase 4 |
|---|---|---|---|
| Lịch học | `GetActivityStudent` | `GetActivityStudent` | Fixture v1/v2; live v1 và live v2 schedule đã có từ Phase 1/3 |
| Lịch tuần | `GetActivityStudentByWeek` | `GetActivityStudentByWeek` | Fixture; v1 live trước đó; smoke v2 HN HTTP/body 200 |
| Điểm tổng hợp | `GetStudentMark` | `GetStudentMark` | Fixture; v1 live trước đó; smoke v2 HN HTTP/body 200 |
| Điểm chi tiết | `GetMarkByCourse` | `GetMarkByCourse` | Fixture; tham số `CourseId` giữ nguyên dạng opaque |
| Lịch thi | `GetScheduleExam` | `GetScheduleExam` | Fixture/capture; smoke v2 HN HTTP/body 200 |
| Điểm danh tổng quát | `GetStudentAttendances` | `GetStudentAttendances` | Fixture/capture; smoke v2 HN HTTP/body 200 |
| Điểm danh chi tiết | `getCourseAttendance` | `GetCourseAttendance` | Fixture; v2 đổi đúng tên route và giữ `SubjectCode`/`ClassName` |
| Đơn từ | `GetApplication` | `GetApplication` | Fixture query `Authen` mới sau refresh; smoke v2 HN HTTP/body 200 |
| Tin tức | `GetTop10News` | `GetTop10News` | Finding v1 body `201` vẫn mở; smoke v2 HN HTTP/body 200 |
| Thông tin sinh viên | `GetStudentById` | `GetStudentById` | Fixture; v1 live trước đó; smoke v2 HN HTTP/body 200 |
| Thông tin campus | `GetCampusInfo` | `GetCampusInfo` | Fixture; v1 live trước đó; smoke v2 HN HTTP/body 200 |
| Survey | Survey service riêng | Survey service riêng | Live HTTP 200/body 404 qua dịch vụ survey; positive case chưa xác nhận |
| Học phí | `GeFeeByRoll` | `GeFeeByRoll` | Finding v1 HTTP 404 vẫn mở; v2 HN HTTP/body 200; positive payload chưa xác nhận |
| Môn học | `GetSubjets` | `GetSubjets` | Fixture strict query; smoke v2 HN HTTP/body 200 |
| Feedback/profile | `CheckOpenFeedBack`, `CheckUpdateProfile` | Cùng operation | Fixture query `Authen` mới sau refresh; smoke v2 HN HTTP/body 200 |
| Thông báo | `GetNotificationByRoll` | `GetNotificationByRoll` | Finding v1 body `201` vẫn mở; smoke v2 HN HTTP/body 200 |

## Quy tắc transport

- V2 chỉ gửi các operation có trong allowlist đọc. Route ghi, stub hoặc chưa có capability vẫn bị chặn trước HTTP.
- GET và POST dùng header theo capture app: `Accept`, `Accept-Encoding`, `User-Agent`, `ClientCode`, `CampusCode`, `Authorization` và `Checksum`. Chỉ POST có JSON body mới thêm `Content-Type: application/json`.
- Các command đọc cần session qua proxy, gồm nhóm `info` và `other`, kiểm tra capability trước khi nạp session. Version được chọn theo option rồi metadata session; lệnh thiếu capability không handshake, refresh hoặc gọi API dữ liệu.
- Survey giữ host và chữ ký riêng. Khi dùng session v2, CLI nhắc trên stderr rằng request đi tới `survey.fpt.edu.vn`; stdout vẫn chỉ chứa JSON khi có `--stdout`.
- `GetSemester` không có query; `GetWeekByDate` chỉ có `date`; các route còn lại dùng đúng case query trong APK.
- Bốn route `CheckOpenFeedBack`, `CheckUpdateProfile`, `GetApplication` và `GetNotificationByRoll` vẫn có `Authen` trong query. Giá trị này lấy từ credential binding hiện tại, không giữ bản cũ sau refresh.
- Retry đọc tối đa một lần khi server báo hết phiên rõ ràng. Timeout, 403, 5xx, App Check và lỗi operation không fallback sang v1.
- `termID` được giữ opaque; CLI chọn kỳ theo `startDate` và giữ thứ tự server khi ngày trùng nhau.

## Kiểm thử đã chạy

- Contract fixture cho method, path, query, header, credential, lỗi JSON/HTTP, empty/not-found, refresh retry và App Check.
- CLI fixture cho command v2, lựa chọn kỳ, `--stdout`, ICS, survey riêng, capability và lỗi trước HTTP.
- Mutation check: bỏ ánh xạ `getCourseAttendance` làm test capability/transport thất bại.
- Bộ test hiện có 306 test trên Python 3.11 Windows: 302 đạt, 4 skip theo điều kiện môi trường. Regression stdout kiểm tra JSON tiếng Việt/emoji và hai bảng Rich trên tiến trình CLI riêng bị ép `PYTHONIOENCODING=cp1252:strict`; byte output được đọc lại bằng UTF-8. Stream chỉ hỗ trợ text vẫn có test riêng. Regression login kiểm tra session sai cấu trúc mở lại browser, giữ nội dung cũ khi hủy và không mở browser lại khi gặp lỗi mạng. Matrix Python 3.9/3.11 và Ubuntu/Windows, build, Twine, artifact validator và pip smoke chạy lại trong CI của PR.

- Regression parser giữ đủ `item`, `weight`, `value` khi thiếu cột ghi chú, nhận diện bảng `Item/Weight/Value` không có category và giữ fallback cũ. ICS chấp nhận khoảng trắng quanh dấu `-`, trong hoặc ngoài dấu ngoặc; thời gian sự kiện vẫn đúng múi giờ Việt Nam.

## Giới hạn còn lại

Phase 4 chưa tích hợp transcript, balance, ảnh, tìm kiếm news, `GetVersion`, form feedback hoặc thao tác ghi. Chưa có positive live case cho học phí và survey trong lượt này. Fiddler/Android chỉ xuất metadata cục bộ; không lưu token, identity, payload học vụ hoặc màn hình vào repository.

Parser điểm đã xử lý hàng có ba cột dữ liệu `Item`, `Weight`, `Value` khi thiếu cột ghi chú; test phủ dòng đầu tiên và dòng tiếp theo trong `rowspan`. Bảng không có category được nhận diện qua header `Item/Weight/Value`; nếu header không xác định cấu trúc này, hàng ba `<td>` vẫn dùng fallback category/item/value cũ. Các trường hợp mới được kiểm bằng HTML tổng hợp, chưa xác nhận live trên cấu trúc này.

Lượt rà môi trường ngày 17/10 ghi nhận Fiddler có 315 session và 23 path API đã biết trong LiveTraffic; capture và system proxy vẫn tắt. ADB thấy một emulator kết nối và tiến trình `com.fuct` đang chạy. Harness CLI Phase 4 đã mở browser login HN nhưng không nhận callback trong thời hạn 120 giây, vì vậy chưa ghi live smoke CLI trong lượt này. Không dùng dữ liệu capture để giả lập session.

Lượt smoke v2 sau đó đã login và chạy thật trên campus HN: semesters, schedule JSON/ICS, marks, exams, week timetable, attendance, applications, news, student/campus info, fee, subjects, notification, feedback và profile đều exit 0 với HTTP 200/body 200. Survey trả HTTP 200/body 404 và được giữ là not-found hợp lệ. Có 21 operation khác nhau và 23 request; stdout JSON hợp lệ, ICS đọc được bằng `icalendar`, session/lock tạm đã xóa. Không chạy thao tác ghi.

Lượt smoke v1 để đóng lại `news`, `notification` và `fee` không nhận callback đăng nhập nên chưa có kết quả mới. Các finding v1 trước đó vẫn mở: news/notification body `201`, fee HTTP 404. Kết quả v2 thành công không được dùng để thay cho kiểm chứng v1.

ICS được kiểm tra bằng dữ liệu tổng hợp với reader `icalendar` độc lập: 250 sự kiện giữ đúng DTSTART/DTEND theo múi giờ Việt Nam. File và stdout giữ nguyên byte CRLF trên cả stream mô phỏng Unix và Windows. Reader `ics` hiện tại gặp giới hạn recursion ở lịch lớn với recursion limit mặc định; runtime không tăng giới hạn để che lỗi. Khả năng import vào ứng dụng lịch thực tế vẫn cần kiểm chứng riêng.
