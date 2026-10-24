# Coverage Phase 6 — đang triển khai

Nhóm đọc ban đầu tại `c829b7004ea2dbb7f99cf1dc3827070039bb9ea5`, bổ sung rating list v1 tại `4c29b81f0e61d11ccb6d047060680cbcf60ab121`, đang review trong [Draft PR #10](https://github.com/WindowScary321/myfap-api-cli/pull/10). V1 vẫn mặc định, v2 opt-in; **chưa tag/publish**. Đây là capability của code đang review, không phải tính năng đã có trên PyPI hoặc bằng chứng mọi endpoint hoạt động live.

## Command và contract đã nối qua CLI

URL dữ liệu v1 là `https://api.fpt.edu.vn/fap/api/MyFAP/<operation>`; v2 là `https://fap-proxy.fpt.edu.vn/MyFAP/<operation>`. Tất cả operation dữ liệu trong bảng dùng GET. Không ghi query có giá trị, token, checksum hoặc thông tin tài khoản vào tài liệu.

| Command | Operation | v1 / v2 | Điểm contract quan trọng | Bằng chứng hiện tại |
|---|---|---|---|---|
| `other balance` | `GetBalance` | Có / Có | Ký v1 bằng roll number; không lookup kỳ; không suy ra currency/nợ/invoice | Fixture hai version; live v2/HN 200/200, v1 chưa live |
| `courses --semester` | `GetCourseOfSemester` | Có / Có | Query `semester` chữ thường; thiếu option dùng resolver `startDate` | Fixture explicit/latest; live v2/HN 200/200, v1 chưa live |
| `other subjects --semester` | `GetSubjectBySemester` | Có / Có | Query `Semester` chữ hoa; signer v1 là semester; không có option vẫn `GetSubjets`, không lookup kỳ | Fixture hai version; live v2/HN 200/200, v1 chưa live |
| `news --search --type` | `SearchNews` | Có / Có | `type`, `keysearch`; signer v1 là type; search rỗng bị chặn | Fixture Unicode/reserved characters; live v2/HN 200/200 |
| `transcript` | `AcademicTranscript` | Có / Có | Không lookup kỳ; giữ JSON, không formatter nghiệp vụ | Fixture; live v2/HN 200/200 với bound key, data string |
| `training --semester` | `GetDiemphongtrao` | Có / Có | Query `semester`; thiếu option dùng resolver | Fixture; live v2/HN 200/200 với bound key, list rỗng |
| `marks --summary` | `GetSemesterMark` | Có / Có | Không có query kỳ; v1 `CampusCode`, `rollNumber`, `Authen`, **không checksum**; v2 có query Authen mới sau refresh | Fixture parser/refresh; live v2/HN 200/200 với envelope data list |
| `info photo` | `RetriveImage` | Có / Có | Chỉ JSON, bảo toàn chuỗi opaque kể cả HTML entity; không tải URL hoặc decode ảnh | Live v2/HN 200/200, data string; định dạng ảnh chưa xác minh |
| `rating list` | `GetStudentRate` | Có / Không | V1 đọc, ký bằng roll number; v2 stub bị chặn trước load session/HTTP | Fixture CLI/HTTP, chưa live |
| `doctor --stdout` | Không gọi HTTP | Local | Chỉ explicit/default, không đọc/khóa/refresh session, không in config path/identity/token | Test CLI và chạy local thật |
| `doctor --api-version v2 --online` | `GetApiActive` | Không / POST bootstrap | URL proxy; query/body rỗng, bootstrap campus HN; không xác nhận session/campus tài khoản | Fixture và live bootstrap v2 200/200; không kiểm tài khoản |

`marks --summary` từ chối `--semester`, `--courseid`, `--pretty` trước auth. `myfap version` vẫn chỉ đọc package version. Doctor không tự lấy version/campus từ session: điều này được ghi rõ trong report để giữ local mode không có tác dụng phụ.

## Policy và phần chưa xác minh

- Các read mới kế thừa binding và tối đa một refresh/retry khi server báo expiry rõ. Không tự refresh/logout từ 201 không rõ nghĩa, 403, timeout, 5xx hoặc App Check. Capability đọc không mở đường ghi.
- Với transcript/training/summary, caller JS phục dựng v2 không truyền credential tường minh như một số read khác. CLI giữ **policy authenticated read dùng FAP key của binding hiện tại**, không thêm anonymous request hoặc fallback credential rỗng. Lượt live v2/HN ngày 24/10 đã đọc thành công bằng policy này; không chứng minh server bắt buộc Bearer, không xác minh nhánh credential rỗng của APK hoặc parity byte-for-byte.
- Reader tổng kết chỉ dành cho `GetSemesterMark`: raw JSON array, envelope có data list, hoặc JSON string chứa trọn array. Giới hạn xử lý cục bộ 1 MiB. Không cắt tùy tiện chuỗi giữa dấu ngoặc; XML/HTML wrapper chưa xác minh bị từ chối bằng lỗi payload an toàn. Reader chung của operation khác không được nới lỏng.
- Photo JSON không đồng nghĩa đã hỗ trợ xuất ảnh binary. Không tự fetch URL bất kỳ hoặc chuyển credential sang host ảnh.
- Rating list v1 có code/fixture; URL là `https://api.fpt.edu.vn/fap/api/MyFAP/GetStudentRate`. Rating list v2 là stub và bị chặn. Rating submit/push/feedback đầy đủ chưa được mở bởi các thay đổi này. Những gate tại [tasks/phase6.md](../tasks/phase6.md) vẫn còn pending, Phase 6 **chưa hoàn tất**.
- `GetVersion` backend tiếp tục unsupported cho đến khi public/text contract đủ rõ. Không thay package `version` thành probe online.

## Kiểm chứng

Test mới dùng CLI/auth/client thật với session tổng hợp và HTTP giả; không dùng capture/account làm fixture. Các chu kỳ RED đã ghi nhận command/option/module chưa tồn tại, GREEN sau implementation; reader bảo toàn lỗi HTTP/App Check/expiry, không đổi lỗi thành mảng rỗng.

Sau rating list, full local Windows có 391 test trên mỗi Python 3.11/3.9, 387 đạt/4 skip, exit 0. Venv Python 3.9 từng lỗi tzdata UTC độc lập với command; cài lại đúng version khóa trong venv test đã phục hồi probe UTC và toàn suite, không đổi lockfile.

CI run [40064482334](https://github.com/WindowScary321/myfap-api-cli/actions/runs/40064482334) tại `d6d0ee63a7c052bf94112426323ed06b4ca05be6` đạt **11/11 job**, gồm source và artifact smoke Ubuntu/Windows × Python 3.9/3.11. Run trước đó thất bại vì assertion đọc tên option trên chuỗi ANSI; đã tái hiện FORCE_COLOR=1 rồi dùng Text.from_ansi theo test help sẵn có, giữ nguyên kiểm tra nội dung và no-HTTP.

Đã thử mở browser/context mới để kiểm live v2/HN trong lượt này: doctor local exit 0 với JSON hợp lệ và không HTTP; login exit 1, chưa có response FAP được quan sát. Các command xác thực mới sau login **chưa chạy**, không ghi chúng là live pass hoặc live-failed endpoint. Logout exit 0; session và thư mục tạm đã dọn. Không suy nguyên nhân lỗi login từ việc không có response.

## Live đọc v2/HN ngày 24/10/2026

Sau khi người dùng xác nhận mở login mới, chạy code tại `0e0c01c8027458d01f215a694351aeb05efb7e7d` với browser/context trống và session tạm riêng. **14 lần command đều exit 0**, JSON stdout hợp lệ; observer giữ 14 request thuộc 12 operation. Một request `GetSemester` bổ sung dùng để chọn input hợp lệ cho subjects theo kỳ trước khi gọi CLI không thuộc số request observer; không diễn giải con số đó là tổng traffic FEID/FAP.

| Command/nhóm | HTTP / body code | Kết quả đã lọc |
|---|---|---|
| `doctor` local | Không HTTP | JSON hợp lệ, không đọc session |
| Login/handshake, refresh và đọc student sau refresh | 200 / 200 | Thành công, không lưu identity/token vào báo cáo |
| `doctor --online` v2 | 200 / 200 | Bootstrap GetApiActive trả boolean; không coi là kiểm session/campus tài khoản |
| `courses` | 200 / 200 | Data list không rỗng, có resolver kỳ |
| `other subjects --semester` | 200 / 200 | Input kỳ lấy từ endpoint thật, không đoán; data list không rỗng |
| `other balance` | 200 / 200 | Data string không rỗng; không suy ra currency/amount/nợ |
| `news --search` | 200 / 200 | Data list không rỗng; search text tổng quát, không chứa dữ liệu tài khoản |
| `transcript` | 200 / 200 | Data string không rỗng; chưa kiểm cấu trúc/formatter nghiệp vụ |
| `training` | 200 / 200 | Data list rỗng hợp lệ; chưa phải positive nghiệp vụ |
| `marks --summary` | 200 / 200 | Envelope data list không rỗng; không thử format XML wrapper |
| `info photo` JSON | 200 / 200 | Data string không rỗng; không đọc/in nội dung ảnh, không chứng minh URL/Base64 |
| `logout` | Không HTTP | Session/lock và thư mục tạm đã dọn |

Không thay request/response hoặc dùng capture credential. Không chạy rating list v1, rating submit, push hoặc feedback ghi trong lượt này. Các command mới trên **v1 vẫn chưa live**, rating list v1 mới có fixture, và schema/ack thao tác ghi còn gate.

CI của đúng commit `0e0c01c` đã đạt [11/11 job](https://github.com/WindowScary321/myfap-api-cli/actions/runs/40064917612), gồm source và artifact smoke Ubuntu/Windows × Python 3.9/3.11. Đây không phải publish/release.

Kết quả full suite và review không thay cho live ở version/campus khác. Các skip/failure/unknown trong [coverage Phase 4](phase4-coverage.md) và TODO positive fee/survey vẫn giữ nguyên. Chỉ metadata allowlist được lưu; payload và biến nhạy cảm không vào GitHub.
