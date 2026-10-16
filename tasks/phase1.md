# Phase 1: sửa v1 và lỗi dữ liệu

## Phạm vi

Tiếp nối Phase 0 trên phiên bản `0.2.0`, branch `fix/phase1-v1-data`. API v1 vẫn là mặc định. Công việc gồm query, payload, chọn kỳ học, survey, học phí, stdout và parser. OAuth/session đầy đủ, adapter v2 và auto release thuộc các phase sau.

## Các bước và tiêu chí hoàn tất

- [ ] Chuyển mọi query v1 sang `params=`, gồm kiểm tra session và handshake login/refresh; giữ nguyên case từng trường và kiểm tra encoding bằng credential giả.
- [ ] Kiểm tra HTTP, JSON và body code riêng; bảo toàn envelope và kiểu `data`. Survey not-found không bị diễn giải thành hết phiên hay không còn survey bắt buộc.
- [ ] Chọn kỳ theo `startDate`, giữ thứ tự server khi trùng ngày; ngày lỗi yêu cầu `--semester`, flag explicit không gọi resolver tự động.
- [ ] Tách checksum survey theo contract của app: username trim/lower, campus rỗng, khóa riêng và giờ Việt Nam.
- [ ] Dùng route v1 `GeFeeByRoll` đã đối chiếu với APK; HTTP 404 là lỗi, giữ mọi dòng học phí và `IsPaid`.
- [ ] Giữ stdout chỉ có JSON/ICS khi dùng `--stdout`; log/lỗi đi stderr. `--date` suy ra năm khi thiếu `--year`.
- [ ] Thêm fixture tổng hợp HTML có rowspan/colspan và lịch ICS; chỉ sửa parser khi regression test tái hiện lỗi.
- [ ] Chạy regression trên Python 3.9/3.11, build wheel/sdist mới, Twine strict, artifact gate và cài thử ngoài checkout.
- [ ] Review độc lập, kiểm tra diff và nội dung tiếng Việt; mở draft PR, ghi kết quả kiểm tra qua comment, giữ trạng thái draft.

## Cơ sở đối chiếu

- Kế hoạch chi tiết: `PLAN-PHASES.md`, Phase 1, ở workspace phân tích.
- Bản so sánh: `analysis/myfap-api-cli-comparison.md` và `analysis/endpoints.md`.
- Contract v1: `analysis/modules/module_550.js`, gồm route học phí và helper survey.
- HAR/SAZ ngày 14/10 chỉ xác nhận runtime v2 và survey. Không coi đây là kiểm thử live v1.

Fixture dùng dữ liệu giả, không chứa token, authenKey, chữ ký thực hoặc thông tin cá nhân. `docs/` và `tasks/` chỉ phục vụ đọc trong repository, không thuộc wheel/sdist hoặc phạm vi kiểm tra code của CI.

## Kiểm chứng

Trước thay đổi: 32 unittest hiện có. Các kết quả RED/GREEN và kiểm tra artifact sẽ được cập nhật sau khi chạy.
