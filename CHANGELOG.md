# Lịch sử thay đổi

## [0.2.0] - Chưa phát hành

### API và dữ liệu

- Giữ API v1 làm mặc định. API v2 chỉ được chọn bằng `--api-version v2` hoặc binding của session; không tự chuyển version khi gặp lỗi.
- Bổ sung adapter v2 cho các lệnh đọc hiện có: kỳ học, lịch học/lịch tuần, điểm, lịch thi, điểm danh, đơn từ, news, thông tin sinh viên/campus, học phí, môn học, thông báo và kiểm tra feedback/profile. Survey tiếp tục dùng dịch vụ và chữ ký riêng.
- Coi ID kỳ học là opaque, chọn kỳ mới nhất theo `startDate` và giữ thứ tự server khi ngày trùng nhau. Query dùng đúng tên trường theo từng operation.
- Giữ stdout JSON/ICS tách khỏi log và lỗi trên stderr; xuất tiếng Việt an toàn hơn trên Windows, kể cả bảng Rich và help.
- Bổ sung xử lý bảng điểm HTML ba cột `Item/Weight/Value`, giữ thông tin khi có `rowspan`. ICS giữ UTF-8, CRLF và thêm `UID`/`DTSTAMP` UTC cho từng sự kiện.

### OAuth và session

- Gia cố đăng nhập FEID bằng discovery, PKCE, state/nonce và xác minh ID token. Identity sinh viên lấy từ handshake FAP, không suy ra từ access token chưa xác minh.
- Ràng buộc session với campus, API version và loại tài khoản; đổi binding phải handshake lại. Giữ session cũ thiếu version theo v1.
- Lưu session nguyên tử và khóa liên tiến trình. Bảo toàn refresh token đã rotate khi handshake tiếp theo thất bại.
- Chỉ refresh/retry thao tác đọc tối đa một lần khi có tín hiệu hết phiên rõ ràng. Lỗi operation, timeout, 5xx hoặc App Check không tự gây refresh, logout hay fallback version.
- `login` có thể phục hồi session sai cấu trúc, thiếu identity hoặc đã nhận `invalid_grant`; lỗi mạng/storage không bị coi là hết phiên.

### Chuẩn bị phát hành

- Chuẩn bị pipeline từ tag stable: kiểm tag/version và quan hệ với `main`, gọi CI tái sử dụng trên đúng SHA, dùng một bộ wheel/sdist cùng manifest SHA-256, rồi tách publish, kiểm tra index và GitHub Release theo quyền tối thiểu.
- Bổ sung runbook xử lý upload một phần, retry và version lỗi; TestPyPI là rehearsal thủ công riêng, không phải nghiệm thu backend và không tự promote sang PyPI.
- Workflow được chuẩn bị không có nghĩa đã publish thành công. Việc tạo/push tag, duyệt environment, upload và tạo GitHub Release cần nghiệm thu riêng.

### Kiểm chứng và giới hạn còn mở

- Báo cáo Phase 4 ghi nhận các luồng đọc v2 trên HN, gồm login/refresh và JSON/ICS; đây không phải bằng chứng cho mọi campus, tài khoản hoặc route.
- **V1/APHL:** `news` và `other notification` vẫn trả HTTP 200/body 201 với `data: null`; `other fee` vẫn trả HTTP 404 trong lượt chạy lại ngày 19/10/2026. Request đã được đối chiếu với app, nhưng nguyên nhân chưa được xác định. CLI giữ lỗi, không coi là dữ liệu rỗng, hết phiên hoặc route ngừng hỗ trợ trên mọi campus.
- **Fee/survey positive:** theo quyết định ngày 19/10/2026, chờ dữ liệu nghiệp vụ phù hợp và không chặn chuyển sang Phase 5. Schema live có dữ liệu vẫn **chưa kiểm chứng**; fee HTTP/body 200 hoặc survey not-found không đủ để đóng các mục này.
- ICS đã được đọc bằng reader độc lập `icalendar`; chưa xác nhận import vào Google Calendar/Outlook. Reader `ics` hiện có giới hạn recursion với lịch lớn.
- Phase 6 đang bổ sung transcript, balance, courses/training, subjects theo kỳ, tìm news, ảnh JSON, marks summary và doctor trước khi phát hành; xem coverage Phase 6. Các capability mới có fixture nhưng chưa nghiệm thu live. Rating list student/v1 đã có code/fixture; v2 stub bị chặn. Feedback đầy đủ và thao tác ghi vẫn còn gate contract/schema, không được coi là đã hỗ trợ.
- Maintainer phải chấp nhận rõ phạm vi hỗ trợ và các lỗi v1 còn mở trước khi tạo tag. CI xanh không thay thế nghiệm thu API thật hoặc quyết định này.

## [0.1.8] - Mốc trước 0.2.0

- Chuyển quy trình phát triển sang uv, bổ sung lockfile và hướng dẫn môi trường dev.
- Sửa lệnh `myfap version` để đọc metadata của distribution `myfap`.
- Giữ setuptools, entry point CLI và phạm vi Python >=3.9.

Phần lịch sử này chỉ tóm tắt nội dung migration đã được ghi nhận; không bổ sung kết luận live hoặc thay đổi ngày phát hành cũ.
