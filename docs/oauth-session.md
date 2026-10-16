# Đăng nhập và quản lý session

[Quay lại README](../README.md) · [Hướng dẫn phát triển](development.md)

## Đăng nhập mới

```sh
myfap login
myfap login --force
myfap --config ./local-state.json login --force
```

CLI mở Chrome, Edge hoặc Firefox để đăng nhập FEID. Mỗi lần đăng nhập dùng PKCE S256, state và nonce mới; thời gian chờ trên trình duyệt là 120 giây. CLI kiểm tra callback, chữ ký RS256 qua JWKS và các claim của ID token trước khi gọi FAP handshake. MSSV, email và loại tài khoản được lấy từ handshake, không suy ra bằng cách decode access token.

ID token có leeway 30 giây cho các claim thời gian `exp`, `iat` và `nbf` để chịu được lệch đồng hồ nhỏ. Token thiếu `exp`, thời gian sai kiểu hoặc giá trị không hữu hạn vẫn bị từ chối. Leeway không bỏ qua chữ ký, issuer, audience, subject, nonce hoặc `at_hash`.

`--force` mở lại trình duyệt kể cả khi đã có session. Nếu file JSON hỏng hoặc thiếu trường bắt buộc, đăng nhập thành công sẽ thay thế file đó. Khi đăng nhập thất bại, file cũ được giữ nguyên. Lỗi quyền truy cập hoặc đường dẫn không an toàn vẫn bị chặn.

Khi session cần đăng nhập lại hoặc binding cũ không được hỗ trợ, `myfap login` tự mở trình duyệt; không cần chạy lại với `--force`. Login mới chỉ kế thừa campus đã lưu, dùng luồng v1/student của Phase 2 dù file cũ có binding v2. Lệnh đọc vẫn từ chối session v2 trước HTTP; chỉ login thành công mới thay binding và credential cũ.

Campus được chọn theo thứ tự: option `--campus` → campus trong session → `APHL` khi chưa có session hợp lệ. Có thể đặt option trước command hoặc trong `login`:

```sh
myfap --campus APHL login --force
myfap login --campus APHL --force
```

Session gắn với campus, API version và loại tài khoản. Thay campus yêu cầu handshake lại trước khi gửi request dữ liệu; binding mới chỉ được lưu sau khi handshake thành công. Phase 2 hỗ trợ v1 và tài khoản student. Adapter v2 cùng option chọn version thuộc Phase 3.

## Dùng session cũ và refresh

Session cũ thiếu API version được hiểu là v1. CLI đọc và kiểm tra binding cục bộ khi nạp session; việc xác thực trên server diễn ra ở request dữ liệu thực tế, không gọi `GetSemester` chỉ để dò session. Session chưa có subject OIDC đã xác minh cần đăng nhập lại bằng `myfap login --force` trước khi refresh; CLI không dùng payload access token làm bằng chứng identity.

`GetSemester` chỉ được gọi khi chạy `semesters` hoặc khi lệnh cần tự chọn kỳ: `schedule`, `marks` không có `--courseid`, `exams`, `attendance`, `week-timetable`. Truyền `--semester` thì bỏ qua bước tra kỳ. Các lệnh như `info`, `news`, `applications`, `marks --courseid` và `other` gọi thẳng operation tương ứng.

```sh
myfap refresh
myfap --config ./local-state.json refresh
```

Lệnh đọc tự refresh rồi retry tối đa một lần khi nhận HTTP 401, hoặc khi API v1 trả body `code: 201` cùng message chính xác `Token invalid` trên 17 FAP read operation có `Authen`. Policy bao gồm kỳ học, news, feedback/profile, notification, học phí, subjects, lịch học/điểm/điểm danh, lịch thi, đơn từ và thông tin sinh viên/campus. Bốn operation cốt lõi đã được đối chiếu trực tiếp với caller APK; 13 operation còn lại được mở rộng theo yêu cầu QoL với cùng exact-message guard. `201` thiếu/sai message vẫn là lỗi operation; news/notification rỗng không refresh. Public bootstrap, tra tuần và survey không mang FAP `Authen` nên không tự refresh. Body `401` của v1, timeout, lỗi mạng, HTTP 403/5xx và App Check cũng không gây refresh. Request ghi không được tự retry.

Refresh giữ lock từ lúc đọc session đến khi lưu xong để hai process không rotate cùng token. Nếu process khác đã refresh cùng tài khoản và binding, CLI dùng session mới; nếu identity hoặc binding đã đổi, command dừng và yêu cầu chạy lại.

Refresh token mới được ghi atomic trước khi xác minh ID token và handshake tiếp theo. Nếu bước sau lỗi, file giữ token đã rotate và đánh dấu FAP cần xác thực lại. Khi ID token đã hợp lệ nhưng handshake lỗi tạm thời, lệnh tiếp theo thử handshake lại. Trước handshake hoặc phục hồi binding, access token đã hết hạn hoặc còn tối đa 30 giây sẽ được refresh sớm để bù thời gian request. Buffer refresh sớm này khác với leeway khi xác minh ID token: buffer tránh dùng access token sát hạn, leeway chấp nhận lệch đồng hồ trong giới hạn 30 giây. FAP session đang dùng được tiếp tục gọi operation thực tế; thời hạn FEID không được suy thành thời hạn FAP `authenKey`.

Nếu xác minh ID token thất bại, đăng nhập lại bằng `login --force`, hoặc thử `refresh` khi lỗi JWKS đã được xử lý. Trường `expires_in` vắng có nghĩa thời hạn chưa biết; refresh không trả refresh token mới thì giữ token trước đó. ID token được trả về luôn phải có `exp` hợp lệ.

## Timeout và file trên máy

`--timeout` ưu tiên hơn `MYFAP_TIMEOUT` và áp dụng cho discovery, JWKS, token exchange/refresh, handshake cùng API dữ liệu. Cấu hình này không đổi thời gian chờ trình duyệt 120 giây. Xem [mặc định theo operation](Example.md#điều-chỉnh-timeout-http).

Session vẫn là JSON chứa credential trên máy, không được mã hóa. CLI dùng file tạm cùng thư mục, flush/fsync rồi thay thế atomic; trên Unix đặt quyền file `0600`. Trên Windows, quyền truy cập phụ thuộc ACL của thư mục tài khoản. Logout xóa session và dọn file khóa `<tên-session>.lock` khi có thể xóa an toàn. Trên Windows, handle của process khác có thể ngăn xóa sidecar; khi đó file khóa được giữ để bảo toàn đồng bộ. File này không chứa token và không nên xóa thủ công khi CLI đang chạy.

Giữ session, file xuất dữ liệu, HAR/SAZ và biến bí mật ngoài Git. `docs/` và `tasks/` chỉ thuộc repository, không nằm trong artifact PyPI. CI dùng dữ liệu giả; đăng nhập FEID và API thật được kiểm chứng thủ công với session tạm riêng.

`logout` không parse nội dung session, nên vẫn dọn được file JSON hỏng. CLI chỉ xóa file thường sau khi lấy lock và kiểm lại đường dẫn; symlink, reparse point và thư mục vẫn bị từ chối.
