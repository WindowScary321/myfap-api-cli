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

- [ ] Contract test ở biên HTTP và wrapper cho các route đọc v1/v2; dữ liệu fixture hoàn toàn tổng hợp.
- [ ] CLI test cho nhóm command hiện có, stdout JSON/ICS, capability, option và lỗi trước HTTP.
- [ ] Regression cho retry dùng key/checksum/Authen mới và giới hạn một lần.
- [ ] Kiểm tra ICS bằng dữ liệu tổng hợp và một reader độc lập; ghi rõ giới hạn của reader hiện tại nếu còn.
- [ ] Live trên session tạm riêng, không đọc thư mục session cá nhân. Chỉ giữ metadata đã lọc, không giữ lịch/điểm/hồ sơ hoặc credential thật trong Git.
- [ ] Chạy lại news, notification và fee của v1; ghi nguyên trạng lỗi còn lại và giới hạn theo version/campus. Không dùng CI xanh thay kết luận live.
- [ ] Kiểm tra positive fee/survey khi tài khoản có điều kiện phù hợp; nếu thiếu thì giữ trạng thái chưa kiểm chứng.
- [ ] Review độc lập, kiểm tra tiếng Việt, test Python 3.9/3.11, build, Twine, artifact validator và pip smoke.
- [ ] Draft PR riêng, comment tiếng Việt sau các mốc quan trọng; maintainer quyết định Ready for review và merge.

## Quy tắc dữ liệu và thiết bị

Fiddler và Android chỉ phục vụ đối chiếu luồng đọc đã được cho phép. Dữ liệu request/response hoặc màn hình được xử lý cục bộ; chỉ tên operation, method, HTTP/body code, kiểu dữ liệu và kết quả kiểm tra được xuất ra. Không replay token từ capture, không đọc hoặc in token bằng tool, không gửi dữ liệu cá nhân ra ngoài PC. Không thay proxy, certificate, quyền truy cập hoặc dữ liệu tài khoản nếu không cần cho phép thử.

Các kết quả live chưa đạt vẫn phải được ghi trong coverage. Nếu backend chưa đáp ứng hoặc thiếu positive case, phạm vi phát hành cần maintainer quyết định; không đánh dấu parity đầy đủ chỉ từ fixture.
