# Đăng nhập và quản lý session

[Quay lại README](../README.md) · [Hướng dẫn phát triển](development.md)

## Đăng nhập mới

```sh
myfap login
myfap login --force
myfap --config ./local-state.json login --force
```

CLI mở Chrome, Edge hoặc Firefox để đăng nhập FEID. Mỗi lần đăng nhập dùng PKCE S256, state và nonce mới; thời gian chờ trên trình duyệt là 120 giây. CLI kiểm tra callback, chữ ký RS256 qua JWKS và các claim của ID token trước khi gọi FAP handshake. MSSV, email và loại tài khoản được lấy từ handshake, không suy ra bằng cách decode access token.

`--force` mở lại trình duyệt kể cả khi đã có session. Nếu file JSON hỏng hoặc thiếu trường bắt buộc, đăng nhập thành công sẽ thay thế file đó. Khi đăng nhập thất bại, file cũ được giữ nguyên. Lỗi quyền truy cập hoặc đường dẫn không an toàn vẫn bị chặn.

Campus được chọn theo thứ tự: option `--campus` → campus trong session → `APHL` khi chưa có session hợp lệ. Có thể đặt option trước command hoặc trong `login`:

```sh
myfap --campus APHL login --force
myfap login --campus APHL --force
```

Session gắn với campus, API version và loại tài khoản. Thay campus yêu cầu handshake lại trước khi gửi request dữ liệu; binding mới chỉ được lưu sau khi handshake thành công. Phase 2 hỗ trợ v1 và tài khoản student. Adapter v2 cùng option chọn version thuộc Phase 3.

## Dùng session cũ và refresh

Session cũ thiếu API version được hiểu là v1. Nếu FAP credential còn hợp lệ, CLI tiếp tục dùng cho các lệnh đọc. Session chưa có subject OIDC đã xác minh cần đăng nhập lại bằng `myfap login --force` trước khi refresh; CLI không dùng payload access token làm bằng chứng identity.

```sh
myfap refresh
myfap --config ./local-state.json refresh
```

Lệnh đọc chỉ tự refresh rồi retry tối đa một lần khi nhận HTTP 401 rõ ràng. Body `201` hoặc `401` của v1 là lỗi operation; chúng không tự gây refresh hay logout. Timeout, lỗi mạng, HTTP 403/5xx và App Check cũng không gây refresh. Request ghi không được tự retry.

Refresh giữ lock từ lúc đọc session đến khi lưu xong để hai process không rotate cùng token. Nếu process khác đã refresh cùng tài khoản và binding, CLI dùng session mới; nếu identity hoặc binding đã đổi, command dừng và yêu cầu chạy lại.

Refresh token mới được ghi atomic trước khi xác minh ID token và handshake tiếp theo. Nếu bước sau lỗi, file giữ token đã rotate và đánh dấu FAP cần xác thực lại. Khi ID token đã hợp lệ nhưng handshake lỗi tạm thời, lệnh tiếp theo thử handshake lại; nếu access token đã hết hạn thì refresh trước. Nếu xác minh ID token thất bại, đăng nhập lại bằng `login --force`, hoặc thử `refresh` khi lỗi JWKS đã được xử lý. Trường `expires_in` vắng có nghĩa thời hạn chưa biết; refresh không trả refresh token mới thì giữ token trước đó. ID token được trả về luôn phải có `exp` hợp lệ.

## Timeout và file trên máy

`--timeout` ưu tiên hơn `MYFAP_TIMEOUT` và áp dụng cho discovery, JWKS, token exchange/refresh, handshake cùng API dữ liệu. Cấu hình này không đổi thời gian chờ trình duyệt 120 giây. Xem [mặc định theo operation](Example.md#điều-chỉnh-timeout-http).

Session vẫn là JSON chứa credential trên máy, không được mã hóa. CLI dùng file tạm cùng thư mục, flush/fsync rồi thay thế atomic; trên Unix đặt quyền file `0600`. Trên Windows, quyền truy cập phụ thuộc ACL của thư mục tài khoản. File khóa `<tên-session>.lock` có thể còn sau logout; file này không chứa token và không nên xóa khi CLI đang chạy.

Giữ session, file xuất dữ liệu, HAR/SAZ và biến bí mật ngoài Git. `docs/` và `tasks/` chỉ thuộc repository, không nằm trong artifact PyPI. CI dùng dữ liệu giả; đăng nhập FEID và API thật được kiểm chứng thủ công với session tạm riêng.
