# Hợp đồng transport API v2

Tài liệu này ghi lại adapter v2 hiện có sau Phase 4 và phạm vi các route còn lại. V1 vẫn là mặc định. V2 chỉ được gọi khi lớp auth/API chọn rõ phiên bản; module transport không tự dò phiên bản, refresh session hoặc diễn giải JSON response.

## Transport và operation đã hỗ trợ

`myfap.v2.request()` trả về `requests.Response` nguyên bản. Lớp gọi phía trên chịu trách nhiệm chạy `read_response`, phân loại `401` và quyết định retry. Transport chỉ dựng request, kiểm tra tham số và che lỗi mạng khỏi thông tin credential.

| Operation | Version/account/capability | Method/path | Query | JSON body | Credential ký/Bearer | Header campus | Loại/retry | Nguồn APK |
|---|---|---|---|---|---|---|---|---|
| `GetAllActiveCampus` | v2/public/bootstrap | POST `/MyFAP/GetAllActiveCampus` | `{}` | `{}` | Credential bootstrap | `HN` | Đọc bootstrap; không refresh/retry | `module_599.js:580,843-861` |
| `GetApiActive` | v2/public/diagnostic | POST `/MyFAP/GetApiActive` | `{}` | `{}` | Credential bootstrap | `HN` | Đọc chẩn đoán; không refresh/retry | `module_599.js:1315,843-861` |
| `AuthenticationByFeId` | v2/student/login | POST `/MyFAP/AuthenticationByFeId` | `{}` | `{"token": <FEID access token>}` | FEID access token | Campus đang handshake | Handshake; auth điều phối phục hồi, transport không replay | `module_599.js:52-58,984-1008` |
| `GetSemester` | v2/student/semesters | GET `/MyFAP/GetSemester` | `{}` | Không có | FAP key của binding v2 | Campus của binding | Đọc; refresh/retry tối đa một lần khi expiry rõ | `module_599.js:153-158,898-919` |
| `GetActivityStudent` | v2/student/schedule | GET `/MyFAP/GetActivityStudent` | `CampusCode`, `rollNumber`, `Semester` | Không có | FAP key của binding v2 | Campus của binding, khớp query | Đọc; refresh/retry tối đa một lần khi expiry rõ | `module_599.js:294-300,898-919` |

Bảng trên nêu các contract nền tảng của bootstrap, handshake và lịch học. Ma trận bên dưới là nguồn trạng thái đầy đủ của operation trong adapter hiện tại; kết quả live theo từng nhóm command nằm trong [coverage Phase 4](phase4-coverage.md).

Mọi request v2 dùng `ClientCode: MyFAP`, `CampusCode`, `Authorization` và `Checksum: <base64-signature>:<unix-second>`. Các header client theo bản ghi app gồm `User-Agent: okhttp/4.9.2`, `Accept: application/json, text/plain, */*` và `Accept-Encoding: gzip`, áp dụng cho cả GET lẫn POST. GET không có body và không thêm `Content-Type`; POST gửi JSON có `Content-Type: application/json`.

Chữ ký là HMAC-SHA256 trên chuỗi `<credential>MyFAP<timestamp>`, dùng bytes UTF-8 của khóa giao thức. Padding `=` trong Base64 được đổi thành `%3d` đúng một lần ở giá trị header. Query không chứa bearer token hay checksum.

Bootstrap dùng campus theo hợp đồng của app, độc lập với campus đang lưu trong session. `GetSemester` giữ query rỗng; lịch học dùng đúng casing `CampusCode`, `rollNumber` và `Semester` của proxy.

Các path trên dùng base `https://fap-proxy.fpt.edu.vn/MyFAP/` nối với tên operation. Credential Bearer cũng là identity đưa vào checksum của từng request; bootstrap dùng định danh giao thức, handshake dùng FEID access token, các operation đọc dùng FAP key đã handshake cho v2. Ngoài hai bootstrap có header campus HN, header campus lấy từ binding đã chọn. Bootstrap không retry qua FEID; handshake do auth điều phối, không tự replay; operation đọc refresh/retry tối đa một lần khi có tín hiệu expiry rõ. Các luồng FEID và dữ liệu hiện tại giới hạn account student.

Nguồn trực tiếp trong `analysis/modules/module_599.js` của workspace: handshake `52-75`, GetSemester `153-164`, schedule `294-302`, header builder `741-780`, bootstrap POST `843-885`, GET/POST transport `904-1080`. V2 giữ payload envelope để lớp API phân loại lỗi, không dùng nhánh trả `[]` của app để che thất bại.

Các route trên cùng dùng base URL `https://fap-proxy.fpt.edu.vn/MyFAP/`. Header và signer được đối chiếu với `module_599.js:719-777`; các literal khóa và credential không được chép vào tài liệu. Token FEID/FAP thật không xuất hiện trong fixture.

## Ma trận route v2

`supported` nghĩa là operation nằm trong `SUPPORTED_OPERATIONS` của adapter v2 hiện tại; `unsupported` nghĩa là chưa có capability trong adapter. `stub` là hàm trong APK không có implementation nghiệp vụ đủ để dựng thành capability. Adapter không giả lập route bằng cách trả danh sách rỗng. Trạng thái triển khai không thay thế bằng chứng live hoặc positive case; xem [coverage Phase 4](phase4-coverage.md).

