# Command, endpoint và URL của CLI hiện tại

Tài liệu này hợp nhất mapping command → operation → method/URL → capability → bằng chứng. Mapping đối chiếu code tại commit `bc8a7ee3131093432de427e1954743ee34618f45`; bảng không bổ sung endpoint hoặc command mới. V1 vẫn mặc định, v2 opt-in qua `--api-version v2` hoặc binding session.

## Bổ sung Phase 6 đang review

Mapping theo mốc Phase 5 trong tài liệu này được giữ làm lịch sử. Capability đọc mới, query ngoại lệ, doctor và giới hạn hiện tại nằm tại [coverage Phase 6](phase6-coverage.md). Các dòng “chưa tích hợp” ở phần inventory Phase 5 bên dưới cần đọc theo mốc commit ban đầu, không phải trạng thái code Phase 6 mới nhất. Chưa publish Phase 6 hoặc đánh dấu các luồng ghi đã đạt.

## Phạm vi theo kế hoạch

- **Phase 4:** phủ command đọc hiện có, lập coverage và kiểm chứng live. Xem [coverage Phase 4](phase4-coverage.md).
- **Phase 5:** chuẩn bị và nghiệm thu pipeline phát hành. Có code và CI xanh chưa đồng nghĩa đã publish `0.2.0`; xem [checklist Phase 5](../tasks/phase5.md).
- **Phase 6:** thêm các chức năng/API mới, nghiệm thu trước khi tạo tag/publish theo quyết định ngày 23/10/2026. Không tự mở route chỉ vì có tên trong APK; cần contract, capability, fixture và kiểm chứng riêng.

Ba giai đoạn trên theo mục Phase 4–6 trong `PLAN.md` và `PLAN-PHASES.md` của workspace phân tích. Hai file kế hoạch nằm ngoài repository CLI; không cần đóng gói chúng vào artifact.

## Quy ước

- URL bên dưới là URL endpoint **không có giá trị query**, không chứa token/checksum/identity. Query/header/body theo [contract v2](v2-contracts.md) và code tương ứng; không dùng URL tĩnh này để bỏ qua signer hoặc session binding.
- Cột method ghi theo thứ tự **v1 / v2**. Các operation đọc nghiệp vụ vẫn có thể dùng POST ở bootstrap. Không suy chính sách retry chỉ từ HTTP method.
- Trừ `campuses` và request bootstrap chẩn đoán, các command dữ liệu đang hỗ trợ luồng **student**. Không suy ra donor/employee capability.
- Khi không truyền `--semester`, command theo kỳ gọi thêm `GetSemester`. `week-timetable` không có `--week` gọi thêm `GetWeekByDate`; `--date` quyết định năm khi thiếu `--year`.
- `load_session` có thể dùng session local hoặc điều phối refresh/handshake khi cần. Không coi mỗi command đều gửi handshake. `refresh` gọi token endpoint FEID rồi handshake FAP; không phải endpoint dữ liệu riêng.

## Ma trận command đang có

