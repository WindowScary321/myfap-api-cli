# Phase 4: phủ các command đọc hiện có

Nhánh `feat/phase4-command-parity` bắt đầu từ main tại `74dd8e5`, sau khi PR #7 được merge. Giữ version package `0.2.0`, Python >=3.9 và entry point hiện có. V1 tiếp tục là mặc định; v2 được chọn bằng option hoặc session.

## Phạm vi triển khai

- Phủ v2 cho lịch học, lịch tuần, điểm tổng hợp/chi tiết, lịch thi, điểm danh tổng hợp/chi tiết, đơn từ, news, thông tin sinh viên/campus, fee, subjects và các lệnh kiểm tra feedback/profile/notification hiện có.
- Giữ host và checksum riêng của survey. Không biến trạng thái not-found thành danh sách rỗng hoặc kết luận không có khảo sát bắt buộc.
- Giữ JSON/ICS, tên trường, lựa chọn kỳ học theo ngày và stdout sạch. Mọi request dùng timeout đã chọn, không follow redirect hoặc fallback version.
- Giữ query theo từng operation, bao gồm CampusCode, Semester/semester, CourseId và bốn route hiện có vẫn mang Authen. Điểm danh chi tiết dùng GetCourseAttendance trên v2 và getCourseAttendance trên v1.
- Credential/signature/legacy Authen phải được dựng lại khi retry sau refresh. Chỉ retry đọc một lần khi có tín hiệu expiry rõ; App Check, timeout, 403 và 5xx không kích refresh.
- Bảng coverage phân biệt bằng chứng APK, capture, fixture, live thành công/thất bại và phần chưa kiểm chứng. HTTP 404 không tự chứng minh route đã ngừng hỗ trợ.

Không thêm transcript, balance, ảnh, news search, GetVersion, form feedback hoặc thao tác ghi vào CLI trong phase này. Những route đó thuộc Phase 6. Không phát hành, tạo tag hay đổi mặc định sang v2.

## Kiểm chứng

- [x] Contract test ở biên HTTP và wrapper cho các route đọc v1/v2; dữ liệu fixture hoàn toàn tổng hợp.
- [x] CLI test cho nhóm command hiện có, stdout JSON/ICS, capability, option và lỗi trước HTTP.
- [x] Regression cho retry dùng key/checksum/Authen mới và giới hạn một lần.
- [x] Kiểm tra ICS bằng dữ liệu tổng hợp và một reader độc lập; ghi rõ giới hạn của reader hiện tại nếu còn.
- [x] Live trên session tạm riêng, không đọc thư mục session cá nhân. Chỉ giữ metadata đã lọc, không giữ lịch/điểm/hồ sơ hoặc credential thật trong Git.
- [ ] Chạy lại news, notification và fee của v1; ghi nguyên trạng lỗi còn lại và giới hạn theo version/campus. Không dùng CI xanh thay kết luận live.
- [ ] Kiểm tra positive fee/survey khi tài khoản có điều kiện phù hợp; nếu thiếu thì giữ trạng thái chưa kiểm chứng.
- [x] Review độc lập, kiểm tra tiếng Việt, test Python 3.9/3.11, build, Twine, artifact validator và pip smoke.
- [x] Draft PR riêng, comment tiếng Việt sau các mốc quan trọng; maintainer quyết định Ready for review và merge.

Đã có bằng chứng cho 7/9 mục. Contract và CLI được kiểm tra tại `tests/test_phase4_transport.py`, `tests/test_api_v2.py`, `tests/test_cli_v2_capabilities.py` và các regression v1. Test ICS dùng reader `icalendar` độc lập. Kết quả live v2 HN đã ghi 21 operation khác nhau, 23 request và dọn session/lock tạm; xem [coverage Phase 4](../docs/phase4-coverage.md). Matrix Ubuntu/Windows × Python 3.9/3.11, build và cài artifact được ghi tại [checks PR #8](https://github.com/WindowScary321/myfap-api-cli/pull/8/checks).

Hai mục live còn mở: lần chạy lại `news`, `notification`, `fee` của v1 chưa nhận callback đăng nhập; positive fee/survey chưa được xác nhận với dữ liệu nghiệp vụ phù hợp. Fee v2 trả HTTP/body 200 chưa đủ để kết luận positive case, còn survey trả body 404. Các ô đã đánh dấu không có nghĩa toàn bộ Phase 4 đã hoàn tất.

Parser điểm đã được sửa cho cấu trúc ba cột `Item`, `Weight`, `Value` khi không có cột ghi chú, gồm cả dòng đầu tiên và dòng tiếp theo trong `rowspan`. Hàng ba `<td>` theo fallback category/item/value cũ vẫn được giữ để tránh thay đổi output tương thích.

Xuất ICS cũng đã xử lý khoảng trắng quanh dấu `-` và dấu ngoặc trong `slotTime`; regression xác nhận giờ bắt đầu/kết thúc không thay đổi. Hai lỗi parser được tái hiện và kiểm thử bằng dữ liệu tổng hợp, chưa dùng dữ liệu tài khoản thật trong lượt sửa này.

Các bản sửa bổ sung xử lý bảng Rich trên stdout `cp1252`, cho `login` tự phục hồi session sai cấu trúc và thêm nhóm dependency `ci` vào hai bước sync/test của workflow publish. Việc này sửa lỗi thiếu `icalendar` trên runner sạch; pipeline tag → reusable CI → publish → smoke → GitHub Release của Phase 5 vẫn chưa được triển khai. Không chạy publish hoặc thay đổi trigger release trong lượt sửa này.

Sau bàn giao 19/10/2026, đã sửa thêm refresh `invalid_grant` không đánh dấu cần đăng nhập lại, student session thiếu `mssv`/`email`, help trên stdout `cp1252` và ICS thiếu `DTSTAMP`. Bộ test có 313 case; các nhánh lỗi session dùng fixture. Live v2/HN đã xác nhận login, refresh, đọc dữ liệu và ICS có đủ `UID`/`DTSTAMP` UTC, sau đó dọn session/lock tạm. Xem [kết quả sau sửa](../docs/phase4-coverage.md#kiểm-chứng-sau-bàn-giao-ngày-19102026); không dùng kết quả này đóng các TODO live v1 hoặc positive fee/survey.

## Quy tắc dữ liệu và thiết bị

Fiddler và Android chỉ phục vụ đối chiếu luồng đọc đã được cho phép. Dữ liệu request/response hoặc màn hình được xử lý cục bộ; chỉ tên operation, method, HTTP/body code, kiểu dữ liệu và kết quả kiểm tra được xuất ra. Không replay token từ capture, không đọc hoặc in token bằng tool, không gửi dữ liệu cá nhân ra ngoài PC. Không thay proxy, certificate, quyền truy cập hoặc dữ liệu tài khoản nếu không cần cho phép thử.

Các kết quả live chưa đạt vẫn phải được ghi trong coverage. Nếu backend chưa đáp ứng hoặc thiếu positive case, phạm vi phát hành cần maintainer quyết định; không đánh dấu parity đầy đủ chỉ từ fixture.
