# Đăng nhập và quản lý session

[Quay lại README](../README.md) · [Hướng dẫn phát triển](development.md)

## Đăng nhập mới

```sh
myfap login --campus HN
myfap login --campus HN --force
myfap --config ./local-state.json --campus HN login --force
```

CLI mở Chrome, Edge hoặc Firefox để đăng nhập FEID. Mỗi lần đăng nhập tạo PKCE S256, state và nonce mới, với thời gian chờ trên trình duyệt là 120 giây. Trước khi gọi FAP handshake, CLI kiểm tra callback, chữ ký RS256 qua JWKS và các claim của ID token. MSSV, email và loại tài khoản lấy từ handshake; CLI không suy ra chúng bằng cách decode access token.

Các claim thời gian `exp`, `iat` và `nbf` của ID token có leeway 30 giây để chịu được lệch đồng hồ nhỏ. Token thiếu `exp`, có thời gian sai kiểu hoặc giá trị không hữu hạn vẫn bị từ chối. Leeway không bỏ qua kiểm tra chữ ký, issuer, audience, subject, nonce hay `at_hash`.

`myfap login` tự mở lại trình duyệt khi file session hỏng JSON hoặc có cấu trúc sai, như thiếu campus hay API version không hợp lệ. `--force` mở lại trình duyệt kể cả khi đã có session dùng được. File cũ chỉ được thay sau khi đăng nhập thành công; nếu hủy hoặc handshake thất bại, nội dung cũ được giữ nguyên. Lỗi mạng, quyền truy cập hoặc đường dẫn không an toàn vẫn được báo, không bị coi là lỗi cấu trúc session.

Session student phải có cả `mssv` và `email` là chuỗi không rỗng, kể cả với session v1/v2 cũ. Trường thiếu, `null`, sai kiểu hoặc rỗng bị chặn trước request dữ liệu; `login` thường mở lại luồng đăng nhập. Metadata OAuth cũ vẫn có thể thiếu nếu FAP session còn dùng được.

Khi session cần đăng nhập lại hoặc binding cũ không được hỗ trợ, `myfap login` tự mở trình duyệt nên không cần chạy lại với `--force`. Login mới kế thừa campus và API version đã lưu nếu bạn không chỉ định option tương ứng; luồng FEID hiện hỗ trợ tài khoản student trên v1 và v2 trong phạm vi adapter của từng version. Binding và credential cũ chỉ được thay sau khi login thành công.

CLI chọn campus theo thứ tự: `--campus`, campus trong session, rồi `APHL` cho login v1 mới. Với v2, profile mới hoặc session lưu `APHL` cần chỉ định `--campus`. CLI kiểm tra trước khi mở trình duyệt, handshake hoặc refresh; `login` có và không có `--force` đều áp dụng quy tắc này. Session lưu mã khác `APHL` vẫn được kế thừa. Các option chung `--campus`, `--config`, `--timeout` và `--api-version` có thể đặt trước hoặc sau command, kể cả lệnh con:

```sh
myfap --api-version v1 --campus APHL login --force
myfap login --api-version v1 --campus APHL --force
myfap --api-version v2 --campus HN login --force
```

Session gắn với campus, API version và loại tài khoản. Đổi campus hoặc version cần handshake lại trước request dữ liệu; binding mới chỉ được lưu sau handshake thành công. CLI chọn version theo `--api-version`, `MYFAP_API_VER`, session, rồi mặc định v2; session cũ thiếu trường version vẫn được hiểu là v1. V2 chỉ gửi các operation đã nằm trong capability của adapter; route chưa hỗ trợ bị chặn trước HTTP. Xem [phạm vi API version](api-versions.md) để biết giới hạn hiện tại.

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

Nếu FEID từ chối refresh bằng `invalid_grant`, CLI lưu `fap_needs_reauth=true` và `oidc_validated=false` dưới lock hiện có, giữ credential và binding để tránh ghi mất dữ liệu. Lệnh `login` kế tiếp mở lại browser mà không cần `--force`. Timeout hoặc lỗi mạng trước khi nhận token không tự đặt hai cờ này; lỗi storage vẫn đi qua nhánh báo lỗi an toàn. Việc lưu token đã rotate khi lỗi xảy ra sau token exchange vẫn theo quy tắc trên.

Trước handshake hoặc phục hồi binding, access token đã hết hạn hoặc còn tối đa 30 giây sẽ được refresh sớm để bù thời gian request. Buffer này tránh dùng access token sát hạn; leeway ID token chấp nhận lệch đồng hồ trong giới hạn 30 giây. Khi FAP session vẫn dùng được, CLI tiếp tục gọi operation thực tế. Thời hạn FEID không được suy thành thời hạn FAP `authenKey`.

Nếu xác minh ID token thất bại, hãy đăng nhập lại bằng `login --force`. Có thể thử `refresh` khi lỗi JWKS đã được xử lý. `expires_in` vắng nghĩa là thời hạn chưa biết. Nếu refresh không trả refresh token mới, CLI giữ token trước đó. ID token trả về luôn phải có `exp` hợp lệ.

## Timeout và file trên máy

`--timeout` ưu tiên hơn `MYFAP_TIMEOUT` và áp dụng cho discovery, JWKS, token exchange/refresh, handshake cùng API dữ liệu. Cấu hình này không đổi thời gian chờ trình duyệt 120 giây. Xem [mặc định theo operation](Example.md#điều-chỉnh-timeout-http).

Session là JSON chứa credential trên máy và không được mã hóa. CLI tạo file tạm cùng thư mục, flush/fsync rồi thay thế atomic. Trên Unix, file được đặt quyền `0600`; trên Windows, quyền truy cập phụ thuộc ACL của thư mục tài khoản.

Logout xóa session và dọn `<tên-session>.lock` khi có thể xóa an toàn. Trên Windows, handle của process khác có thể ngăn xóa sidecar; khi đó CLI giữ file khóa để bảo toàn đồng bộ. File này không chứa token và không nên xóa thủ công khi CLI đang chạy.

Giữ session, file xuất dữ liệu, HAR/SAZ và biến bí mật ngoài Git. `docs/` và `tasks/` chỉ thuộc repository, không nằm trong artifact PyPI. CI dùng dữ liệu giả; đăng nhập FEID và API thật được kiểm chứng thủ công với session tạm riêng.

`logout` không parse nội dung session, nên vẫn dọn được file JSON hỏng. CLI chỉ xóa file thường sau khi lấy lock và kiểm tra lại đường dẫn; symlink, reparse point và thư mục đều bị từ chối.