| Operation | Method | Trạng thái adapter | Ghi chú contract |
|---|---:|---|---|
| `AuthenticationByGoogleAccessToken` | `POST` | unsupported | Body token, chưa có luồng CLI tương ứng |
| `AuthenticationByFeId` | `POST` | supported | FEID token trong body và Bearer header |
| `AuthenticationByFeIdCode` | `POST` | unsupported | Nhánh code exchange của app đang tắt |
| `GetStudentById` | `GET` | supported | Query `CampusCode`, `rollNumber` |
| `RetriveImage` | `GET` | unsupported | Query `CampusCode`, `rollNumber` |
| `CheckUpdateProfile` | `GET` | supported | Vẫn giữ query `Authen` theo app |
| `GetSemester` | `GET` | supported | Query rỗng |
| `GetSubjets` | `GET` | supported | Query `CampusCode` |
| `GetSubjectBySemester` | `GET` | unsupported | Query `CampusCode`, `Semester` |
| `GetCourseOfSemester` | `GET` | unsupported | Query `CampusCode`, `semester`, `rollNumber` |
| `GetStudentMark` | `GET` | supported | Query `CampusCode`, `rollNumber`, `Semester` |
| `GetSemesterMark` | `GET` | unsupported | Query có `Authen` |
| `GetMarkByCourse` | `GET` | supported | Query `CampusCode`, `CourseId`, `rollNumber` |
| `AcademicTranscript` | `GET` | unsupported | Query `CampusCode`, `rollNumber` |
| `GetDiemphongtrao` | `GET` | unsupported | Query `CampusCode`, `rollNumber`, `semester` |
| `GetActivityStudent` | `GET` | supported | Query `CampusCode`, `rollNumber`, `Semester` |
| `GetActivityStudentByWeek` | `GET` | supported | Query thêm `week`, `year` |
| `GetScheduleExam` | `GET` | supported | Query `CampusCode`, `rollNumber`, `Semester` |
| `GetWeekByDate` | `GET` | supported | Query `date` |
| `GetStudentAttendances` | `GET` | supported | Query `CampusCode`, `Semester`, `rollNumber` |
| `GetCourseAttendance` | `GET` | supported | V2 đổi chữ hoa; query có `SubjectCode`, `ClassName` |
| `GeFeeByRoll` | `GET` | supported | Query `CampusCode`, `rollNumber` |
| `GetBalance` | `GET` | unsupported | Query `CampusCode`, `rollNumber` |
| `GetTop10News` | `GET` | supported | Query `CampusCode`, `type` |
| `SearchNews` | `GET` | unsupported | Query `CampusCode`, `type`, `keysearch` |
| `GetApplication` | `GET` | supported | Vẫn giữ query `Authen` theo app |
| `CheckOpenFeedBack` | `GET` | supported | Vẫn giữ query `Authen` theo app |
| `AddRate` | `POST` | unsupported | Vẫn giữ query `Authen` theo app |
| `UpdateTokedevices` | `GET` | unsupported | Query `CampusCode`, `Email`, `tokendevice` |
| `GetNotificationByRoll` | `GET` | supported | Vẫn giữ query `Authen` theo app |
| `UpdateTokenDonor` | `GET` | unsupported | Donor flow |
| `GetNotificationByDonor` | `GET` | unsupported | Vẫn giữ query `Authen` theo app |
| `GetTokenWithEmp` | `GET` | unsupported | Employee flow |
| `GetAllActiveCampus` | `POST` | supported | Body `{}` |
| `GetCampusInfo` | `GET` | supported | Query `CampusCode`, `rollNumber` |
| `GetStudentFeedbacks` | `GET` | unsupported | Query `CampusCode`, `rollNumber` |
| `GetStudentFeedbackForm` | `GET` | unsupported | Query `CampusCode`, `rollNumber`, `feedbackId` |
| `SubmitStudentFeedback` | `POST` | unsupported | Body nghiệp vụ |
| `GetVersion` | `GET` | unsupported | Query rỗng |
| `GetApiActive` | `POST` | supported | Bootstrap chẩn đoán trạng thái proxy |
| `GetStudentRate` | Không có | stub | APK export không có implementation request rõ ràng |
| `GetConnect` | Không có | stub | APK chỉ nối lại một đối tượng kết nối đã có |
| `GetLoginDonor` | Không có | stub | APK trả trạng thái tạm, chưa có contract login donor |

Ma trận hiện có 21 operation được hỗ trợ: 18 operation đọc, 2 bootstrap và 1 handshake. `GetApiActive` có API method chẩn đoán, chưa có command CLI riêng.

Bảy route giữ `Authen` trong query của adapter app là `CheckUpdateProfile` (`module_599.js:136`), `GetSemesterMark` (`223`), `GetApplication` (`429`), `CheckOpenFeedBack` (`443`), `AddRate` (`467`), `GetNotificationByRoll` (`491`) và `GetNotificationByDonor` (`532`). Trong số này, CLI đã triển khai bốn route `CheckUpdateProfile`, `GetApplication`, `CheckOpenFeedBack` và `GetNotificationByRoll`; ba route còn lại vẫn chưa được hỗ trợ. Route điểm danh chi tiết đổi từ `getCourseAttendance` của v1 sang `GetCourseAttendance` ở v2 (`module_599.js:363-364`); wrapper v1 không đủ để ghi nhận capability v2.

## Giới hạn hiện tại

- Chưa tích hợp auto-detect/fallback; `GetApiActive` chỉ là request chẩn đoán.
- Chưa xác nhận live schema của proxy cho các route unsupported.
- Chưa thêm v2 vào command mặc định hoặc đổi phiên bản session đã lưu khi handshake thất bại.
- Không dùng response rỗng để che route stub, HTTP 404 hoặc capability chưa biết.

Inventory được đối chiếu với các caller `MyFAP/*` trong `module_599.js`; các hàm stub nằm tại `21-31` và `458-460`. Service survey tiếp tục dùng host, checksum và contract riêng, không đi qua transport proxy này.
