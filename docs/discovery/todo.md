# Công việc chuyển sang uv

- [x] Thiết lập `.python-version`, tạo `uv.lock`, cập nhật README; `uv sync --locked` thành công.
- [x] Thêm regression test và sửa `myfap version`; xác nhận test thất bại trước sửa và thành công sau sửa.
- [x] Cập nhật CI/build, kiểm tra local trên Python 3.9/3.11 và cài wheel trong môi trường riêng.
- [x] Review diff và kiểm tra tiếng Việt; sẵn sàng tạo commit, PR và bình luận bằng tiếng Việt.

Kết quả GitHub Actions và bình luận kiểm tra được theo dõi trực tiếp trong PR. Đăng nhập và gọi API đã được kiểm chứng theo từng phase; các mục live còn mở được liệt kê bên dưới. Publish PyPI vẫn thuộc Phase 5.

## Kiểm chứng live còn mở trước khi phát hành

- [x] Chạy lại `news`, `other notification` và `other fee` trên v1/APHL bằng session tạm ngày 19/10/2026. News/notification nhận HTTP 200/body 201; fee nhận HTTP 404. Lệnh đối chứng `info student` đạt 200/200 trước và sau; session/lock tạm đã xóa. Xem [báo cáo live v1](phase4-coverage.md#chạy-lại-ba-lệnh-v1-ngày-19102026).
- [ ] Xác minh ý nghĩa body 201 của `news` v1 và đối chiếu trường hợp có dữ liệu. Lượt live mới vẫn có `data: null`, message null hoặc không có. Không gộp mọi code 201 vào hết phiên hoặc coi đó là danh sách rỗng hợp lệ.
- [ ] Xác định nguyên nhân body 201 của `other notification` v1. Request khớp path/query/checksum của app; session đối chứng vẫn đọc được, chưa xác nhận lỗi thuộc backend hay điều kiện tài khoản.
- [ ] Xác nhận `GeFeeByRoll` v1 có response thành công hoặc có bằng chứng từ đơn vị vận hành về phạm vi hỗ trợ. HTTP 404 trên APHL chưa đủ để kết luận route đã ngừng hỗ trợ trên mọi campus hoặc suy ra schema.

Mỗi mục cần session tạm, kết quả ghi rõ API version/campus và metadata đã lọc trước khi đóng. Không đưa credential, thông tin cá nhân hoặc raw response lên Git. CI xanh, fixture hoặc kết quả API v2 không thay thế kiểm chứng live v1. Xem [checklist Phase 4](https://github.com/WindowScary321/myfap-api-cli/blob/467df1edb2220261dcd21392fbe3eaf008d6c662/tasks/phase4.md) và [báo cáo coverage](phase4-coverage.md).

## Kiểm chứng hoãn chờ dữ liệu phù hợp

Theo quyết định của người dùng ngày 19/10/2026, hoãn positive fee/survey vì hiện chưa có dữ liệu nghiệp vụ phù hợp. Hai mục này không chặn chuyển sang Phase 5; schema live vẫn ở trạng thái **chưa kiểm chứng**, không được đánh dấu đã đạt.

- [ ] **Fee:** khi có tài khoản với khoản học phí cần thanh toán hoặc dữ liệu hóa đơn phù hợp, đối chiếu `IsPaid`, số tiền và thông tin hóa đơn trên payload thật. HTTP/body 200 với dữ liệu rỗng chưa đủ để đóng mục này.
- [ ] **Survey:** khi có tài khoản với khảo sát bắt buộc, đối chiếu payload có dữ liệu với contract của dịch vụ survey. Trạng thái `Data Not Found` chưa đủ để đóng mục này.

Khi có điều kiện kiểm chứng, dùng session tạm, ghi rõ API version/campus và chỉ lưu metadata đã lọc. Không đưa credential, thông tin cá nhân hoặc raw response lên Git.

## Chuẩn bị phát hành Phase 5

Theo dõi triển khai, kết quả kiểm tra và gate dịch vụ còn mở tại [phase5.md](phase5.md). [Runbook phát hành](../cli/releasing.md) mô tả kiểm tag/version/artifact, Trusted Publishing, retry và TestPyPI; [CHANGELOG.md](../../CHANGELOG.md) giữ release notes cùng known issues.

Chuyển Phase 5 không tự đóng ba lỗi live v1, không xác nhận positive fee/survey và không cho phép tạo/push tag hoặc publish. Maintainer phải duyệt phạm vi hỗ trợ và các gate phát hành trước khi thực hiện.

## Mở rộng command và endpoint Phase 6

Theo quyết định ngày 23/10/2026, **chưa tag/publish cho đến sau khi hoàn thiện và nghiệm thu phạm vi Phase 6**. PR #9 đã merge tại `75fc7b4aa33a13b9b39eab898f61e2e693f4baf9`; đó là pipeline chuẩn bị, không phải release. Giữ baseline `0.2.0`, v1 mặc định/v2 opt-in.

Checklist, tiêu chí và gate bằng chứng nằm tại [phase6.md](phase6.md). Các mục sau chỉ được đánh dấu khi có kết quả tương ứng:

- [x] Hoàn thiện các lát cắt đọc: courses, subjects theo kỳ, balance và news search, giữ hành vi command cũ (nghiệm thu 24/10/2026).
- [x] Hoàn thiện transcript/training và marks summary sau khi chốt các ngoại lệ credential/response; không đoán query hoặc schema (nghiệm thu 24/10/2026, bổ sung `transcript --pretty`).
- [x] Bổ sung photo JSON và doctor an toàn; không tự fetch/decode ảnh hoặc refresh session khi chẩn đoán local (nghiệm thu 24/10/2026, mở `doctor --online` với `GetVersion`).
- [ ] Chốt rating/push/feedback theo gate schema/capability; không mở write hoặc ghi live khi chưa đủ bằng chứng/xác nhận. (Tám (8) hộp việc ở mục 4–5 của `phase6.md` tiếp tục **giữ gate/unsupported có chủ đích** do tài khoản kiểm chứng trả danh sách rỗng, không thể xác minh positive schema/ack).
- [x] Bổ sung xuất lịch thi `exams --ics` (RFC 5545, CRLF, UTC UID/DTSTAMP) và cờ `--full` (hoàn tất 26/10/2026).
- [x] Kiểm regression, artifact, CI và live đọc riêng; giữ nguyên mọi skip/failure/unverified và TODO v1/positive fee/survey ở trên (420 test đạt trên Python 3.9/3.11).
- [x] Đồng bộ tài liệu và đóng các điểm lệch phạm vi trước merge (Pre-merge Docs Sync):
  - [x] Khớp lại ghi chú mục 4–5 trong `docs/discovery/phase6.md` (khẳng định 8 hộp việc giữ gate/unsupported có chủ đích, không tick khi chưa có schema live).
  - [x] Chuẩn hóa tuyên bố trong `docs/discovery/endpoint-gap-analysis.md` (ghi nhận CLI phủ toàn bộ thao tác đọc sinh viên ngoại trừ `GetStudentFeedbackForm`).
  - [x] Đồng bộ thứ tự phát hành trong `docs/cli/releasing.md` (khớp quyết định phát hành sau khi nghiệm thu phạm vi Phase 6).
- [x] Cập nhật Draft PR Phase 6; mỗi commit push có comment ngay sau commit, không tự merge/tag/publish.
- [ ] Maintainer duyệt phạm vi Phase 6 và các gate dịch vụ Phase 5 trước khi phát hành thật.

### Lỗi live v1 mới ngày 24/10/2026

Các command đã chạy thật trên v1/APHL sau login mới; chi tiết tại [coverage Phase 6](phase6-coverage.md#live-đọc-v1aphl-ngày-24102026). Không dùng kết quả v2 hoặc fixture để đóng các mục này:

- [ ] Xác định nguyên nhân GetCourseOfSemester HTTP 404; request hiện giữ casing/signing theo caller v1.
- [ ] Xác định nguyên nhân GetSemesterMark HTTP 404; không tự thêm checksum/kỳ hoặc đổi route để thử.
- [ ] Xác định nguyên nhân SearchNews HTTP 200/body 201, data null; không coi là hết phiên hoặc empty hợp lệ.
- [ ] Xác định nguyên nhân GetDiemphongtrao HTTP 200/body 201, data null; không bỏ lỗi hoặc fallback v2.

Cùng lượt, subjects/balance/rating list đọc được và student sau refresh đạt 200/200. Transcript rỗng, photo null và rating list rỗng không xác nhận positive schema hoặc ID hợp lệ cho submit. Session/lock/thư mục tạm đã dọn; chỉ metadata được ghi, không raw response/identity/credential.

## Mục 4–5 Phase 6 khó thực hiện với tài khoản hiện tại

Theo đánh giá của maintainer ngày 24/10/2026, **các mục 4 (rating/push) và 5 (feedback đầy đủ) của [phase6.md](phase6.md) không thể thực hiện hoặc xác minh bằng tài khoản hiện tại**:

- **Rating submit (`AddRate`)**: rating list v1 trả danh sách rỗng — không có rateid/positive item để đối chiếu input schema và ack.
- **Push register (`UpdateTokedevices`)**: thao tác ghi thiết bị; cần contract student đã chốt và xác nhận riêng trước khi live ghi.
- **`GetStudentFeedbackForm`**: `other feedbacks` trả list rỗng — không có feedbackId thật; không đoán ID theo quy tắc plan.
- **`SubmitStudentFeedback`**: cần feedback đang mở để có form/ack hợp lệ.
- **Donor/employee và login thay thế** (`GetNotificationByDonor`, `GetTokenWithEmp`, `UpdateTokenDonor`, Google/username/FeIdCode): đã ghi out of scope tại [phân tích khoảng trống endpoint](endpoint-gap-analysis.md), không dự định triển khai trong Phase 6.

Hệ quả khi chốt phạm vi Phase 6 và phát hành `0.2.0`: Tám (8) hộp việc ở mục 4–5 trong `docs/discovery/phase6.md` tiếp tục giữ trạng thái **gate/unsupported có chủ đích** (không tick trong `phase6.md`), không đánh dấu hoàn tất và không mở generic submit; `docs/discovery/endpoint-gap-analysis.md` đã chuẩn hóa tuyên bố phủ toàn bộ đọc sinh viên ngoại trừ `GetStudentFeedbackForm`; maintainer duyệt phát hành với known issues này. Khi có tài khoản hoặc dữ liệu phù hợp:

- [ ] Thu thập input schema và ack của `AddRate` (v1 checksum `rateid`, v2 query `Authen`, body `{}`) và các form feedback theo [phase6-write-gates.md](phase6-write-gates.md) trước khi mở command.
- [ ] `push register --token-file` cần contract student đã chốt và xác nhận riêng của người dùng trước khi live ghi; token thiết bị chỉ đọc từ regular file, không đưa vào argv/preview/log/error.

Các gate và trình tự validate → capability → preview → confirmation → auth vẫn áp dụng; không cố tình thử ghi để tạo dữ liệu, không coi list rỗng là route lỗi, và việc chưa xác minh được không tự đóng cũng không nới gate.

## Finding robustness từ review Phase 6 (24/10/2026)

Lượt review lượt hai trên toàn bộ diff PR #10 theo 4 trục (query/credential/parser/write safety): query contract, credential và write safety sạch; parser có bốn finding, đều không phải lỗ hổng bảo mật (CLI chạy bởi chính người dùng trên máy họ). Maintainer quyết định sửa trước khi tag `0.2.0` hay phát hành với known issues:

- [x] `parse_marks_html` crash khi `rowspan` không phải số nguyên (`myfap/parsers.py`) — **đã sửa 24/10/2026**: giá trị rác coi như 1, kèm test regression.
- [x] ICS: `isOnline` boolean mất nhãn "(Online)"; slot vượt nửa đêm và `slotTime` không dấu gạch — **đã sửa 24/10/2026**: nhận boolean, slot kết thúc sang ngày hôm sau, lỗi `slotTime` có thông báo rõ; kèm test.
- [x] `save_output` sanitize tên file xuất — **đã sửa 24/10/2026**: thay `/`, `\` và NUL bằng `_`, file luôn nằm trong thư mục `--output`; kèm test.
- [x] (low) Test nhánh `transcript --pretty` khi data không phải HTML — **đã có**: test CLI seam phủ cả nhánh giữ nguyên chuỗi gốc.