| Command/caller | Operation | Method v1 / v2 | URL v1 | URL v2 | Capability và bằng chứng |
|---|---|---|---|---|---|
| `campuses` | `GetAllActiveCampus` | GET / POST | `https://api.fpt.edu.vn/fap/api/MyFAP/GetAllActiveCampus` | `https://fap-proxy.fpt.edu.vn/MyFAP/GetAllActiveCampus` | Public/bootstrap; fixture hai version, live v2/HN 200/200 |
| `login`, handshake của `refresh`/auth | `AuthenticationByFeId` | GET / POST | `https://api.fpt.edu.vn/fap/api/MyFAP/AuthenticationByFeId` | `https://fap-proxy.fpt.edu.vn/MyFAP/AuthenticationByFeId` | Student/handshake; binding campus/version; live v2/HN 200/200 |
| `semesters`, resolver kỳ | `GetSemester` | GET / GET | `https://api.fpt.edu.vn/fap/api/MyFAP/GetSemester` | `https://fap-proxy.fpt.edu.vn/MyFAP/GetSemester` | Student; fixture và live v1/v2; lượt mới v2/HN 200/200 |
| `schedule`, `schedule --ics` | `GetActivityStudent` | GET / GET | `https://api.fpt.edu.vn/fap/api/MyFAP/GetActivityStudent` | `https://fap-proxy.fpt.edu.vn/MyFAP/GetActivityStudent` | Student/read; live JSON/ICS v2/HN đạt |
| Resolver tuần của `week-timetable` | `GetWeekByDate` | GET / GET | `https://api.fpt.edu.vn/fap/api/MyFAP/GetWeekByDate` | `https://fap-proxy.fpt.edu.vn/MyFAP/GetWeekByDate` | Read/helper; live v2/HN 200/200, data integer |
| `week-timetable` | `GetActivityStudentByWeek` | GET / GET | `https://api.fpt.edu.vn/fap/api/MyFAP/GetActivityStudentByWeek` | `https://fap-proxy.fpt.edu.vn/MyFAP/GetActivityStudentByWeek` | Student/read; live v2/HN 200/200 |
| `marks` | `GetStudentMark` | GET / GET | `https://api.fpt.edu.vn/fap/api/MyFAP/GetStudentMark` | `https://fap-proxy.fpt.edu.vn/MyFAP/GetStudentMark` | Student/read; lượt mới v2/HN 200/200 với danh sách rỗng |
| `marks --courseid`, thêm `--pretty` để parse HTML | `GetMarkByCourse` | GET / GET | `https://api.fpt.edu.vn/fap/api/MyFAP/GetMarkByCourse` | `https://fap-proxy.fpt.edu.vn/MyFAP/GetMarkByCourse` | Fixture hai version; lượt mới skip vì không lấy được CourseId phù hợp, không ghi live pass |
| `exams` | `GetScheduleExam` | GET / GET | `https://api.fpt.edu.vn/fap/api/MyFAP/GetScheduleExam` | `https://fap-proxy.fpt.edu.vn/MyFAP/GetScheduleExam` | Student/read; live v2/HN 200/200 |
| `attendance` | `GetStudentAttendances` | GET / GET | `https://api.fpt.edu.vn/fap/api/MyFAP/GetStudentAttendances` | `https://fap-proxy.fpt.edu.vn/MyFAP/GetStudentAttendances` | Student/read; live v2/HN 200/200 |
| `attendance --subjectcode --classname` | `getCourseAttendance` / `GetCourseAttendance` | GET / GET | `https://api.fpt.edu.vn/fap/api/MyFAP/getCourseAttendance` | `https://fap-proxy.fpt.edu.vn/MyFAP/GetCourseAttendance` | Fixture alias/case; lượt mới skip vì không lấy được cặp tham số phù hợp |
| `applications` | `GetApplication` | GET / GET | `https://api.fpt.edu.vn/fap/api/MyFAP/GetApplication` | `https://fap-proxy.fpt.edu.vn/MyFAP/GetApplication` | Student/read; live v2/HN 200/200 với danh sách rỗng |
| `news` | `GetTop10News` | GET / GET | `https://api.fpt.edu.vn/fap/api/MyFAP/GetTop10News` | `https://fap-proxy.fpt.edu.vn/MyFAP/GetTop10News` | V2/HN live 200/200; v1/APHL vẫn lỗi 200/201 ngày 19/10 |
| `info student` | `GetStudentById` | GET / GET | `https://api.fpt.edu.vn/fap/api/MyFAP/GetStudentById` | `https://fap-proxy.fpt.edu.vn/MyFAP/GetStudentById` | Student/read; live v2/HN 200/200 trước và sau refresh |
| `info campus` | `GetCampusInfo` | GET / GET | `https://api.fpt.edu.vn/fap/api/MyFAP/GetCampusInfo` | `https://fap-proxy.fpt.edu.vn/MyFAP/GetCampusInfo` | Student/read; live v2/HN 200/200 |
| `other fee` | `GeFeeByRoll` | GET / GET | `https://api.fpt.edu.vn/fap/api/MyFAP/GeFeeByRoll` | `https://fap-proxy.fpt.edu.vn/MyFAP/GeFeeByRoll` | V2/HN live 200/200, data không rỗng; chưa đối chiếu schema nghiệp vụ. V1/APHL HTTP 404 ngày 19/10 |
| `other subjects` | `GetSubjets` | GET / GET | `https://api.fpt.edu.vn/fap/api/MyFAP/GetSubjets` | `https://fap-proxy.fpt.edu.vn/MyFAP/GetSubjets` | Student/read; live v2/HN 200/200; timeout tối thiểu 30 giây |
| `other feedback` | `CheckOpenFeedBack` | GET / GET | `https://api.fpt.edu.vn/fap/api/MyFAP/CheckOpenFeedBack` | `https://fap-proxy.fpt.edu.vn/MyFAP/CheckOpenFeedBack` | Chỉ kiểm tra/read, không submit feedback; live v2/HN 200/200, data boolean |
| `other profile` | `CheckUpdateProfile` | GET / GET | `https://api.fpt.edu.vn/fap/api/MyFAP/CheckUpdateProfile` | `https://fap-proxy.fpt.edu.vn/MyFAP/CheckUpdateProfile` | Chỉ kiểm tra/read, không cập nhật hồ sơ; live v2/HN 200/200, data boolean |
| `other notification` | `GetNotificationByRoll` | GET / GET | `https://api.fpt.edu.vn/fap/api/MyFAP/GetNotificationByRoll` | `https://fap-proxy.fpt.edu.vn/MyFAP/GetNotificationByRoll` | V2/HN live 200/200; v1/APHL vẫn lỗi 200/201 ngày 19/10 |
| `other survey` ở cả hai API version | `GetRequiredSurvey` | GET / GET | `https://survey.fpt.edu.vn/API/myFAP/GetRequiredSurvey` | `https://survey.fpt.edu.vn/API/myFAP/GetRequiredSurvey` | Dịch vụ riêng, signer riêng; live HTTP 200/body 404, không phải positive survey |
| Chỉ Python API `MyFapEssential.get_api_active()`; chưa có command CLI | `GetApiActive` | Không hỗ trợ / POST | — | `https://fap-proxy.fpt.edu.vn/MyFAP/GetApiActive` | Public/bootstrap diagnostic v2; fixture, chưa gọi trong lượt live mới; không auto-switch/fallback |

