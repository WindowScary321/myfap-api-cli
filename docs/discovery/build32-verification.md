# Đồng bộ hợp đồng myFAP 2.0.7 — build 32

Đối chiếu ngày 18/11/2026, từ baseline CLI `0d862be4fb5e3c6b02a7f3708333aeb51b0d9b33`.
Phần này phân biệt bằng chứng tĩnh, traffic app thật và nghiệm thu CLI sau thay đổi.
Quy tắc chọn API giữ nguyên: v2 cho session mới, session cũ thiếu version được hiểu là v1.

## Hợp đồng thay đổi

Năm GET v2 dưới đây dùng đúng query `CampusCode`, `rollNumber`, không có `Authen`:

| Command | Operation | Bằng chứng tĩnh build 32 | Fiddler LiveTraffic của app | CLI sau sửa, v2/HN |
|---|---|---|---|---|
| `other profile` | `CheckUpdateProfile` | fn#7514 | #350: HTTP 200, data boolean | Exit 0, HTTP/body 200, data boolean |
| `marks --summary` | `GetSemesterMark` | fn#7538 | Chưa quan sát được request | Exit 0, HTTP/body 200, data list |
| `applications` | `GetApplication` | fn#7594 | #327: HTTP 200, data list rỗng | Exit 0, HTTP/body 200, data list |
| `other feedback` | `CheckOpenFeedBack` | fn#7598 | #351: HTTP 200, data boolean | Exit 0, HTTP/body 200, data boolean |
| `other notification` | `GetNotificationByRoll` | fn#7614 | #296: HTTP 200, data list có phần tử | Exit 0, HTTP/body 200, data list |

Bytecode còn xác nhận `GetNotificationByDonor` (fn#7622) bỏ query `Authen`,
nhưng CLI chưa mở donor capability. `AddRate` (fn#7606) vẫn giữ `Authen`
trong query POST và tiếp tục unsupported.

Nguồn trong workspace phân tích: `new-fap/analysis-32/modules/module_604.js`
và `new-fap/analysis-32/index.android.disasm.txt`. APK base build 32 có SHA-256
`98025a7d21259249cb8b750432ab2aa6c0f3e3cdb2ee9975ffc8a2c62ad6bfa4`;
bundle Hermes có SHA-256 `490bda4349c4d8e1cc2ed6a6e31519e4ed4f9b6214847f1933000a8134a5961a`.
Các artifact phân tích không nằm trong repository/package CLI.

## Header, chữ ký và giới hạn quan sát

- Bốn request live trên có header `Authorization`, `Checksum`, `ClientCode`,
  `CampusCode`; không có `X-Signature`. Checksum có timestamp và padding `%3d`,
  không thấy double-encode `%253d`.
- Theo bytecode và signer CLI, Authorization là `Bearer <credential>`;
  Checksum là HMAC-SHA256 trên `<credential>MyFAP<timestamp>`, rồi Base64 và
  đổi padding `=` thành `%3d` đúng một lần, sau cùng nối `:<timestamp>`.
  Query không tham gia HMAC này.
- Fiddler MCP che Authorization và body `code`; không dùng HTTP 200 để suy ra
  body code 200 hoặc xác nhận trực tiếp giá trị credential/HMAC.
- Traffic app không có query `Authen` chứng minh request mới đã được gửi và
  nhận HTTP 200; chưa có thử nghiệm đối chứng cho việc backend từ chối query thừa.
- Các session #649 (`GetStudentMark`) và #632 (`GetMarkByCourse`) là route khác;
  chúng không thay thế bằng chứng live cho `GetSemesterMark`.

## Chính sách CLI và nghiệm thu

CLI giữ Bearer FAP key của binding v2 và Checksum ký cùng key cho cả năm GET,
kể cả sau refresh. Riêng wrapper `GetSemesterMark` của APK gọi helper không
truyền credential; CLI tiếp tục policy authenticated-read đã có bằng chứng
kiểm đọc lịch sử, không sao chép credential rỗng hoặc thử unauth rồi fallback.
V1, OAuth, session, reader summary và giới hạn retry giữ nguyên.

Regression dùng request thật đã prepare với HTTP giả, credential tổng hợp,
kiểm query không chứa key, header đổi sau refresh, v1 giữ query cũ và output
giữ kiểu boolean/list. Dữ liệu notification trong test được tạo mới, không
sao chép response tài khoản.

Ngày 18/11/2026 đã nghiệm thu đủ **5/5 command CLI** trên v2/HN bằng phiên FEID
mới và file session tạm. Mỗi command gửi một GET, query chỉ có `CampusCode`,
`rollNumber`, có Authorization và Checksum khớp credential/timestamp theo signer
CLI; exit 0, stdout parse được JSON, HTTP/body 200. Harness quan sát biên
Requests thật, không thay request/response, không phát lại capture hoặc dùng
fixture thay backend. Raw output chỉ được xử lý trong RAM; metadata được lọc
trước khi in. Logout exit 0, session và thư mục tạm đã được dọn.

Đây là nghiệm thu CLI trên một binding v2/HN, không chứng minh mọi campus,
tài khoản hoặc tình huống expiry/App Check. Refresh/retry sau sửa được phủ bằng
regression HTTP giả, chưa được gây lỗi có chủ ý trên backend thật. `GetSemesterMark`
đã được gọi đúng bằng CLI; việc chưa thấy route này trong traffic app vẫn giữ
nguyên là giới hạn quan sát của Fiddler.

Kiểm thử local: 44 test focused đạt; toàn suite 437 test, 433 đạt/4 skip,
exit 0. Hai test mới phủ URL đã prepare và từ chối query Authen do caller đưa vào.
Trước sửa, regression URL thất bại ở đủ năm operation; sau sửa đạt.
Build wheel/sdist, Twine strict, artifact validator và pip smoke install đều
exit 0 với artifact mới trong thư mục tạm ngoài repository. Version package
vẫn là `0.2.0`; không đổi dependency hoặc pipeline publish.

Rating, push và feedback form/submit tạm hoãn; không thay đổi các gate schema/ack.
Các finding v1 và TODO positive fee/survey vẫn mở. Tài liệu này không chứa
query có giá trị, token, raw response, thông tin tài khoản hoặc đường dẫn máy cá nhân.
