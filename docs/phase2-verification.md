# Kiểm chứng Phase 2

Ngày kiểm tra: 16/10/2026. Branch: `feat/phase2-oauth-session`; [PR #5](https://github.com/WindowScary321/myfap-api-cli/pull/5) giữ draft.

## Offline và artifact

Windows/Python 3.9.25 và 3.11 cùng chạy 179 unittest: 176 pass, 3 skip. Các skip liên quan mode POSIX và quyền tạo symlink trên Windows; trường hợp reparse point có fixture riêng. Test lock dùng process riêng, test JWT dùng key/token sinh riêng trong bộ test. Không test nào cần tài khoản FEID hoặc session thật.

Regression bao phủ callback trùng/sai state/cancel/timeout, chữ ký và claim ID token, binding, session cũ, file hỏng, read retry, request ghi không retry, redirect, lưu token trước validation và lỗi handshake sau rotation. Test cũng chặn command đang chạy nhận nhầm session do process khác đổi tài khoản, campus hoặc version.

`uv build` tạo wheel/sdist version `0.2.0`; Twine strict và artifact validator đều pass. Hai artifact được cài bằng pip vào hai venv sạch ngoài checkout, sau đó chạy `pip check`, `myfap version` và `myfap --help`. Artifact không chứa `docs/`, `tasks/`, fixture, capture hoặc file session.

[CI của commit triển khai `8a369d3`](https://github.com/WindowScary321/myfap-api-cli/actions/runs/38895605533) đã pass toàn bộ 11 job: scope, bốn source job, build, bốn artifact job và ready. Matrix gồm Ubuntu/Windows × Python 3.9/3.11. Kết quả commit tài liệu cuối được cập nhật vào PR khi hoàn tất.

## Live với session tạm trước bổ sung QoL

Người dùng tự đăng nhập trên cửa sổ FEID. CLI dùng `--config` trỏ đến file tạm ngoài repository, không đọc trực tiếp thư mục session cá nhân. Output được giữ trong RAM và chỉ xuất các trường đã cho phép: tên operation, HTTP/body code, kiểu dữ liệu, kết quả validation và exit code. Không lưu URL chứa query, token, MSSV/email, raw response, lịch học hoặc điểm.

| Luồng/command | Kết quả |
|---|---|
| `login --force` | Discovery, token endpoint và JWKS HTTP 200; ID token qua validation; handshake HTTP 200/body 200, data list; exit 0 |
| `semesters` | Probe và request GetSemester HTTP 200/body 200; exit 0 |
| `news --stdout`, timeout 20 giây | Lỗi mạng/timeout; exit 1; không gọi token endpoint |
| `news --stdout`, timeout 60 giây | HTTP 200/body 201, data null; exit 1; không refresh |
| `other notification --stdout` | HTTP 200/body 201, data null; exit 1; không refresh |
| `refresh` | Token endpoint/JWKS HTTP 200; ID token refresh được trả và qua validation; handshake HTTP 200/body 200; exit 0 |
| `info student --stdout` sau refresh | Probe và GetStudentById HTTP 200/body 200, data list; stdout parse được JSON; exit 0 |
| `--campus HCM login` với tài khoản chỉ có APHL | Handshake thật HTTP 200/body 201; exit 1; không gọi request nghiệp vụ; nội dung session được so sánh trong RAM và không đổi |
| `--campus APHL login` sau lần HCM thất bại | Probe GetSemester HTTP 200/body 200; exit 0 |
| Fault injection timeout tại handshake sau refresh thật | Refresh token mới được server trả và persist trước lỗi; binding giữ nguyên, FAP đánh dấu cần xác thực lại, exit 1 |
| `semesters` sau khi bỏ fault handshake | Handshake lại HTTP 200/body 200 rồi GetSemester HTTP 200/body 200; exit 0; không exchange token lần hai |
| Console entry point `myfap.exe` | Chạy trực tiếp `semesters` và `info student --stdout`, exit 0; JSON hợp lệ |
| Console entry point `logout` | Xóa session tạm, exit 0 |

Các luồng cần trace operation chạy qua Typer app với tham số CLI thật và Requests thật; console entry point được chạy thêm bằng subprocess để xác minh đường gọi của bản cài editable. Login, đổi campus, token exchange và request phục hồi đều gọi server thật; riêng phép thử lỗi handshake chặn request trong bộ nhớ trước khi gửi, không thay token hay file session bằng dữ liệu giả. Lần mở trình duyệt đầu chưa có callback; lần đăng nhập sau đã hoàn tất. Hai lỗi body 201 vẫn thuộc backend/contract và được giữ là lỗi operation.

## Phần chưa xác nhận live

Đổi campus thất bại với HCM đã được kiểm chứng live và giữ nguyên APHL. Chưa xác nhận chuyển campus thành công vì tài khoản mẫu chỉ có APHL. Phục hồi sau handshake lỗi đã được kiểm bằng fault injection trên session thật; chưa quan sát server tự trả lỗi handshake. FEID trả `expires_in: 3600` khi refresh, nhưng FAP `authenKey` không có contract TTL; hết hạn FEID access token không đồng nghĩa FAP credential hết hạn. Vì vậy HTTP 401 tự refresh/retry mới chỉ có fixture, chưa có bằng chứng phiên thật tự hết hạn. Đổi API version hoàn tất khi có adapter v2 ở Phase 3.

Session cũ chưa có subject OIDC đã xác minh cần `login --force` trước khi refresh. File session vẫn là JSON chứa credential; xem [quy tắc lưu session](oauth-session.md#timeout-và-file-trên-máy). PR này không tạo tag, publish PyPI hoặc triển khai auto release.

## Kiểm chứng QoL trong PR #5

Sau khi bỏ probe `GetSemester`, thêm buffer 30 giây trước khi dùng FEID access token để handshake và dọn lock khi logout, Windows/Python 3.9 và 3.11 cùng chạy 191 test: 188 pass, 3 skip mỗi môi trường. Test số request dùng auth/client thật với HTTP giả; test biên thời hạn cố định đồng hồ; test cleanup dùng process riêng để giữ handle chờ và phát hiện hai khóa song song. POSIX được kiểm trong CI Ubuntu.

Đã đăng nhập mới bằng session tạm riêng và chạy Requests thật:

| Command | Trace sau QoL |
|---|---|
| `info student --stdout` | Chỉ GetStudentById HTTP 200/body 200; JSON hợp lệ, exit 0 |
| `semesters` | Chỉ một GetSemester HTTP 200/body 200; exit 0 |
| `login` với session đã lưu | Không phát sinh HTTP; exit 0 |
| `logout` | Exit 0; cả session tạm và `.lock` đều không còn |

Buffer 30 giây được kiểm bằng đồng hồ cố định, không sửa token thật để giả thời hạn. Buffer chỉ refresh sớm trước handshake/phục hồi binding; không kéo dài token hoặc suy thời hạn FAP từ FEID. Trên Windows, logout có thể giữ lock nếu process khác còn mở handle; hành vi này tránh phá đồng bộ giữa các process. Kết quả CI commit QoL được cập nhật qua comment PR.