`version` và `--help` không cần API. `logout` chỉ xóa session local, không phải request logout FEID/FAP. Các command export JSON/ICS/pretty dùng cùng endpoint dữ liệu, không tạo route mới.

### OAuth ngoài API nghiệp vụ

FEID lấy metadata tại `https://feid.fpt.edu.vn/.well-known/openid-configuration`; authorization, token và JWKS dùng endpoint discovery đã kiểm định. Browser thực hiện Authorization Code + PKCE; callback URI không phải endpoint dữ liệu FAP. Không ghi URL authorize/callback thực, code/token/cookie hoặc query có giá trị vào tài liệu. Xem [OAuth và session](oauth-session.md).

## Lượt live mới ngày 23/10/2026

Chạy trên commit `bc8a7ee3131093432de427e1954743ee34618f45`, **v2/HN**, browser context mới, file session tạm riêng; timeout HTTP 30 giây. Harness gọi entry point CLI thật và chỉ quan sát metadata sau HTTP, không thay request/response. Đây không phải replay capture hoặc fixture.

- **22 lần chạy command**, tất cả exit 0; **28 request FAP/survey quan sát được, 19 operation khác nhau**. Con số không bao gồm các request discovery/JWKS/token/browser của FEID; không diễn giải thành tổng số request mạng.
- Mỗi JSON stdout được kiểm parse. ICS được đọc bằng `icalendar`, có sự kiện, UID và DTSTAMP UTC, giữ CRLF; chưa thử import vào ứng dụng lịch.
- `marks` ở kỳ tự chọn và `applications` trả danh sách rỗng hợp lệ với HTTP/body 200. Không lấy danh sách rỗng này làm bằng chứng cho dữ liệu positive hoặc điểm chi tiết.
- Hai nhóm `marks detail` và `attendance detail` **skip do không lấy được tham số phù hợp trong lượt này**. Không đoán ID, không suy ra endpoint unsupported hoặc payload không tồn tại ở mọi kỳ.
- Fee có danh sách không rỗng nhưng chưa kiểm nội dung `IsPaid`, amount/invoice bằng dữ liệu nghiệp vụ; TODO schema positive fee vẫn mở. Survey tiếp tục not-found; TODO positive survey vẫn mở.
- Refresh FEID và handshake thành công; `info student` sau refresh vẫn HTTP/body 200. Không chạy thao tác ghi nghiệp vụ, không gây lỗi session có chủ ý.
- Session/lock và thư mục tạm đã dọn. Chỉ metadata allowlist được giữ; không lưu raw response, nội dung học vụ, thông tin tài khoản, credential, query có giá trị hoặc ảnh màn hình vào repository/GitHub.

