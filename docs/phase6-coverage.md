# Coverage Phase 6 — đang triển khai

Nhóm đọc ban đầu tại `c829b7004ea2dbb7f99cf1dc3827070039bb9ea5`, bổ sung rating list v1 tại `4c29b81f0e61d11ccb6d047060680cbcf60ab121`, đang review trong [Draft PR #10](https://github.com/WindowScary321/myfap-api-cli/pull/10). V1 vẫn mặc định, v2 opt-in; **chưa tag/publish**. Đây là capability của code đang review, không phải tính năng đã có trên PyPI hoặc bằng chứng mọi endpoint hoạt động live.

## Command và contract đã nối qua CLI

URL dữ liệu v1 là `https://api.fpt.edu.vn/fap/api/MyFAP/<operation>`; v2 là `https://fap-proxy.fpt.edu.vn/MyFAP/<operation>`. Tất cả operation dữ liệu trong bảng dùng GET. Không ghi query có giá trị, token, checksum hoặc thông tin tài khoản vào tài liệu.

| Command | Operation | v1 / v2 | Điểm contract quan trọng | Bằng chứng hiện tại |
|---|---|---|---|---|
| `other balance` | `GetBalance` | Có / Có | Ký v1 bằng roll number; không lookup kỳ; không suy ra currency/nợ/invoice | Fixture hai version; live v2/HN 200/200, v1: xem kết quả APHL bên dưới |
| `courses --semester` | `GetCourseOfSemester` | Có / Có | Query `semester` chữ thường; thiếu option dùng resolver `startDate` | Fixture explicit/latest; live v2/HN 200/200, v1: xem kết quả APHL bên dưới |
| `other subjects --semester` | `GetSubjectBySemester` | Có / Có | Query `Semester` chữ hoa; signer v1 là semester; không có option vẫn `GetSubjets`, không lookup kỳ | Fixture hai version; live v2/HN 200/200, v1: xem kết quả APHL bên dưới |
| `news --search --type` | `SearchNews` | Có / Có | `type`, `keysearch`; signer v1 là type; search rỗng bị chặn | Fixture Unicode/reserved characters; live v2/HN 200/200 |
| `transcript`, `transcript --pretty` | `AcademicTranscript` | Có / Có | Không lookup kỳ; `--pretty` phân tích HTML thành JSON keyed theo header từng bảng (chuẩn hoá `&nbsp;`), mặc định giữ chuỗi gốc | Fixture parser/CLI; live v2/HN 200/200 — `--pretty` cho 2 bảng 49+2 dòng, header khớp dữ liệu thật |
| `other training --semester` | `GetDiemphongtrao` | Có / Có | Query `semester`; thiếu option dùng resolver | Fixture; live v2/HN 200/200 với bound key, list rỗng |
| `marks --summary` | `GetSemesterMark` | Có / Có | Không có query kỳ; v1 `CampusCode`, `rollNumber`, `Authen`, **không checksum**; v2 có query Authen mới sau refresh | Fixture parser/refresh; live v2/HN 200/200 với envelope data list |
| `info photo` | `RetriveImage` | Có / Có | Chỉ JSON, bảo toàn chuỗi opaque kể cả HTML entity; không tải URL hoặc decode ảnh | Live v2/HN 200/200, data string; định dạng ảnh chưa xác minh |
| `other rating list` | `GetStudentRate` | Có / Không | V1 đọc, ký bằng roll number; v2 stub bị chặn trước load session/HTTP | Fixture và live v1/APHL 200/200, danh sách rỗng |
| `other feedbacks` | `GetStudentFeedbacks` | Không / Có | V2-only; query `CampusCode`, `rollNumber`, không query `Authen` (bytecode dòng 613); credential qua header Bearer | Fixture contract; live 24/10 200/200 list rỗng — item schema chưa positive |
| `doctor --stdout` | Không gọi HTTP | Local | Chỉ explicit/default, không đọc/khóa/refresh session, không in config path/identity/token | Test CLI và chạy local thật |
| `doctor --api-version v2 --online` | `GetApiActive`, `GetVersion` | Không / POST bootstrap | Probe `api_active` boolean rồi `backend_version` chuỗi; query/body rỗng, bootstrap campus HN; không xác nhận session/campus tài khoản | Fixture và live bootstrap v2 200/200; GetVersion POST 200 (GET 405, v1 404), `myfap version` vẫn offline |

`marks --summary` từ chối `--semester`, `--courseid`, `--pretty` trước auth. `myfap version` vẫn chỉ đọc package version. Doctor không tự lấy version/campus từ session: điều này được ghi rõ trong report để giữ local mode không có tác dụng phụ.

Cột v1/v2 là capability trong code, không bảo đảm backend mọi campus trả success. Kết quả live v1/APHL có các lỗi 404/201 được giữ nguyên ở phần cuối; không đổi thành unsupported hoặc dữ liệu rỗng.

**Namespace hiện tại:** training và nhóm rating nằm trong `other`: `myfap other training`, `myfap other rating list`. Không giữ alias ở root. Các lượt live lịch sử bên dưới chạy trước khi đổi namespace nên giữ nguyên nhãn command cũ; endpoint/callback và capability không đổi. Lượt đổi namespace chỉ kiểm CLI/help/HTTP giả, không chạy lại login/FAP. Focused FORCE_COLOR=1 đạt 17/17; full Windows Python 3.9 và 3.11 mỗi bản 394 test, 390 đạt/4 skip, exit 0. Help mới được kiểm cả UTF-8/cp1252 ở group lồng ba cấp; option tại leaf vẫn override root/group.

## Policy và phần chưa xác minh

- Các read mới kế thừa binding và tối đa một refresh/retry khi server báo expiry rõ. Không tự refresh/logout từ 201 không rõ nghĩa, 403, timeout, 5xx hoặc App Check. Capability đọc không mở đường ghi.
- Với transcript/training/summary, caller của APK (module_599.js) gọi wrapper GET **không truyền credential header**: wrapper (dòng 898–906) mặc định credential chuỗi rỗng khi thiếu tham số thứ tư, `_buildHeaders` (747–781) khi đó tạo header không `Authorization` và `_makeChecksum` (726–746) ký bằng bootstrap token. Chỉ `GetSemesterMark` (218–224) đặt FAP key trong query `Authen`; `AcademicTranscript` (266–272) và `GetDiemphongtrao` (280–286) chỉ có query campus/roll/semester. CLI giữ **policy authenticated read dùng FAP key của binding hiện tại** cho cả ba — không sao chép credential rỗng của app, không thử unauth rồi fallback, không nới reader chung. Thí nghiệm transport có kiểm soát (bảng cuối file) cho thấy proxy hiện tại **từ chối** mọi biến thể lệch khỏi policy này; vậy nhánh credential rỗng trong bytecode không được server chấp nhận — hoặc app thật bơm token ở tầng khác (Axios wrapper `module_1(Axios2)` chưa phục dựng) hoặc proxy đã đổi hành vi so với APK build 31. CLI không thay đổi.
- Reader tổng kết chỉ dành cho `GetSemesterMark`: raw JSON array, envelope có data list, hoặc JSON string chứa trọn array. Giới hạn xử lý cục bộ 1 MiB. Không cắt tùy tiện chuỗi giữa dấu ngoặc; XML/HTML wrapper chưa xác minh bị từ chối bằng lỗi payload an toàn. Reader chung của operation khác không được nới lỏng.
- Photo JSON không đồng nghĩa đã hỗ trợ xuất ảnh binary. Không tự fetch URL bất kỳ hoặc chuyển credential sang host ảnh.
- Rating list v1 có code/fixture; URL là `https://api.fpt.edu.vn/fap/api/MyFAP/GetStudentRate`. Rating list v2 là stub và bị chặn. Rating submit/push/feedback đầy đủ chưa được mở bởi các thay đổi này. Những gate tại [tasks/phase6.md](../tasks/phase6.md) vẫn còn pending, Phase 6 **chưa hoàn tất**.
- `GetVersion` đã mở cho `doctor --online` ngày 24/10/2026 sau khi chốt contract bằng probe: caller APK dùng GET nhưng proxy trả 405; POST body `{}` bootstrap đạt 200 với data chuỗi ngắn (chấp nhận bootstrap lẫn FAP key Bearer); route v1 trả 404. `myfap version` tiếp tục chỉ đọc package version.

## Kiểm chứng

Test mới dùng CLI/auth/client thật với session tổng hợp và HTTP giả; không dùng capture/account làm fixture. Các chu kỳ RED đã ghi nhận command/option/module chưa tồn tại, GREEN sau implementation; reader bảo toàn lỗi HTTP/App Check/expiry, không đổi lỗi thành mảng rỗng.

Sau rating list, full local Windows có 391 test trên mỗi Python 3.11/3.9, 387 đạt/4 skip, exit 0. Venv Python 3.9 từng lỗi tzdata UTC độc lập với command; cài lại đúng version khóa trong venv test đã phục hồi probe UTC và toàn suite, không đổi lockfile.

Nghiệm thu nhóm mục 1 (24/10/2026): `ReadSliceAcceptanceTests` bổ sung 5 test tại seam CLI cho cả bốn lát cắt đọc trên hai version — header v2 đúng contract client (`ClientCode`, `CampusCode`, `Authorization` Bearer, `Checksum` dạng `chữ ký:timestamp giây`, GET không body/`Content-Type`), expiry retry đúng một lần với credential mới rồi dừng, và App Check/timeout/HTTP 503/malformed giữ một request, không refresh/fallback, stdout rỗng khi lỗi. Test GREEN ngay vì xác nhận hành vi đã có; focused `tests.test_phase6_reads` 22/22, full Windows 399 test, 395 đạt/4 skip, exit 0.

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

Không thay request/response hoặc dùng capture credential. Không chạy v1 hoặc thao tác ghi trong lượt v2 này; kết quả v1 độc lập ở phần sau. Schema/ack thao tác ghi còn gate.

CI của đúng commit `0e0c01c` đã đạt [11/11 job](https://github.com/WindowScary321/myfap-api-cli/actions/runs/40064917612), gồm source và artifact smoke Ubuntu/Windows × Python 3.9/3.11. Đây không phải publish/release.

Kết quả full suite và review không thay cho live ở version/campus khác. Các skip/failure/unknown trong [coverage Phase 4](phase4-coverage.md) và TODO positive fee/survey vẫn giữ nguyên. Chỉ metadata allowlist được lưu; payload và biến nhạy cảm không vào GitHub.

## Live đọc v1/APHL ngày 24/10/2026

Người dùng xác nhận mở browser/context mới, session tạm riêng trên code `ca09b1106ddacca96145a36df0b0668bf15ae52f`. **14 lần command: 10 exit 0, 4 exit 1; harness exit 1**, không sửa response hoặc fallback version. Observer giữ 14 request thuộc 12 operation; một GetSemester chuẩn bị input subjects nằm ngoài observer. Không đưa raw response/query có giá trị hoặc identity vào báo cáo.

| Command/nhóm | HTTP / body | Exit | Kết quả đã lọc |
|---|---|---:|---|
| Doctor local | Không HTTP | 0 | JSON hợp lệ, không load session |
| Login, refresh và student sau refresh | 200 / 200 | 0 | Handshake POST thành công, đọc đối chứng sau refresh đạt |
| `courses` | 404 / không code FAP | 1 | GetSemester trước đó 200/200; chưa xác định nguyên nhân 404 của GetCourseOfSemester |
| Subjects theo kỳ | 200 / 200 | 0 | List không rỗng; input kỳ lấy từ API thật |
| Balance | 200 / 200 | 0 | String không rỗng; không suy giá trị hoặc trạng thái nợ |
| News search | 200 / 201 | 1 | Data null; chưa có bằng chứng expiry rõ hoặc empty hợp lệ |
| Transcript | 200 / 200 | 0 | String rỗng; chưa xác minh positive schema |
| Training | 200 / 201 | 1 | Data null; chưa rõ nguyên nhân |
| Marks summary | 404 / không code FAP | 1 | Chưa biết nguyên nhân; không thử format XML vì HTTP đã lỗi |
| Photo JSON | 200 / 200 | 0 | Data null hợp lệ, không ghi nhận có ảnh |
| Rating list | 200 / 200 | 0 | List rỗng từ endpoint v1 thật, không phải stub v2; chưa có item schema/ID để kiểm submit |
| Logout | Không HTTP | 0 | Session/lock và thư mục tạm đã dọn |

Đối chiếu code với caller APK: courses/training giữ `semester` chữ thường và signer roll; search ký bằng type; summary v1 `CampusCode`, rollNumber, Authen, không checksum. Chưa tìm được sai lệch request được xác nhận để sửa client. HTTP 404 không tự chứng minh route unsupported trên mọi campus; code 201 không tự chứng minh hết phiên. Các request đọc khác trong cùng lượt vẫn thành công; không biến bốn lỗi thành `[]`, không tự refresh vì 201 không rõ và không gọi v2 ngầm.

Khảo sát caller bổ sung: training dùng **semesterName** tại `module_1303.js:114–117,288–302` và `module_1300.js:108–110,222–229`; không có căn cứ đổi thành termID. Với courses, chỉ thấy facade forward (`549_AlertMaintain.js:262–265`), chưa có UI caller chứng minh semesterName hay termID ở v1. Search UI (`module_1291.js:251–263,345–358`) còn có trim/lower và bước XML entity encoding với receiver phục dựng chưa rõ; CLI hiện truyền search text qua params. Input live tổng quát đã trim/lower, chưa xác nhận đây là nguyên nhân 201 hoặc có căn cứ sửa contract từ decompile. Không dùng các bất định này để tự thử ID/alias khác hay double URL-encode.

Regression tổng hợp `V1ObservedFailureTests` giữ bốn trạng thái 404/201 là lỗi CLI với stdout rỗng, một request, không refresh/fallback và không đổi session. Đây là test policy bằng mã/shape đã lọc, không phải bằng chứng sửa backend hoặc dữ liệu thật làm fixture. Theo dõi nguyên nhân tại [TODO](../tasks/todo.md). Rating submit/push/feedback ghi vẫn chưa mở; Phase 6 chưa hoàn tất.

## Live nghiệm thu mục 2 (24/10/2026, v2/HN)

Chạy trên máy cá nhân bằng session thật của người dùng ở code `c34d7ed`; output raw chỉ xử lý cục bộ trên máy đó và đã xóa sau khi trích metadata, không đưa lên repository/GitHub. Không thay request/response; không chạy thao tác ghi.

| Command/nhóm | HTTP / body code | Metadata đã lọc |
|---|---|---|
| `info student` (đối chứng) | 200 / 200 | List 1 phần tử; các trường identity dạng chuỗi như shape fixture tổng hợp |
| `transcript` | 200 / 200 | Data chuỗi ~10,5 KB là mảnh HTML bảng: 53 `<tr`, 504 `<td`, không có thẻ `<table>` bao; formatter nghiệp vụ chưa tích hợp |
| `other training` (tự chọn kỳ mới nhất) | 200 / 200 | List rỗng; không phải positive nghiệp vụ |
| `marks --summary` | 200 / 200 | Envelope data list 32 phần tử; mỗi phần tử đúng 5 khóa `SubjectCode`, `ClassName`, `AverageMark`, `Status`, `GradeStatus` — positive schema thật đầu tiên cho GetSemesterMark |

Lượt này cùng bằng chứng bytecode ở phần Policy khép hộp credential v2 của transcript/training/summary trong [phase6.md](../tasks/phase6.md) mục 2. Schema nghiệp vụ transcript (HTML) và training vẫn giữ nhãn chưa kiểm chứng; positive schema summary là xác nhận dạng dữ liệu trên một tài khoản, chưa phải nghiệm thu backend mọi campus.

### Thí nghiệm transport có kiểm soát (24/10/2026)

Sau khi đọc bytecode cho thấy nhánh credential rỗng, maintainer yêu cầu thử đưa biến thể đó vào kiểm chứng. Thí nghiệm gửi trực tiếp năm biến thể header cho cả ba operation bằng session thật (chỉ đọc GET, metadata đã lọc, không giá trị) trước khi đổi CLI:

| Biến thể | Authorization | Checksum ký bằng | Kết quả cả 3 operation |
|---|---|---|---|
| App-parity đủ theo `_buildHeaders` (kể cả `Content-Type` json) | không có | bootstrap token | HTTP 400, body không JSON |
| Bearer FAP key + checksum bootstrap | FAP key | bootstrap token | HTTP 400 — checksum phải ký đúng credential trong Authorization |
| Bearer bootstrap token (kiểu `_getNoAuth`) | bootstrap token | bootstrap token | HTTP 500 — qua tầng xác thực, hỏng tầng nghiệp vụ |
| Bearer FAP key + checksum theo key (policy CLI) | FAP key | FAP key | HTTP 200, body 200 — duy nhất được chấp nhận |

Kết luận: proxy v2 hiện tại chỉ chấp nhận cặp `Authorization: Bearer <FAP key>` + `Checksum` ký bằng đúng key đó cho cả ba operation; nhánh credential rỗng trong bytecode bị từ chối. CLI giữ nguyên policy — nay có bằng chứng hai chiều trên một tài khoản/campus (HN), không suy rộng cho mọi campus hay suy luận app thật gửi gì lúc runtime.

## Mở rộng endpoint sau phân tích khoảng trống (24/10/2026)

Đối chiếu 82 route của APK với adapter ([phân tích khoảng trống](endpoint-gap-analysis.md)) mở thêm hai capability theo bằng chứng probe cùng ngày, chạy trên máy cá nhân với session thật, metadata đã lọc:

- **`myfap other feedbacks` → `GetStudentFeedbacks`** (v2-only, `module_599.js:601-623`): query `{CampusCode, rollNumber}` không có `Authen` (bytecode dòng 613), credential qua Bearer. Live v2/HN HTTP/body 200, data list rỗng — envelope chuẩn, item schema chưa positive, giữ nhãn unverified như rating list. RED 3 test → GREEN sau implementation.
- **`doctor --api-version v2 --online` thêm `GetVersion`**: probe chạy sau khi `GetApiActive` hợp lệ, report có `backend_version`. Contract: GET bị 405, POST body `{}` bootstrap đạt 200 với data chuỗi ngắn, route v1 404. Test hiện có cập nhật (2 probe cho lượt online) và test mới chặn version không phải chuỗi; một lỗi thứ tự thật bị test bắt (probe version chạy trước khi validate active) đã sửa.

Full suite sau hai feature: 403 test, 399 đạt/4 skip, exit 0 trên Windows Python 3.11; kiểm CLI thật với session cá nhân: `other feedbacks` exit 0 (200, list rỗng), `doctor --online` exit 0 (`api_active` true, `backend_version` chuỗi 3 ký tự).

## Quét toàn bộ lệnh đọc bằng session/browser mới (24/10/2026)

Đóng checkpoint nhóm đọc: login FEID mới bằng browser context mới với session tạm riêng (hai lượt — lượt chính cho bộ quét, lượt phụ cho lệnh bảng), chạy toàn bộ command đọc trên v2/HN, raw chỉ xử lý cục bộ trên máy cá nhân và xóa sau khi trích metadata; parameter (`CourseId`, `SubjectCode`/`ClassName`) trích từ response trong thư mục tạm, không in giá trị. Cả hai session đã logout.

| Phân loại | Command (HTTP/body code, dạng data) |
|---|---|
| Success có dữ liệu | info student 200/list(1); info campus 200/list(1); photo 200/str ngắn không rỗng (lần đầu có chuỗi); courses 200/list(5) — resolver kỳ tự chạy; schedule 200/list(64); schedule --ics vcalendar chuẩn CRLF; week-timetable 200/list(6); marks --summary 200/list(32); exams 200/list(6); attendance 200/list(5); **attendance detail 200/list(1) — positive đầu tiên (param trích từ courses)**; news 200/list(10); **news --search 200/list(50)**; notification 200/list(49); fee 200/list(1) không rỗng — **không đóng positive fee, schema nghiệp vụ chưa đối chiếu**; balance 200/str ngắn; subjects 200/list lớn; transcript 200/str ~10,5 KB; doctor local/online exit 0 |
| Success, data rỗng | marks 200/list(0); marks --courseid 200/str(0) (CourseId thật trích từ courses; chuỗi rỗng, chưa phải positive nội dung); applications 200/list(0); other training 200/list(0); other feedbacks 200/list(0) |
| Theo contract đặc thù | other survey HTTP 200/body 404 exit 0 (not-found cho phép); other feedback/profile 200/data boolean |
| Không áp dụng trên v2 | other rating list exit 1 — v1-only, chặn trước HTTP đúng thiết kế |
| Lệnh bảng | semesters exit 0, bảng UTF-8 ~29 dòng kỳ (lượt phụ, login riêng) |
| Ghi chú harness | Lượt chính bị lỗi harness ở `semesters --stdout` (lệnh bảng không có option này → exit 2, không phải lỗi CLI; chạy lại đúng cú pháp ở lượt phụ). `other subjects --semester` không lặp lại trong lượt này vì cùng lỗi; bằng chứng lượt 24/10 trước (200/200, input kỳ từ API thật) vẫn đứng |

Không đóng các mục cấm: positive fee/survey giữ mở (dữ liệu chưa đối chiếu nghiệp vụ), các finding v1 giữ nguyên — không dùng kết quả v2 để đóng. Transcript HTML và các formatter nghiệp vụ tiếp tục nhãn chưa kiểm chứng.

- **`myfap exams --ics` (thêm `--full`)**: mở rộng xuất lịch thi ra định dạng iCalendar chuẩn RFC 5545 (giờ VN, UID/DTSTAMP UTC, CRLF); mặc định đưa đầy đủ thông tin quan trọng (Môn, Phòng thi `roomNo`, Ngày công bố `dateofPublication`), chỉ ẩn mã slot UUID và ghi chú phụ; cờ `--full` kèm toàn bộ thông tin phụ; xuất JSON mặc định bảo toàn 100% dữ liệu gốc. RED→GREEN qua parser converter và CLI seam; live v2/HN đạt 7 sự kiện thật trên tài khoản kiểm chứng. Mặc định không `--ics` vẫn giữ JSON nguyên bản.
