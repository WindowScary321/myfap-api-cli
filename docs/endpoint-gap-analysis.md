# Phân tích khoảng trống endpoint giữa APK myFAP và CLI

Đối chiếu ngày 24/10/2026 giữa inventory 82 route của APK 2.0.6 build 31 (`analysis/endpoints.md` của workspace phân tích, nguồn `analysis/modules/*.js`) và tập operation adapter CLI. Mục đích: xác định CLI còn thiếu gì, thiếu có chủ đích hay chưa biết, và endpoint nào đủ bằng chứng để mở.

Quy tắc riêng tư: mọi probe live dưới đây là GET/POST chỉ đọc bằng session thật trên máy cá nhân; output raw chỉ xử lý cục bộ và bị xóa sau khi trích metadata. Tài liệu này chỉ chứa metadata đã lọc (status, body code, dạng dữ liệu, tên khóa), không chứa token, identity, giá trị trường hay raw response.

## Kết luận tổng quan

- App có 82 route: 37 v1, 40 proxy v2, 1 survey, 4 OTA, 1 HEAD connectivity.
- CLI hỗ trợ **toàn bộ operation đọc student của cả v1 lẫn v2** (26+1 read v2 sau đợt này, 29 route v1 tương ứng), survey riêng và handshake FEID, **ngoại trừ** `GetStudentFeedbackForm` (tiếp tục gate có chủ đích chờ `feedbackId` thực tế từ tài khoản có feedback mở, không đoán ID). Không có route đọc student khả dụng nào khác của app bị bỏ sót.
- Sau đợt mở rộng này, adapter v2 có **31 operation**: 27 đọc, 3 bootstrap (`GetAllActiveCampus`, `GetApiActive`, `GetVersion`) và 1 handshake.

## Nhóm A — Read student từng gate, đã đủ bằng chứng và mở trong đợt này

| Operation | Bằng chứng đóng gate (24/10/2026) | Kết quả triển khai |
|---|---|---|
| `GetStudentFeedbacks` (v2-only, `module_599.js:601-623`) | Query đúng là `{CampusCode, rollNumber}` — **không có `Authen` trong query** (đối chiếu bytecode dòng 613, sửa lại ghi chú inventory cũ); credential đi header Bearer. Live: HTTP/body 200, data list rỗng với policy Bearer FAP key | Mở `myfap other feedbacks`; envelope đã xác nhận, **item schema chưa có positive** (danh sách rỗng) — giữ nhãn unverified như rating list |
| `GetVersion` (`module_599.js:659-670`) | Caller APK dùng GET nhưng proxy trả **405** với GET; **POST body rỗng** được chấp nhận với cả bootstrap Bearer lẫn FAP key Bearer (200, data chuỗi ngắn); **route v1 đã chết (HTTP 404)** | Mở cho `doctor --api-version v2 --online`: report thêm `backend_version`; `myfap version` vẫn chỉ đọc package version |
| `GetStudentFeedbackForm` (`module_599.js:624-637`) | Query `{CampusCode, rollNumber, feedbackId}`; cần `feedbackId` thật từ danh sách — danh sách đang rỗng nên **không đoán ID** theo quy tắc plan | Vẫn gate; chờ tài khoản có feedback đang mở |

## Nhóm B — Thao tác ghi đang gate có chủ đích

`AddRate` (rating submit, checksum `rateid` v1 / query `Authen` v2), `UpdateTokedevices` (push register, v1 ký bằng email, token chỉ đọc từ file), `SubmitStudentFeedback` (body runtime). Theo quyết định ghi tại [todo](../tasks/todo.md), tài khoản hiện tại không thể xác minh ack/schema thao tác ghi; gate và trình tự validate → preview → confirmation → auth giữ nguyên.

## Nhóm C — Out of scope theo thiết kế CLI

| Nhóm | Route | Lý do không tích hợp |
|---|---|---|
| Donor/employee | `GetNotificationByDonor`, `GetTokenWithEmp`, `UpdateTokenDonor` | CLI giới hạn luồng student theo plan |
| Login thay thế | `AuthenticationByGoogleAccessToken` (v1 GET/v2 POST), `AuthenticationByUsername` (v1) | CLI chọn luồng FEID; nhánh username đặt password trong query URL — không tái hiện |
| FEID server-code | `AuthenticationByFeIdCode` | Chính app tắt bằng flag `FEID_SERVER_CODE_EXCHANGE=false` |
| Hạ tầng OTA | `codepushota.ptudev.net` check-update/report-crash/report-failure/report-success | Hạ tầng cập nhật app, không phải dữ liệu FAP |
| Connectivity | HEAD `clients3.google.com/generate_204` | NetInfo của app |

## Nhóm D — Tính năng ngoài API (Linking.openURL)

App mở trình duyệt cho: trang hóa đơn `dng.fpt.edu.vn/Invoice?StudentId=…`, file đính kèm tin `fap.fpt.edu.vn/temp/{fileAttach}`, link Meet. CLI đã giữ nguyên các trường tương ứng trong JSON output (`meetURL`, `fileAttach`); có thể thêm lệnh QoL in URL hóa đơn nếu cần, không phải route API.

## Bằng chứng thí nghiệm transport liên quan

Thí nghiệm ngày 24/10/2026 (chi tiết tại [coverage Phase 6](phase6-coverage.md#thí-nghiệm-transport-có-kiểm-soát-24102026)) cho thấy proxy chỉ chấp nhận cặp Bearer FAP key + Checksum ký cùng key cho các operation đọc; nhánh credential rỗng trong bytecode bị từ chối 400/500. Đó là cơ sở giữ policy transport cho các endpoint mở trong đợt này.

## Theo dõi tiếp

- Positive item schema cho `GetStudentFeedbacks` và `GetStudentRate` (cả hai đang list rỗng trên tài khoản kiểm chứng).
- `feedbackId` thật để mở `GetStudentFeedbackForm`.
- Các finding v1 (404/201) và positive fee/survey tại [todo](../tasks/todo.md).