Không chạy lại v1 trong lượt này. Kết quả v2 không đóng ba finding v1 trong [TODO](../tasks/todo.md).

## Các endpoint còn lại không thuộc triển khai Phase 5

Đây là phạm vi **chưa có command/capability tương ứng**, không phải danh sách chức năng đã hoàn tất:

| Nhóm mở rộng dự kiến | Operation | Trạng thái |
|---|---|---|
| Transcript / marks summary | `AcademicTranscript`, `GetSemesterMark` | Phase 6; transcript có ở cả v1/v2, chưa tích hợp CLI |
| Courses / subjects theo kỳ / training | `GetCourseOfSemester`, `GetSubjectBySemester`, `GetDiemphongtrao` | Phase 6; phải giữ đúng case từng query |
| Balance / tìm news / ảnh | `GetBalance`, `SearchNews`, `RetriveImage` | Phase 6; chưa có command tương ứng |
| Doctor / kiểm version backend | `GetApiActive`, `GetVersion` | `GetApiActive` đã có Python method v2 nhưng chưa có CLI; `GetVersion` chưa hỗ trợ |
| Rating / push | `GetStudentRate`, `AddRate`, `UpdateTokedevices`, `UpdateTokenDonor` | Chưa mở CLI; phân biệt stub v2 và GET ghi; cần schema, xác nhận và không retry ghi |
| Feedback đầy đủ | `GetStudentFeedbacks`, `GetStudentFeedbackForm`, `SubmitStudentFeedback` | Không đồng nhất với `other feedback`; schema submit/capability chưa đầy đủ |
| Google/donor/employee, FEID server-code exchange | Các flow tương ứng trong inventory | TODO riêng; không suy hỗ trợ chỉ từ route có trong APK |

Inventory và method từng route proxy nằm trong [ma trận v2](v2-contracts.md#ma-trận-route-v2). Thêm các endpoint này vào Phase 5 sẽ là thay đổi phạm vi cần thống nhất lại; smoke command hiện có không chứng minh chúng đã được triển khai.

## Nguồn kiểm tra

- [Command và resolver](../myfap/cli.py).
- [Wrapper nghiệp vụ v1/v2 và survey](../myfap/api.py).
- [Allowlist, alias, method và query v2](../myfap/v2.py).
- [Auth/handshake](../myfap/auth.py), [discovery/OIDC](../myfap/oidc.py).
- Regression: [v1 API](../tests/test_api.py), [v2 API](../tests/test_api_v2.py), [transport Phase 4](../tests/test_phase4_transport.py), [CLI capability](../tests/test_cli_v2_capabilities.py).
