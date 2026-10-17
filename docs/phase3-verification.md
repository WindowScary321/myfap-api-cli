# Kiểm chứng Phase 3

Baseline là `238c718` trên main, sau PR #5. Phase 3 được triển khai tại [PR #7](https://github.com/WindowScary321/myfap-api-cli/pull/7), giữ draft và version package `0.2.0`.

## Offline

Regression dùng credential giả, file session tạm và HTTP mock; không đọc thư mục session cá nhân. Bộ test giữ toàn bộ v1 và bổ sung:

- Header/body/query v2 cho hai bootstrap, handshake, GetSemester và schedule; signing identity đúng theo từng bước.
- HMAC-SHA256 dùng UTF-8 key, timestamp cố định và padding `%3d`; ngăn decode khóa hex hoặc encode padding hai lần.
- Precedence option → session → v1; state CLI không bị lẫn giữa các lần gọi. Public bootstrap đọc version mà không restore identity hoặc handshake.
- Đổi binding v1/v2 hai chiều; handshake lỗi giữ binding cũ; không gửi FAP key của version cũ vào request dữ liệu version mới. Cùng campus/account không được âm thầm đổi MSSV/email.
- Rotation persist trước validation/handshake, retry đọc tối đa một lần với key/chữ ký mới, App Check/403/5xx và route unsupported không gây fallback.
- Capability CLI được kiểm trước tra kỳ/tuần cho command chưa hỗ trợ; survey giữ contract riêng.

Windows/Python 3.9.25 và 3.11 chạy 261 test mỗi môi trường: 257 pass, 4 skip theo quyền/mode POSIX hoặc symlink. Build version `0.2.0` qua Twine strict và artifact validator; wheel/sdist được cài bằng pip vào hai venv sạch, `pip check`, version và help đều pass. Review độc lập không còn finding runtime; phần contract matrix đã bổ sung account/path/read-write/retry sau review.

## Live với session tạm

Ngày 17/10/2026, người dùng tự đăng nhập FEID và xác nhận tài khoản mẫu thuộc Hà Nội/Hòa Lạc. Output chỉ được giữ trong RAM và xuất metadata: operation, method, HTTP/body code, kiểu data, kết quả ID token validation, exit code hoặc tính hợp lệ JSON. Không ghi token, MSSV/email, query có credential, lịch học, điểm hay raw response vào repository.

| Phép thử | Kết quả |
|---|---|
| V2 GetAllActiveCampus | POST HTTP 200/body 200, data list |
| V2 GetApiActive gọi rõ để chẩn đoán | POST HTTP 200/body 200, data bool |
| Login v2 với campus APHL | FEID discovery/token/JWKS HTTP 200, ID token hợp lệ; handshake HTTP 200/body 401, exit 1; không lưu session v2 |
| Lấy mã campus từ bootstrap v2 | Có CT, DN, HCM, HN, QN; HN là Cơ sở Hà Nội, không có APHL |
| Login v2 với HN sau xác nhận của người dùng | FEID discovery/token/JWKS HTTP 200, ID token hợp lệ; handshake POST HTTP 200/body 200, data list, exit 0 |
| `--api-version v2 semesters` | Một GetSemester GET HTTP 200/body 200, data list, exit 0 |
| `--api-version v2 schedule --stdout` | GetSemester và GetActivityStudent GET HTTP 200/body 200, stdout JSON hợp lệ, exit 0 |
| `schedule --stdout` cùng session, bỏ option version | Chọn v2 đã lưu; hai operation trên HTTP 200/body 200, JSON hợp lệ, exit 0 |
| `--api-version v2 marks --stdout` | Exit 1, không phát sinh HTTP vì chưa hỗ trợ |
| Logout session tạm | Exit 0; session và sidecar lock đều được xóa |

Lần handshake APHL thất bại và lần HN thành công được giữ thành hai kết quả riêng. CLI không tự đổi campus, không đổi version hoặc thêm token App Check để vượt lỗi. Không kết luận mọi body 401 đều do campus; ở lần này mã campus đã được kiểm tra lại bằng bootstrap và người dùng xác nhận.

## Giới hạn

Live mới xác nhận bootstrap, login mới, kỳ học, schedule JSON và lựa chọn version từ session với một campus. Đổi version hai chiều, refresh v2 và các nhánh lỗi có fixture, chưa xác nhận live riêng trong lượt này. Chưa có bằng chứng một session v2 tự hết hạn. Khả năng import lịch ICS và parity các command còn lại thuộc Phase 4.

Kết quả Python 3.9/3.11, build, Twine, artifact validator, pip smoke và CI của commit cuối được cập nhật qua comment PR. Không có tag, GitHub Release hoặc publish PyPI trong Phase 3.
