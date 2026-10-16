# Sửa lỗi sau review Phase 2

Review ban đầu dựa trên PR #5 ở commit `9573617`. Trong lúc sửa, branch được fast-forward theo merge `937ae7c` để giữ thay đổi README và hướng dẫn phát triển mới từ main. Không sửa branch tài liệu riêng hoặc đọc thư mục session cá nhân.

## Kết luận từng nhận định

| Nhận định | Kết luận và thay đổi |
|---|---|
| V1 không tự refresh với body 201 | Có gap. Mở rộng expiry cho mọi FAP read operation có `Authen` khi cả code 201 và message `Token invalid` khớp; không áp mọi 201 |
| `login --force` bị session v2 cũ chặn | Đúng. Login mới chỉ kế thừa campus, dùng v1/student trừ tham số rõ ràng; session cũ giữ nguyên đến khi login mới thành công |
| `login` bắt người dùng gõ thêm `--force` khi binding cần xác thực lại | Đúng. CLI chuyển từ `SessionBindingError` sang mở trình duyệt; lỗi mạng hoặc lỗi khác không bị che bằng login mới |
| ID token thiếu clock skew tolerance | Đúng. Thêm leeway 30 giây cho exp/iat/nbf, giữ chữ ký và các claim khác; buffer access token vẫn riêng |
| Logout không xóa được JSON hỏng | Đúng. Xóa file thường dưới lock mà không parse JSON, kiểm lại đường dẫn trước unlink |
| Attendance gọi mạng trước khi báo thiếu cờ | Đúng. Kiểm tra cặp cờ trước khi tạo auth, nạp session hoặc tra kỳ |
| Dependency pkce không còn được dùng | Đúng. Bỏ khỏi pyproject và uv.lock; PKCE S256 vẫn dùng secrets/hashlib |

## Bằng chứng cho contract 201

Nghiên cứu `analysis/auth-var-v1-v2-comparison.md`, mục 6.1, mô tả v1 dùng body 201 cho hết phiên nhưng chưa chỉ rõ điều kiện theo operation. Đối chiếu caller APK trong workspace xác nhận app kiểm đồng thời `code == 201` và `message == "Token invalid"`:

| Operation đang có trong CLI | Nguồn phân tích APK cục bộ |
|---|---|
| GetActivityStudent | `analysis/modules/module_1299.js:719-729` |
| GetStudentMark | `analysis/modules/module_1302.js:331-340` |
| GetStudentAttendances | `analysis/modules/module_1332.js:385-394` |
| GetActivityStudentByWeek | `analysis/modules/module_2598.js:746-756` |

Caller GetBalance cũng có điều kiện này tại `analysis/modules/module_825.js:409-417`, nhưng CLI chưa có operation đó nên không thêm capability hoặc policy chưa dùng. Những nguồn phân tích trên nằm ngoài repository CLI.

News/notification đã có bằng chứng live trả 201 khi cùng session vẫn đọc được dữ liệu. Policy mới chỉ refresh khi message chính xác `Token invalid`; body 201 rỗng của hai route này vẫn là lỗi operation. GetSemester và các FAP read route khác được mở rộng theo cùng guard. Public bootstrap, tra tuần, survey, operation lạ, thao tác ghi và handshake không thuộc allowlist FAP read. Body `201` thiếu hoặc sai message vẫn là lỗi operation. HTTP 401 tiếp tục là tín hiệu expiry rõ ràng cho request đọc.

Allowlist được mở rộng từ bốn lên 17 operation theo yêu cầu QoL của maintainer. `AUTHENTICATED_READ_OPERATIONS` là nguồn dùng chung cho phân loại lỗi và policy retry, tránh danh sách lệch nhau. Bốn caller APK ở bảng trên là bằng chứng trực tiếp; expiry live của 13 operation bổ sung chưa được quan sát trong lượt này.

## Kiểm chứng

Đã tái hiện lỗi bằng fixture trước sửa: login v2 bị chặn, logout không parse được JSON, ID token lệch đồng hồ 0,5 giây bị từ chối, attendance gọi auth trước kiểm tra cờ và body 201 `Token invalid` không kích hoạt refresh.

Regression sau sửa bao gồm login/refresh với JWT ký RSA thật trong bộ test; biên leeway; claim sai kiểu/không hữu hạn; giữ bytes session cũ khi login thất bại; logout corrupt/missing/symlink/reparse; retry một lần với key/checksum mới; second expiry; refresh thất bại; operation/message không khớp và App Check/403/5xx không refresh. CLI schedule vẫn giữ stdout chỉ chứa JSON sau refresh.

Windows/Python 3.9.25 và 3.11 đều chạy 214 test: 210 pass, 4 skip mỗi môi trường theo quyền/mode POSIX hoặc symlink. Console entry point được chạy trực tiếp với file tạm giả: logout JSON hỏng exit 0, session/lock đều được xóa; attendance thiếu `--classname` exit 1, stdout rỗng, báo đúng cờ và không tạo auth lock. Review độc lập theo hai trục Standards/Spec không còn finding sau sửa tài liệu.

Các test xác minh contract APK và xử lý CLI, không chứng minh server live tự hết phiên trả envelope nào trong một phiên cụ thể. Không sửa token thật hoặc tạo lỗi server để lấy bằng chứng. Kết quả test, artifact và CI của commit cuối được cập nhật qua comment PR; PR tiếp tục giữ draft.
