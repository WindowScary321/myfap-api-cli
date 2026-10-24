# Phase 6: mở rộng command và endpoint trước phát hành

Nhánh triển khai `feat/phase6-command-expansion` bắt đầu từ `main` tại `75fc7b4aa33a13b9b39eab898f61e2e693f4baf9`, sau khi [PR #9](https://github.com/WindowScary321/myfap-api-cli/pull/9) được merge. Theo quyết định ngày **23/10/2026**, Phase 5 chỉ chuẩn bị pipeline; **hoãn tag/publish đến sau khi hoàn thiện và nghiệm thu phạm vi Phase 6**. Giữ baseline `0.2.0`, Python >=3.9, v1 mặc định và v2 opt-in.

Nhóm command đọc đã có implementation và fixture CLI/HTTP; xem [coverage Phase 6](../docs/phase6-coverage.md). Dấu đã kiểm bên dưới chỉ áp dụng cho code/fixture được nêu, không thay thế live hoặc nghiệm thu backend. Phần thiếu contract/schema vẫn giữ gate rõ; không đánh dấu toàn Phase 6 hoàn tất khi các yêu cầu bắt buộc còn mở.

## Quy tắc xuyên suốt

- Tái sử dụng wrapper, common options, resolver kỳ và output JSON hiện có; không refactor auth/CI ngoài phạm vi. Không thay `tasks/plan.md` vì đó là lịch sử migration.
- Kiểm capability và option/input trước HTTP; giữ binding campus/API version/student và bảo toàn token đã rotate. Không fallback version, không trả dữ liệu rỗng giả cho stub/lỗi.
- Retry đọc tối đa một lần chỉ khi expiry rõ. Thao tác ghi không replay dù endpoint dùng GET; timeout hoặc kết quả không rõ không được báo thành công hoặc tự gửi lại.
- JSON/ICS stdout giữ UTF-8; log/lỗi stderr. `save_output` không phải binary writer.
- Test dùng dữ liệu tổng hợp, credential giả và session tạm. Live đọc dùng browser/context mới, payload chỉ xử lý cục bộ; chỉ operation/method/HTTP/body code/kiểu dữ liệu/exit code/kiểm định dạng được ghi vào báo cáo.
- Không đưa raw response, ảnh, token, query có giá trị, identity hoặc dữ liệu tài khoản lên GitHub. Live ghi cần người dùng xác nhận riêng thao tác cụ thể.
- Mỗi commit push lên PR phải có comment ngay sau commit, ghi SHA, kiểm tra/exit code và giới hạn; không tự merge, tạo tag, publish hoặc đổi default v2.

## 1. Các lát cắt đọc rõ contract

Mỗi mục cần đi trọn CLI → wrapper → transport v1/v2 → fixture/test → coverage, không chỉ thêm tên vào allowlist.

- [x] **`courses --semester` → `GetCourseOfSemester`:** dùng resolver kỳ nếu thiếu option; query `semester` chữ thường, đúng credential/signing identity từng version.
- [x] **`other subjects --semester` → `GetSubjectBySemester`:** query `Semester` chữ hoa; v1 ký bằng semester. Khi không có option mới vẫn dùng `GetSubjets`, không lookup kỳ và giữ timeout subjects hiện có.
- [x] **`other balance` → `GetBalance`:** không lookup kỳ; bảo toàn payload, không suy ra currency/nợ/invoice. Cập nhật retry/error allowlist có chủ đích và giữ regression cho operation chưa hỗ trợ.
- [x] **`news --search` → `SearchNews`:** không có search vẫn dùng `GetTop10News`; từ chối search rỗng trước auth, truyền `type`/`keysearch` qua params và v1 ký bằng type. Kiểm Unicode và ký tự reserved, không nối query thủ công.

**Nghiệm thu nhóm:**
- [ ] Test tại public seam CLI và biên HTTP chứng minh method/path/query/header/body đúng, stdout sạch, binding và common-option precedence được giữ.
- [ ] Có success/empty/not-found phù hợp, malformed, expiry, App Check, timeout/5xx và không fallback; focused tests rồi regression hiện có đạt.

## 2. Transcript, training và marks summary

- [x] **`transcript` → `AcademicTranscript`:** hỗ trợ theo contract cả v1/v2, không lookup kỳ; chưa thêm formatter nghiệp vụ khi schema data chưa được xác minh.
- [x] **`training --semester` → `GetDiemphongtrao`:** query `semester` chữ thường, dùng resolver khi thiếu kỳ; giữ bound credential phù hợp.
- [x] **`marks --summary` → `GetSemesterMark`:** không lookup kỳ hoặc thêm query semester. V1 dùng đúng `CampusCode`, `rollNumber`, `Authen`, **không checksum**; v2 giữ query `Authen` mới sau refresh.
- [ ] Từ chối tổ hợp summary với `--courseid`/`--pretty`; nếu `--semester` không áp dụng thì báo lỗi, không âm thầm bỏ qua.
- [ ] Reader riêng cho summary kiểm HTTP/App Check/expiry trước khi đọc raw array/envelope/text. Chỉ parse dạng đã có bằng chứng, có giới hạn; malformed/unknown phải báo payload error, không cắt tùy tiện giữa dấu ngoặc rồi trả success.
- [ ] Chốt khác biệt credential v2 ở các caller decompile của transcript/training/summary bằng bytecode/contract và kiểm đọc. Không mặc định sao chép credential rỗng, thử unauth rồi fallback hoặc nới reader chung cho mọi endpoint.

**Nghiệm thu nhóm:**
- [ ] Test exact casing, no-semester/no-checksum, signing identity và dựng Authen mới sau refresh; giữ nguyên command marks cũ.
- [ ] Fixture được ghi rõ synthetic; các schema hoặc credential chưa live xác nhận tiếp tục có nhãn unverified.

## 3. Photo và doctor

- [x] **`info photo` → `RetriveImage`:** output JSON theo representation đã chứng minh, giữ chuỗi opaque; không tự fetch URL, decode Base64, in binary hoặc mở ảnh. Xuất ảnh file riêng chỉ mở sau khi đủ bằng chứng định dạng/size/type và fixture.
- [x] **`doctor` local:** chỉ xuất allowlist chẩn đoán package/API version, campus được chọn, capability và loại lỗi; không dump auth/session, email/MSSV, header, token hoặc config path đầy đủ. Không gọi `require_auth`/`load_session` gây refresh/persist.
- [ ] Probe online là option explicit và tái sử dụng `GetApiActive` v2; không auto-login/refresh/switch version. `GetVersion` giữ gate riêng khi public/text contract còn chưa rõ; `myfap version` tiếp tục offline.
- [ ] Test doctor/help local không gọi mạng; lỗi không lộ payload; photo không tạo file/fetch ngoài ý muốn.

## Checkpoint: nhóm đọc

- [ ] Focused/full regression, build/Twine/artifact validator và pip smoke đạt; không có docs/tasks/tests/session/capture trong distribution.
- [ ] Cập nhật [mapping command/endpoint/URL](../docs/command-endpoints.md), [contract v2](../docs/v2-contracts.md) và coverage Phase 6 với capability theo version/account rõ ràng.
- [ ] Live đọc bằng session/browser mới; ghi riêng success, empty, not-found, failure, skip và unverified. Không dùng 200 hoặc nonempty để đóng positive fee/survey; không dùng v2 để đóng finding v1.

## 4. Rating và push — chỉ mở sau gate contract

- [ ] **Rating list:** chốt fixture/schema tối thiểu cho student/v1; v2 là stub nên unsupported trước auth/network, không gọi v1 ngầm hoặc trả `[]` giả.
- [ ] **`rating submit --input`:** chốt input/ack bằng bằng chứng đủ tin cậy trước khi mở. `AddRate` là POST; v1 checksum dùng **rateid**, v2 giữ query `Authen` và body `{}`. Dải rating 1–5 có nguồn caller; không tự đặt type ID/comment bounds của backend.
- [ ] **`push register --token-file`:** chốt contract student; `UpdateTokedevices` là **GET ghi**, v1 ký bằng **email**. Token chỉ đọc từ regular file có giới hạn, kiểm encoding/newline và symlink/reparse/path swap; không token trên argv/preview/log/error. Campus/identity lấy từ session đã bind.
- [ ] Đường ghi tách khỏi read retry, không thêm AddRate/push vào read allowlist để cấp credential. Trình tự: validate → capability → preview không bí mật → confirmation/`--yes` → auth → một lần gửi. `--yes` không bỏ validation.
- [ ] Test invalid input/cancel/noninteractive thiếu xác nhận gây zero auth/network; 401/App Check/timeout/5xx hoặc unknown outcome không replay.
- [ ] Live ghi chỉ thực hiện sau xác nhận riêng của người dùng; nếu chưa đủ schema/ack thì capability vẫn đóng và ghi TODO, không mở generic submit.

## 5. Feedback và flow còn thiếu bằng chứng

- [ ] Giữ `other feedback` là `CheckOpenFeedBack`; không đổi nghĩa thành list/form/submit.
- [ ] `GetStudentFeedbacks`/`GetStudentFeedbackForm` chỉ mở khi có response contract đủ; không suy kiểu item/ID/câu hỏi từ tên route.
- [ ] `SubmitStudentFeedback`, donor/employee, donor push và FEID server-code exchange thiếu schema/capability tiếp tục gate/TODO; không nhận JSON tùy ý để vượt gate.
- [ ] Trước khi chốt phạm vi, liệt kê từng blocker và bằng chứng cần thêm; không đánh dấu Phase 6 hoàn tất bằng cách lặng lẽ bỏ các mục chưa đạt.

## 6. Kiểm chứng và bàn giao PR

- [ ] Dùng red → green từng feature qua CLI thật và HTTP giả; mutation check cho casing, signing identity và no-retry. Không dùng dữ liệu account làm fixture.
- [ ] Chạy từ checkout: `uv sync --locked --group ci`, focused tests, rồi `uv run --locked --group ci python -m unittest discover -s tests -v` trên Python 3.9/3.11; `git diff --check`.
- [ ] Build, Twine, artifact validator và pip smoke theo [development.md](../docs/development.md); CI xác nhận Ubuntu/Windows × Python 3.9/3.11.
- [ ] Review độc lập phần query/credential/parser/write safety và cập nhật README/CHANGELOG/coverage theo đúng kết quả.
- [ ] Draft PR Phase 6 được tạo từ nhánh mới; mỗi commit push có comment ngay sau commit, gồm SHA, thay đổi, lệnh/exit code và giới hạn.
- [ ] Maintainer nghiệm thu phạm vi Phase 6 trước khi tiếp tục [gate phát hành Phase 5](phase5.md). Không tự merge/tag/publish.

## Trạng thái khởi động

Nhóm command đọc và doctor đã có fixture; focused tests ghi RED trước implementation rồi GREEN. Full suite ngày 24/10/2026 trên Windows: **389 test mỗi Python 3.11 và 3.9, 385 đạt/4 skip, exit 0**. Bốn skip là các phép symlink/POSIX mode không áp dụng hoặc thiếu quyền trên Windows, không phải test bị bỏ mới.

Review độc lập đã tái hiện hai finding bằng HTTP giả: public API v1 chưa validate kỳ trước HTTP, và body summary lỗi quá lớn che HTTP 401/503. Đã sửa và test lại. Lượt full đầu chạy hai interpreter đồng thời bị timeout tiến trình help 20 giây; Python 3.9 còn lộ cách CliRunner tách stderr khác version. Đã sửa cấu hình capture trong test theo mẫu hiện có, giữ nguyên kiểm tra nội dung/timeout; focused help đạt, sau đó hai full suite chạy tuần tự đều đạt. Không hạ tiêu chí hoặc bỏ test.

Build, Twine và artifact validator đã đạt với bộ `dist-phase6-reads`, manifest SHA-256 `f88e6fe7b5795fbb01acfda00df434e74d02965aaab21c2c83328e4bfaff2fea`. Pip smoke wheel/sdist trong hai venv sạch Windows/Python 3.11 đạt, exit 0; không dùng lockfile để resolve dependency. Mutation đổi signer subjects từ semester sang identity khác bị test bắt; chạy trên bản sao tạm, không sửa checkout. Fixture mới dùng identity tổng hợp kể cả nhánh legacy. Doctor local đã chạy qua CLI thật, không đọc session/HTTP. Chưa có live account hoặc CI cho commit runtime mới tại thời điểm ghi nhận; rating/push/feedback vẫn gate, không tuyên bố Phase 6 hoàn tất. Các finding v1 và positive fee/survey giữ tại [todo.md](todo.md).
