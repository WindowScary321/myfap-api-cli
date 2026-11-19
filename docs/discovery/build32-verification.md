# Đồng bộ hợp đồng myFAP 2.0.7 — build 32

CLI được đối chiếu ngày 18/11/2026, lấy commit `0d862be4fb5e3c6b02a7f3708333aeb51b0d9b33` làm mốc.
Báo cáo ghi riêng bằng chứng tĩnh, traffic của app và kết quả nghiệm thu CLI sau sửa.
Quy tắc chọn API giữ nguyên: session mới dùng v2; session cũ thiếu version được hiểu là v1.

## Hợp đồng thay đổi

Năm GET v2 dưới đây chỉ gửi `CampusCode`, `rollNumber` trong query, bỏ `Authen`:

| Command | Operation | Bằng chứng tĩnh build 32 | Fiddler LiveTraffic của app | CLI sau sửa, v2/HN |
|---|---|---|---|---|
| `other profile` | `CheckUpdateProfile` | fn#7514 | #350: HTTP 200, data boolean | Exit 0, HTTP/body 200, data boolean |
| `marks --summary` | `GetSemesterMark` | fn#7538 | Chưa quan sát được request | Exit 0, HTTP/body 200, data list |
| `applications` | `GetApplication` | fn#7594 | #327: HTTP 200, data list rỗng | Exit 0, HTTP/body 200, data list |
| `other feedback` | `CheckOpenFeedBack` | fn#7598 | #351: HTTP 200, data boolean | Exit 0, HTTP/body 200, data boolean |
| `other notification` | `GetNotificationByRoll` | fn#7614 | #296: HTTP 200, data list có phần tử | Exit 0, HTTP/body 200, data list |

Bytecode cũng xác nhận `GetNotificationByDonor` (fn#7622) bỏ query `Authen`;
CLI vẫn chưa hỗ trợ donor. `AddRate` (fn#7606) tiếp tục giữ `Authen`
trong query POST và chưa được CLI hỗ trợ.

Nguồn trong workspace phân tích: `new-fap/analysis-32/modules/module_604.js`
và `new-fap/analysis-32/index.android.disasm.txt`. APK base build 32 có SHA-256
`98025a7d21259249cb8b750432ab2aa6c0f3e3cdb2ee9975ffc8a2c62ad6bfa4`;
bundle Hermes có SHA-256 `490bda4349c4d8e1cc2ed6a6e31519e4ed4f9b6214847f1933000a8134a5961a`.
Các tệp phân tích này không nằm trong repo hoặc package CLI.

## Header, chữ ký và giới hạn quan sát

- Bốn request quan sát qua Fiddler có header `Authorization`, `Checksum`, `ClientCode`,
  `CampusCode`; không có `X-Signature`. Checksum có timestamp và padding `%3d`,
  không thấy double-encode `%253d`.
- Theo bytecode và signer của CLI, Authorization là `Bearer <credential>`.
  Checksum dùng HMAC-SHA256 trên `<credential>MyFAP<timestamp>`, chuyển kết quả
  sang Base64, đổi padding `=` thành `%3d` đúng một lần rồi nối `:<timestamp>`.
  Query không tham gia HMAC này.
- Fiddler MCP ẩn Authorization và body `code`, nên HTTP 200 chưa đủ để xác nhận
  body code 200 hay kiểm tra trực tiếp giá trị credential/HMAC.
- Traffic của app cho thấy request không có query `Authen` đã nhận HTTP 200.
  Chưa có thử nghiệm đối chứng để biết backend có từ chối query thừa hay không.
- Các session #649 (`GetStudentMark`) và #632 (`GetMarkByCourse`) là route khác;
  chúng không thay thế bằng chứng live cho `GetSemesterMark`.

## Chính sách CLI và nghiệm thu

CLI dùng FAP key của binding v2 cho cả Bearer và Checksum trên năm GET,
kể cả sau refresh. Wrapper `GetSemesterMark` của APK gọi helper mà không
truyền credential. CLI giữ chính sách authenticated-read đã được kiểm chứng
ở các lượt đọc trước; không dùng credential rỗng hoặc thử unauth rồi fallback.
V1, OAuth, session, reader summary và giới hạn retry vẫn giữ nguyên.

Regression dựng request bằng Requests, dùng HTTP giả và credential tổng hợp.
Các test kiểm tra query không chứa key, header đổi sau refresh, v1 giữ query cũ
và output giữ kiểu boolean/list. Dữ liệu notification được tạo riêng cho test,
không sao chép response của tài khoản.

Ngày 18/11/2026, **5/5 command CLI** đã được nghiệm thu trên v2/HN bằng phiên FEID
mới và file session tạm. Mỗi command gửi một GET, query chỉ có `CampusCode`,
`rollNumber`, có Authorization và Checksum khớp credential/timestamp theo signer
CLI. Cả năm command exit 0, stdout là JSON hợp lệ, HTTP/body 200. Harness quan sát
request tại Requests, giữ nguyên request/response và gọi backend thật; không
phát lại capture hoặc dùng fixture thay backend. Kết quả thô chỉ được xử lý
trong RAM; metadata được lọc trước khi in. Logout exit 0, session và thư mục tạm đã được dọn.

Kết quả chỉ áp dụng cho một binding v2/HN, chưa xác nhận mọi campus,
tài khoản hoặc tình huống expiry/App Check. Refresh/retry sau sửa được kiểm tra
bằng HTTP giả; chưa thử gây lỗi có chủ ý trên backend thật. CLI đã gọi đúng
`GetSemesterMark`; Fiddler vẫn chưa ghi nhận route này từ app.

Kiểm thử local: 44 test liên quan đều đạt; toàn bộ suite có 437 test, 433 đạt/4 skip,
exit 0. Hai test mới kiểm tra URL của request và việc từ chối query Authen do caller đưa vào.
Regression URL thất bại ở cả năm operation trước sửa và đạt sau sửa.
Các bước build wheel/sdist, Twine strict, kiểm tra artifact và cài thử bằng pip đều
exit 0, dùng artifact mới trong thư mục tạm ngoài repo. Lượt kiểm tra trên dùng
package `0.2.0`; dependency và pipeline publish giữ nguyên. Bản cập nhật build 32
được chuẩn bị phát hành dưới version `0.2.1`.

Rating, push và feedback form/submit tiếp tục tạm hoãn, giữ các điều kiện về schema/ack.
Các finding v1 và TODO positive fee/survey vẫn mở. Báo cáo chỉ ghi metadata,
không kèm giá trị query, token, response thô, thông tin tài khoản hoặc đường dẫn máy cá nhân.
