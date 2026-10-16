# Phase 1: sửa v1 và lỗi dữ liệu

## Phạm vi

Tiếp nối Phase 0 trên phiên bản `0.2.0`, branch `fix/phase1-v1-data`. API v1 vẫn là mặc định. Công việc gồm query, payload, chọn kỳ học, survey, học phí, stdout và parser. OAuth/session đầy đủ, adapter v2 và auto release thuộc các phase sau.

**Trạng thái sau kiểm chứng API thật ngày 16/10/2026:** phần triển khai và kiểm thử offline đã xong; live còn ba command chưa hoạt động. Chi tiết nằm trong [báo cáo kiểm chứng live](../docs/phase1-live-verification.md).

## Các bước và tiêu chí hoàn tất

- [x] Chuyển mọi query v1 sang `params=`, gồm kiểm tra session và handshake login/refresh; giữ nguyên case từng trường và kiểm tra encoding bằng credential giả.
- [x] Kiểm tra HTTP, JSON và body code riêng; bảo toàn envelope và kiểu `data`. Survey not-found không bị diễn giải thành hết phiên hay không còn survey bắt buộc.
- [x] Chọn kỳ theo `startDate`, giữ thứ tự server khi trùng ngày; ngày lỗi yêu cầu `--semester`, flag explicit không gọi resolver tự động.
- [x] Tách checksum survey theo contract của app: username trim/lower, campus rỗng, khóa riêng và giờ Việt Nam.
- [x] Dùng route v1 `GeFeeByRoll` đã đối chiếu với APK; HTTP 404 là lỗi, giữ mọi dòng học phí và `IsPaid`.
- [x] Giữ stdout chỉ có JSON/ICS khi dùng `--stdout`; log/lỗi đi stderr. `--date` suy ra năm khi thiếu `--year`.
- [x] Thêm fixture tổng hợp HTML có rowspan/colspan và lịch ICS; chỉ sửa parser khi regression test tái hiện lỗi.
- [x] Chạy regression trên Python 3.9/3.11, build wheel/sdist mới, Twine strict, artifact gate và cài thử ngoài checkout.
- [x] Review độc lập, kiểm tra diff và nội dung tiếng Việt; mở draft PR, ghi kết quả kiểm tra qua comment, giữ trạng thái draft.
- [x] Chạy command trực tiếp với session mẫu; kiểm chứng 20 route, chỉ lưu kết quả đã che dữ liệu.
- [ ] Giải quyết code 201 của `news` và `other notification`; chưa kết luận đây là lỗi hết phiên.
- [ ] Xác minh endpoint học phí v1 vì cả `GeFeeByRoll` và phép chẩn đoán `GetFeeByRoll` đều trả HTTP 404.

## Cơ sở đối chiếu

- Kế hoạch chi tiết: `PLAN-PHASES.md`, Phase 1, ở workspace phân tích.
- Bản so sánh: `analysis/myfap-api-cli-comparison.md` và `analysis/endpoints.md`.
- Contract v1: `analysis/modules/module_550.js`, gồm route học phí và helper survey.
- HAR/SAZ ngày 14/10 chỉ xác nhận runtime v2 và survey. Không coi đây là kiểm thử live v1.

Fixture dùng dữ liệu giả, không chứa token, authenKey, chữ ký thực hoặc thông tin cá nhân. `docs/` và `tasks/` chỉ phục vụ đọc trong repository, không thuộc wheel/sdist hoặc phạm vi kiểm tra code của CI.

## Kiểm chứng

Trước thay đổi có 32 unittest. Suite mới tái hiện lỗi query, thứ tự kỳ, học phí HTTP 404, survey, stdout, ngày/năm và rowspan trước khi sửa. Kết quả sau sửa:

- 88 unittest ban đầu; sau bổ sung `--timeout` trong PR #4, suite có 96 test và pass Ubuntu/Windows × Python 3.9/3.11.
- Mutation đảo thứ tự ngày và sửa sai bộ đếm rowspan đều bị regression test bắt.
- ICS pass trên Python 3.9 không có `tzdata`, dùng `pytz` sẵn có.
- Twine strict và artifact validator pass với wheel/sdist mới; pip cài được cả hai artifact trong hai venv riêng ngoài checkout.
- Mã runtime trong artifact khớp source. `docs/`, `tasks/` và `tests/` không nằm trong artifact; fixture chỉ phục vụ CI từ checkout.
- Validator tiếng Việt strict không có lỗi hoặc cảnh báo; diff không có lỗi whitespace. Đã review độc lập và đối chiếu giá trị credential/identity từ capture bằng script, chỉ xuất kết quả không trùng, không in giá trị.

PR [#4](https://github.com/WindowScary321/myfap-api-cli/pull/4) đã merge vào branch Phase 1. [CI sau merge timeout](https://github.com/WindowScary321/myfap-api-cli/actions/runs/38875363915) pass cả 11 job trên commit `07fb289` của PR [#3](https://github.com/WindowScary321/myfap-api-cli/pull/3). Trạng thái review/merge do maintainer quyết định; không tự chuyển Ready for review hoặc merge.

Kiểm chứng live trên commit đó: 25 lần chạy command, 22 exit 0 và 3 exit 1, phủ 20 route. Lịch, điểm chi tiết, điểm danh, thông tin, đơn từ, môn học và survey not-found đã có bằng chứng runtime v1. Ba lỗi còn lại được ghi riêng, không bỏ qua trong kết luận.

## Giới hạn

Đã kiểm thử server v1 qua CLI với một session mẫu, không đọc trực tiếp thư mục chứa session. Fixture survey thành công và học phí v1 vẫn là dữ liệu tổng hợp: live chỉ quan sát survey not-found và học phí HTTP 404. Chưa xác minh nhiều tài khoản/campus hoặc đối chiếu toàn bộ nội dung với app chính.

Phase 2 tiếp tục xử lý token validation, campus binding, session lock/atomic write và refresh rotation. Phase 1 không triển khai adapter v2, auto release, tag hoặc publish PyPI. Rollback dùng revert các commit trong PR; không có migration dữ liệu.
