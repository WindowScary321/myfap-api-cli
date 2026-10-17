# Coverage Phase 4

Phase 4 bổ sung adapter v2 cho các command đọc đã có trong CLI. V1 vẫn là mặc định. Bảng dưới đây tách kết quả test fixture, request quan sát trong Fiddler và kiểm chứng live trước đó; một route được đánh dấu capture không có nghĩa command CLI đã chạy live với cùng session.

| Nhóm command | Operation v1 | Operation v2 | Trạng thái sau Phase 4 |
|---|---|---|---|
| Lịch học | `GetActivityStudent` | `GetActivityStudent` | Fixture v1/v2; live v1 và live v2 schedule đã có từ Phase 1/3 |
| Lịch tuần | `GetActivityStudentByWeek` | `GetActivityStudentByWeek` | Fixture; v1 live trước đó, v2 cần live smoke riêng |
| Điểm tổng hợp | `GetStudentMark` | `GetStudentMark` | Fixture; v1 live trước đó, v2 cần live smoke riêng |
| Điểm chi tiết | `GetMarkByCourse` | `GetMarkByCourse` | Fixture; tham số `CourseId` giữ nguyên dạng opaque |
| Lịch thi | `GetScheduleExam` | `GetScheduleExam` | Fixture; v2 có route trong capture, chưa kết luận live CLI |
| Điểm danh tổng quát | `GetStudentAttendances` | `GetStudentAttendances` | Fixture; v2 có route trong capture, chưa kết luận live CLI |
| Điểm danh chi tiết | `getCourseAttendance` | `GetCourseAttendance` | Fixture; v2 đổi đúng tên route và giữ `SubjectCode`/`ClassName` |
| Đơn từ | `GetApplication` | `GetApplication` | Fixture; query `Authen` được dựng lại sau refresh |
| Tin tức | `GetTop10News` | `GetTop10News` | V1 live trước đó trả body `201`, chưa đóng finding; v2 fixture/capture |
| Thông tin sinh viên | `GetStudentById` | `GetStudentById` | Fixture; v1 live trước đó |
| Thông tin campus | `GetCampusInfo` | `GetCampusInfo` | Fixture; v1 live trước đó |
| Survey | Survey service riêng | Survey service riêng | Giữ contract riêng; not-found chưa phải positive success |
| Học phí | `GeFeeByRoll` | `GeFeeByRoll` | V1 live trước đó trả HTTP 404; v2 fixture/capture, chưa kết luận capability đầy đủ |
| Môn học | `GetSubjets` | `GetSubjets` | Fixture; v2 route đọc có strict query |
| Feedback/profile | `CheckOpenFeedBack`, `CheckUpdateProfile` | Cùng operation | Fixture; query `Authen` được dựng lại sau refresh |
| Thông báo | `GetNotificationByRoll` | `GetNotificationByRoll` | V1 live trước đó trả body `201`, chưa đóng finding; v2 fixture/capture |

## Quy tắc transport

- V2 chỉ gửi các operation có trong allowlist đọc. Route ghi, stub hoặc chưa có capability vẫn bị chặn trước HTTP.
- GET dùng header theo capture app: `Accept`, `Accept-Encoding`, `User-Agent`, `ClientCode`, `CampusCode`, `Authorization` và `Checksum`; GET không thêm `Content-Type`.
- `GetSemester` không có query; `GetWeekByDate` chỉ có `date`; các route còn lại dùng đúng case query trong APK.
- Bốn route `CheckOpenFeedBack`, `CheckUpdateProfile`, `GetApplication` và `GetNotificationByRoll` vẫn có `Authen` trong query. Giá trị này lấy từ credential binding hiện tại, không giữ bản cũ sau refresh.
- Retry đọc tối đa một lần khi server báo hết phiên rõ ràng. Timeout, 403, 5xx, App Check và lỗi operation không fallback sang v1.
- `termID` được giữ opaque; CLI chọn kỳ theo `startDate` và giữ thứ tự server khi ngày trùng nhau.

## Kiểm thử đã chạy

- Contract fixture cho method, path, query, header, credential, lỗi JSON/HTTP, empty/not-found, refresh retry và App Check.
- CLI fixture cho command v2, lựa chọn kỳ, `--stdout`, ICS, survey riêng, capability và lỗi trước HTTP.
- Mutation check: bỏ ánh xạ `getCourseAttendance` làm test capability/transport thất bại.
- 289 test local pass trên Python 3.11 Windows, gồm 4 skip theo điều kiện môi trường. Matrix Python 3.9/3.11 và Ubuntu/Windows, build, Twine, artifact validator và pip smoke chạy lại trong CI của PR.

## Giới hạn còn lại

Phase 4 chưa tích hợp transcript, balance, ảnh, tìm kiếm news, `GetVersion`, form feedback hoặc thao tác ghi. Chưa có positive live case cho học phí và survey trong lượt này. Fiddler/Android chỉ xuất metadata cục bộ; không lưu token, identity, payload học vụ hoặc màn hình vào repository.

ICS được kiểm tra bằng dữ liệu tổng hợp với reader `icalendar` độc lập: 250 sự kiện giữ đúng DTSTART/DTEND theo múi giờ Việt Nam. File và stdout giữ nguyên byte CRLF trên cả stream mô phỏng Unix và Windows. Reader `ics` hiện tại gặp giới hạn recursion ở lịch lớn với recursion limit mặc định; runtime không tăng giới hạn để che lỗi. Khả năng import vào ứng dụng lịch thực tế vẫn cần kiểm chứng riêng.
