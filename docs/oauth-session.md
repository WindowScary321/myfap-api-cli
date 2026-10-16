# Đăng nhập và quản lý session

[Quay lại README](../README.md) · [Hướng dẫn phát triển](development.md)

## Đăng nhập mới

```sh
myfap login
myfap login --force
myfap --config ./local-state.json login --force
```

CLI mở Chrome, Edge hoặc Firefox để đăng nhập FEID. Mỗi lần đăng nhập tạo PKCE S256, state và nonce mới, với thời gian chờ trên trình duyệt là 120 giây. Trước khi gọi FAP handshake, CLI kiểm tra callback, chữ ký RS256 qua JWKS và các claim của ID token. MSSV, email và loại tài khoản lấy từ handshake; CLI không suy ra chúng bằng cách decode access token.

Các claim thời gian `exp`, `iat` và `nbf` của ID token có leeway 30 giây để chịu được lệch đồng hồ nhỏ. Token thiếu `exp`, có thời gian sai kiểu hoặc giá trị không hữu hạn vẫn bị từ chối. Leeway không bỏ qua kiểm tra chữ ký, issuer, audience, subject, nonce hay `at_hash`.

`--force` mở lại trình duyệt kể cả khi đã có session. Nếu file JSON hỏng hoặc thiếu trường bắt buộc, đăng nhập thành công sẽ thay file đó. Khi đăng nhập thất bại, file cũ được giữ nguyên. Lỗi quyền truy cập hoặc đường dẫn không an toàn vẫn bị chặn.

Khi session cần đăng nhập lại hoặc binding cũ không được hỗ trợ, `myfap login` tự mở trình duyệt nên không cần chạy lại với `--force`. Login mới chỉ kế thừa campus đã lưu, rồi dùng luồng v1/student của Phase 2 dù file cũ có binding v2. Lệnh đọc vẫn từ chối session v2 trước khi gửi HTTP. Binding và credential cũ chỉ được thay sau khi login thành công.

CLI chọn campus theo thứ tự: `--campus`, campus trong session, rồi `APHL` nếu chưa có session hợp lệ. Có thể đặt option trước command hoặc trong `login`:

```sh
myfap --campus APHL login --force
myfap login --campus APHL --force
```

Session gắn với campus, API version và loại tài khoản. Đổi campus cần handshake lại trước request dữ liệu; binding mới chỉ được lưu sau handshake thành công. Phase 2 hỗ trợ v1 và tài khoản student. Adapter v2 và option chọn version thuộc Phase 3.

## Dùng session cũ và refresh

Session cũ thiếu API version được hiểu là v1. Khi nạp session, CLI đọc và kiểm tra binding cục bộ. Việc xác thực trên server diễn ra trong request dữ liệu thực tế, nên CLI không gọi `GetSemester` chỉ để dò session. Session chưa có subject OIDC đã xác minh cần `myfap login --force` trước khi refresh; payload access token không được dùng làm bằng chứng identity.

`GetSemester` chỉ chạy khi gọi `semesters` hoặc khi command cần tự chọn kỳ: `schedule`, `marks` không có `--courseid`, `exams`, `attendance` và `week-timetable`. Khi truyền `--semester`, CLI bỏ qua bước tra kỳ. Các lệnh như `info`, `news`, `applications`, `marks --courseid` và `other` gọi thẳng operation tương ứng.

```sh
myfap refresh
myfap --config ./local-state.json refresh
```

Lệnh đọc tự refresh rồi retry tối đa một lần khi nhận HTTP 401. Với API v1, cùng cơ chế đó áp dụng cho body `code: 201` có message chính xác `Token invalid` trên 17 FAP read operation có `Authen`. Nhóm operation này gồm kỳ học, news, feedback/profile, notification, học phí, subjects, lịch học, điểm, điểm danh, lịch thi, đơn từ và thông tin sinh viên/campus. Bốn operation cốt lõi đã được đối chiếu trực tiếp với caller APK; 13 operation còn lại là mở rộng QoL theo cùng exact-message guard.

Body `201` thiếu hoặc sai message vẫn là lỗi operation. News/notification rỗng cũng không refresh. Public bootstrap, tra tuần và survey không mang FAP `Authen`, nên không tự refresh. Body `401` của v1, timeout, lỗi mạng, HTTP 403/5xx và App Check cũng không gây refresh. Request ghi không tự retry.

Refresh giữ lock từ lúc đọc session đến lúc lưu xong để hai process không rotate cùng token. Nếu process khác đã refresh cùng tài khoản và binding, CLI dùng session mới. Nếu identity hoặc binding đã đổi, command dừng và yêu cầu chạy lại.

CLI ghi refresh token mới bằng thao tác atomic trước khi xác minh ID token và handshake tiếp theo. Nếu bước sau lỗi, file giữ token đã rotate và đánh dấu FAP cần xác thực lại. Khi ID token đã hợp lệ nhưng handshake gặp lỗi tạm thời, command kế tiếp thử handshake lại.

Trước handshake hoặc phục hồi binding, access token đã hết hạn hoặc còn tối đa 30 giây sẽ được refresh sớm để bù thời gian request. Buffer này tránh dùng access token sát hạn; leeway ID token chấp nhận lệch đồng hồ trong giới hạn 30 giây. Khi FAP session vẫn dùng được, CLI tiếp tục gọi operation thực tế. Thời hạn FEID không được suy thành thời hạn FAP `authenKey`.

Nếu xác minh ID token thất bại, hãy đăng nhập lại bằng `login --force`. Có thể thử `refresh` khi lỗi JWKS đã được xử lý. `expires_in` vắng nghĩa là thời hạn chưa biết. Nếu refresh không trả refresh token mới, CLI giữ token trước đó. ID token trả về luôn phải có `exp` hợp lệ.

## Timeout và file trên máy

`--timeout` ưu tiên hơn `MYFAP_TIMEOUT` và áp dụng cho discovery, JWKS, token exchange/refresh, handshake cùng API dữ liệu. Cấu hình này không đổi thời gian chờ trình duyệt 120 giây. Xem [mặc định theo operation](Example.md#điều-chỉnh-timeout-http).

Session là JSON chứa credential trên máy và không được mã hóa. CLI tạo file tạm cùng thư mục, flush/fsync rồi thay thế atomic. Trên Unix, file được đặt quyền `0600`; trên Windows, quyền truy cập phụ thuộc ACL của thư mục tài khoản.

Logout xóa session và dọn `<tên-session>.lock` khi có thể xóa an toàn. Trên Windows, handle của process khác có thể ngăn xóa sidecar; khi đó CLI giữ file khóa để bảo toàn đồng bộ. File này không chứa token và không nên xóa thủ công khi CLI đang chạy.

Giữ session, file xuất dữ liệu, HAR/SAZ và biến bí mật ngoài Git. `docs/` và `tasks/` chỉ thuộc repository, không nằm trong artifact PyPI. CI dùng dữ liệu giả; đăng nhập FEID và API thật được kiểm chứng thủ công với session tạm riêng.

`logout` không parse nội dung session, nên vẫn dọn được file JSON hỏng. CLI chỉ xóa file thường sau khi lấy lock và kiểm tra lại đường dẫn; symlink, reparse point và thư mục đều bị từ chối.
