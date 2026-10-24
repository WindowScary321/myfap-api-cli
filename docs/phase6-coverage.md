# Coverage Phase 6 — đang triển khai

Phần đọc tại commit `c829b7004ea2dbb7f99cf1dc3827070039bb9ea5` đang review trong [Draft PR #10](https://github.com/WindowScary321/myfap-api-cli/pull/10). V1 vẫn mặc định, v2 opt-in; **chưa tag/publish**. Đây là capability của code đang review, không phải tính năng đã có trên PyPI hoặc bằng chứng mọi endpoint hoạt động live.

## Command và contract đã nối qua CLI

URL dữ liệu v1 là `https://api.fpt.edu.vn/fap/api/MyFAP/<operation>`; v2 là `https://fap-proxy.fpt.edu.vn/MyFAP/<operation>`. Tất cả operation dữ liệu trong bảng dùng GET. Không ghi query có giá trị, token, checksum hoặc thông tin tài khoản vào tài liệu.

| Command | Operation | v1 / v2 | Điểm contract quan trọng | Bằng chứng hiện tại |
|---|---|---|---|---|
| `other balance` | `GetBalance` | Có / Có | Ký v1 bằng roll number; không lookup kỳ; không suy ra currency/nợ/invoice | Fixture CLI/HTTP hai version; chưa live Phase 6 |
| `courses --semester` | `GetCourseOfSemester` | Có / Có | Query `semester` chữ thường; thiếu option dùng resolver `startDate` | Fixture hai version, explicit/latest; chưa live |
| `other subjects --semester` | `GetSubjectBySemester` | Có / Có | Query `Semester` chữ hoa; signer v1 là semester; không có option vẫn `GetSubjets`, không lookup kỳ | Fixture hai version; chưa live |
| `news --search --type` | `SearchNews` | Có / Có | `type`, `keysearch`; signer v1 là type; search rỗng bị chặn | Fixture Unicode/reserved characters; chưa live |
| `transcript` | `AcademicTranscript` | Có / Có | Không lookup kỳ; giữ JSON, không formatter nghiệp vụ | Fixture; policy credential v2 cần live xác nhận |
| `training --semester` | `GetDiemphongtrao` | Có / Có | Query `semester`; thiếu option dùng resolver | Fixture; policy credential v2 cần live xác nhận |
| `marks --summary` | `GetSemesterMark` | Có / Có | Không có query kỳ; v1 `CampusCode`, `rollNumber`, `Authen`, **không checksum**; v2 có query Authen mới sau refresh | Fixture array/envelope/JSON-string array và refresh; chưa live |
| `info photo` | `RetriveImage` | Có / Có | Chỉ JSON, bảo toàn chuỗi opaque kể cả HTML entity; không tải URL hoặc decode ảnh | Fixture; representation ảnh live chưa xác minh |
| `doctor --stdout` | Không gọi HTTP | Local | Chỉ explicit/default, không đọc/khóa/refresh session, không in config path/identity/token | Test CLI và chạy local thật |
| `doctor --api-version v2 --online` | `GetApiActive` | Không / POST bootstrap | URL proxy; query/body rỗng, bootstrap campus HN; không xác nhận session/campus tài khoản | Fixture; chưa probe live trong Phase 6 |

`marks --summary` từ chối `--semester`, `--courseid`, `--pretty` trước auth. `myfap version` vẫn chỉ đọc package version. Doctor không tự lấy version/campus từ session: điều này được ghi rõ trong report để giữ local mode không có tác dụng phụ.

## Policy và phần chưa xác minh

- Các read mới kế thừa binding và tối đa một refresh/retry khi server báo expiry rõ. Không tự refresh/logout từ 201 không rõ nghĩa, 403, timeout, 5xx hoặc App Check. Capability đọc không mở đường ghi.
- Với transcript/training/summary, caller JS phục dựng v2 không truyền credential tường minh như một số read khác. CLI giữ **policy authenticated read dùng FAP key của binding hiện tại**, không thêm anonymous request hoặc fallback credential rỗng. Đây là khác biệt policy cần ghi nhận và kiểm đọc live, không tự tuyên bố byte-for-byte giống APK.
- Reader tổng kết chỉ dành cho `GetSemesterMark`: raw JSON array, envelope có data list, hoặc JSON string chứa trọn array. Giới hạn xử lý cục bộ 1 MiB. Không cắt tùy tiện chuỗi giữa dấu ngoặc; XML/HTML wrapper chưa xác minh bị từ chối bằng lỗi payload an toàn. Reader chung của operation khác không được nới lỏng.
- Photo JSON không đồng nghĩa đã hỗ trợ xuất ảnh binary. Không tự fetch URL bất kỳ hoặc chuyển credential sang host ảnh.
- Rating list v2 là stub; rating/push/feedback chưa được mở bởi các thay đổi này. Những gate tại [tasks/phase6.md](../tasks/phase6.md) vẫn còn pending, Phase 6 **chưa hoàn tất**.
- `GetVersion` backend tiếp tục unsupported cho đến khi public/text contract đủ rõ. Không thay package `version` thành probe online.

## Kiểm chứng

Test mới dùng CLI/auth/client thật với session tổng hợp và HTTP giả; không dùng capture/account làm fixture. Các chu kỳ RED đã ghi nhận command/option/module chưa tồn tại, GREEN sau implementation; reader bảo toàn lỗi HTTP/App Check/expiry, không đổi lỗi thành mảng rỗng.

Kết quả full suite và review được ghi theo commit trong PR, không thay cho live. Chưa chạy login/live command mới trong lượt implementation này. Các skip/failure/unknown trong [coverage Phase 4](phase4-coverage.md) và TODO positive fee/survey vẫn giữ nguyên.
