# Gate còn mở cho rating, push và feedback

Đây là danh sách bằng chứng cần bổ sung, **không phải các write command đã triển khai**. Không gửi mutation live, đăng ký token hoặc đánh giá thay người dùng để tự lấp khoảng trống. Phase 6 chưa hoàn tất chỉ vì nhóm read đã có code/CI.

## Request đã biết và phần còn thiếu

| Nhóm | Bằng chứng tĩnh đã có | Còn thiếu trước khi mở CLI |
|---|---|---|
| `AddRate` student | POST ở cả v1/v2; query rateid/rateValue/rateComment. V1 campusCode/Authen/checksum, signer rateid; v2 CampusCode/Authen và body `{}`. Caller kiểm code 200 rồi lấy data. UI có lựa chọn 1–5. | Positive rating item/kiểu ID và liên kết với binding; ý nghĩa acknowledgment data; validation comment và kết quả submit trùng/không rõ. Lượt live rating list v1 hiện rỗng, không có ID để kiểm submit. |
| `UpdateTokedevices` student | GET **ghi**, không phải read. V1 CampusCode/Email/tokendevice/checksum ký bằng email; v2 cùng query bỏ checksum và dùng FAP credential hiện tại trong header. | Ack response theo từng version; semantics thay thế/thêm registration; reader token-file an toàn và test confirmation/no-replay. Không có device token thật được thu thập trong lượt này. |
| Feedback list/form v2 | GET list: CampusCode/rollNumber. GET form thêm feedbackId; facade forward request. | Positive response shape, kiểu/nguồn ID, trạng thái/required fields. Chưa có CLI; không lấy tên route làm schema. |
| Feedback submit v2 | POST với query CampusCode/rollNumber; body được caller chuyển nguyên trạng. | Schema câu trả lời, quan hệ với form, required/choices/types, ack và duplicate-submit. Không mở generic `--input` nhận JSON tùy ý. |
| Donor/employee, donor push, server-code exchange | Inventory có caller/nhánh riêng; donor login v2 có stub, server-code exchange còn flag tắt trong app. | Luồng auth/capability và schema riêng. Không dùng student binding hoặc giả định request không credential được phép. |

Nguồn nội bộ workspace: `analysis/modules/module_550.js:484–521`, `module_599.js:458–483,601–678`, rating UI `module_2597.js:101–129`, push caller `762_fcmService.js:44–53`. Không sao chép khóa, bootstrap literal hoặc dữ liệu tài khoản từ các nguồn này vào repo.

## Không suy quá bằng chứng

- Code 200 là điều kiện transport của AddRate đã thấy trong caller; **ý nghĩa data và xác nhận nghiệp vụ** chưa được kiểm. Không nói hoàn toàn không biết ack transport, cũng không suy code 200 bảo đảm mọi thay đổi đã được ghi đúng.
- UI gợi ý comment cho rating dưới 4, nhưng bản decompile không thể hiện chắc chắn việc dừng sau cảnh báo. Không ghi đó là ràng buộc backend đã xác minh.
- HTTP GET của push không chứng minh idempotent. Timeout hoặc mất response có thể là kết quả không rõ; tuyệt đối không refresh-and-replay hoặc khuyên retry mù.
- Rating list v2 là stub nên giữ unsupported. Rating list v1 là endpoint thật trả list rỗng trong lượt live, không cung cấp bằng chứng cho kiểu item/ID hoặc khả năng submit.

## Cách bổ sung bằng chứng mà không đưa PII lên GitHub

1. Với read/list/form, dùng browser và session tạm được cho phép; chọn ID chỉ từ response thật thuộc binding hiện tại, không đoán ID hoặc role.
2. Với write, cần người dùng xác nhận **thao tác cụ thể và input cụ thể** trước; có thể đối chiếu một thao tác người dùng thực hiện trên app, không tự tạo dữ liệu ghi để thử.
3. Payload/token chỉ xử lý tại máy. Báo cáo chỉ giữ operation/method/HTTP/body code, tên trường/kiểu dữ liệu và kết quả xác minh, không giá trị ID, comment, token, identity, ảnh hay câu trả lời.
4. Fixture tạo lại bằng dữ liệu tổng hợp, không copy response/capture nguyên bản. Mỗi version có test exact query/body/signing identity và lỗi riêng.
5. Khi đủ contract mới mở capability: validate input → capability → preview không bí mật → confirmation/`--yes` → auth → một lần gửi. Cancel hoặc input lỗi không load/refresh session; 401/timeout/5xx/App Check không replay mutation.

Các gate là công việc còn mở, không bị bỏ khỏi scope âm thầm. Maintainer cần bổ sung bằng chứng hoặc chốt thay đổi phạm vi tường minh trước khi nghiệm thu Phase 6 và tiếp tục phát hành. Xem [checklist](phase6.md) và [coverage](phase6-coverage.md).
