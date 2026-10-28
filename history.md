# Lưu trữ lịch sử

Commit gốc của checkout khi lưu trữ: `467df1edb2220261dcd21392fbe3eaf008d6c662`. Mỗi mục ghi đường dẫn ban đầu và commit cuối cùng đã thay đổi file tại commit gốc. Nội dung lịch sử được giữ nguyên, trừ đích liên kết tương đối được điều chỉnh theo vị trí lưu trữ.

<a id="docs-phase1-live-verification"></a>

---

Đường dẫn ban đầu: `docs/phase1-live-verification.md`

Commit cuối thay đổi file tại commit gốc: `eb8f0e302436c076a3a8644a4e7aa18718481fbb`

# Kiểm chứng CLI với API thật, ngày 16/10/2026

Đây là báo cáo lịch sử tại commit `07fb289`. Kiểm chứng lại ngày 19/10/2026 trên v1/APHL đã xác nhận cùng các mã lỗi của ba route; policy hiện tại coi body 201 không có message `Token invalid` là lỗi operation, không phải hết phiên. Xem [kết quả mới](docs/phase4-coverage.md#chạy-lại-ba-lệnh-v1-ngày-19102026).

## Kết quả

Đã chạy executable CLI từ checkout commit `07fb289`, dùng session mẫu qua luồng nạp session thông thường. Đợt kiểm chứng chuẩn gồm 25 lần chạy command, phủ 20 route: 22 lần exit 0, 3 lần exit 1. Có thử điểm ở một kỳ có dữ liệu để kiểm tra điểm chi tiết; không ghi kỳ, mã môn hoặc nội dung điểm vào báo cáo.

Phase 1 đã có kiểm chứng live cho các luồng đọc chính, nhưng còn ba lỗi ở `news`, `other notification` và `other fee`. Kết quả unit test và CI thành công không thay thế việc giải quyết ba lỗi này.

| Command hoặc biến thể | HTTP / body code | Kết quả |
|---|---|---|
| `version`, `--help` | Không gọi HTTP | Exit 0 |
| `campuses`, `semesters` | 200 / 200 | Exit 0, bảng hiển thị được |
| `info student`, `info campus` | 200 / 200 | Exit 0, JSON hợp lệ |
| `schedule` tự chọn kỳ | 200 / 200 | Exit 0, JSON hợp lệ |
| `schedule --ics` | 200 / 200 | Exit 0, cấu trúc ICS hợp lệ |
| `marks` tự chọn kỳ và chỉ định kỳ | 200 / 200 | Exit 0, xử lý được cả danh sách rỗng và có dữ liệu |
| `marks --courseid <ID>` | 200 / 200 | Exit 0, giữ HTML trong JSON |
| `marks --courseid <ID> --pretty` | 200 / 200 | Exit 0, HTML được chuyển thành danh sách JSON |
| `exams` | 200 / 200 | Exit 0, danh sách rỗng vẫn hợp lệ |
| `week-timetable --date <DATE>` | 200 / 200 | Exit 0, tra tuần và lấy lịch được |
| `attendance`, điểm danh chi tiết | 200 / 200 | Exit 0, JSON hợp lệ |
| `applications` | 200 / 200 | Exit 0, JSON hợp lệ |
| `other survey` | 200 / 404 | Exit 0, giữ `Data Not Found` và `data: null` |
| `other feedback`, `other profile` | 200 / 200 | Exit 0, giữ kiểu boolean |
| `other subjects` | 200 / 200 | Exit 0, JSON hợp lệ |
| `news` | 200 / 201 | Exit 1, `data: null` |
| `other notification` | 200 / 201 | Exit 1, `data: null` |
| `other fee` với `GeFeeByRoll` | 404 / không có envelope FAP | Exit 1, không diễn giải thành không nợ |

Các command JSON đều được chạy với `--stdout`. Khi thành công, toàn bộ stdout parse được thành JSON; khi ba command thất bại, stdout rỗng. Progress và lỗi nằm trên stderr.

ICS có thể parse lại trong process kiểm tra riêng sau khi tăng recursion limit của Python. Parser thư viện `ics` ở giới hạn mặc định đã gặp `RecursionError` với output live; command xuất ICS vẫn exit 0. Chưa kiểm tra import vào Google Calendar hoặc ứng dụng lịch khác.

## Ba vấn đề chưa giải quyết

### Thông báo trả code 201

`GetTop10News` và `GetNotificationByRoll` đều trả HTTP 200, body code 201, `data: null` và `message: null` trong các lần thử. Kiểm tra session bằng `GetSemester` ngay trước đó vẫn trả 200/200; các route dữ liệu khác cũng chạy được.

CLI hiện phân loại code 201 thành `ApiSessionExpiredError`. Bằng chứng live chưa đủ để kết luận hai lỗi này là hết phiên: cần phân biệt lỗi theo operation với tín hiệu session hết hạn rõ ràng. Không refresh cưỡng bức hoặc thay credential để che lỗi. Chưa xác định nguyên nhân ở backend, tài khoản hay contract request.

### Học phí trả HTTP 404

Contract APK v1 dùng `GeFeeByRoll`, nhưng route này trả HTTP 404 trong lần thử thực tế. Một phép chẩn đoán chỉ đọc, chạy riêng ngoài mã runtime, dùng lại request để so sánh tên cũ `GetFeeByRoll`; route cũ cũng trả 404. Không triển khai fallback hoặc thay route theo suy đoán.

Chưa có response học phí v1 thành công để kiểm chứng `IsPaid`, invoice và amount trên backend hiện tại. Các kiểm tra bảo toàn trường vẫn dựa trên fixture tổng hợp. Không suy ra trạng thái thanh toán từ HTTP 404.

### Điều kiện chốt kiểm chứng live

- [ ] Xác định và xử lý nguyên nhân code 201 của hai route thông báo; bổ sung regression tổng hợp khi có contract rõ.
- [ ] Xác nhận endpoint học phí v1 đang hoạt động hoặc ghi nhận unsupported có căn cứ; cần một response thành công để kiểm chứng schema thực.
- [ ] Kiểm tra lại ba command sau khi có thay đổi phù hợp. Giữ kết quả thất bại hiện tại trong lịch sử kiểm chứng.

## Giới hạn và bảo vệ dữ liệu

Bạn có thể dùng báo cáo này để đánh giá route và output CLI, chưa thể coi đó là kiểm chứng đầy đủ mọi tài khoản hoặc campus. Survey mới được kiểm chứng trạng thái not-found, chưa có trường hợp thành công có survey bắt buộc. Login mới, OAuth callback, refresh rotation, đổi campus, API v2 và thao tác ghi nghiệp vụ chưa được kiểm thử trong lượt này.

Không đọc, liệt kê, sao chép hoặc kiểm tra trực tiếp thư mục session của người dùng. Chỉ executable CLI tự nạp session theo hành vi sẵn có. Command chạy tuần tự; không chạy `login`, `logout` hoặc `refresh` thủ công.

Stdout/stderr và response thật chỉ được xử lý trong RAM. Chương trình kiểm tra chỉ xuất metadata trong danh sách cho phép: route, mã HTTP/body, loại dữ liệu, exit code và kết quả kiểm tra định dạng. Không lưu response, header, query có giá trị, lịch học, bảng điểm, đơn từ, identity, credential hoặc biến môi trường bí mật vào repo, fixture, commit hay comment PR. Không phát lại HAR/SAZ.

Các script chạy live nằm ngoài repository và không được đưa lên GitHub. Báo cáo này và bản cập nhật checklist chỉ chứa kết quả đã che dữ liệu. `docs/` và `tasks/` vẫn là repository-only, không nằm trong artifact PyPI.

<a id="docs-phase2-review-fixes"></a>

---

Đường dẫn ban đầu: `docs/phase2-review-fixes.md`

Commit cuối thay đổi file tại commit gốc: `96b4a2ee0d23854964f9ad6dad36c685e20dc92c`

# Sửa lỗi sau review Phase 2

Review ban đầu dựa trên PR #5 ở commit `9573617`. Trong lúc sửa, branch được fast-forward theo merge `937ae7c` để giữ thay đổi README và hướng dẫn phát triển mới từ main. Không sửa branch tài liệu riêng hoặc đọc thư mục session cá nhân.

## Kết luận từng nhận định

| Nhận định | Kết luận và thay đổi |
|---|---|
| V1 không tự refresh với body 201 | Có gap. Mở rộng expiry cho mọi FAP read operation có `Authen` khi cả code 201 và message `Token invalid` khớp; không áp mọi 201 |
| `login --force` bị session v2 cũ chặn | Đúng. Login mới chỉ kế thừa campus, dùng v1/student trừ tham số rõ ràng; session cũ giữ nguyên đến khi login mới thành công |
| `login` bắt người dùng gõ thêm `--force` khi binding cần xác thực lại | Đúng. CLI chuyển từ `SessionBindingError` sang mở trình duyệt; lỗi mạng hoặc lỗi khác không bị che bằng login mới |
| ID token thiếu clock skew tolerance | Đúng. Thêm leeway 30 giây cho exp/iat/nbf, giữ chữ ký và các claim khác; buffer access token vẫn riêng |
| Logout không xóa được JSON hỏng | Đúng. Xóa file thường dưới lock mà không parse JSON, kiểm lại đường dẫn trước unlink |
| Attendance gọi mạng trước khi báo thiếu cờ | Đúng. Kiểm tra cặp cờ trước khi tạo auth, nạp session hoặc tra kỳ |
| Dependency pkce không còn được dùng | Đúng. Bỏ khỏi pyproject và uv.lock; PKCE S256 vẫn dùng secrets/hashlib |

## Bằng chứng cho contract 201

Nghiên cứu `analysis/auth-var-v1-v2-comparison.md`, mục 6.1, mô tả v1 dùng body 201 cho hết phiên nhưng chưa chỉ rõ điều kiện theo operation. Đối chiếu caller APK trong workspace xác nhận app kiểm đồng thời `code == 201` và `message == "Token invalid"`:

| Operation đang có trong CLI | Nguồn phân tích APK cục bộ |
|---|---|
| GetActivityStudent | `analysis/modules/module_1299.js:719-729` |
| GetStudentMark | `analysis/modules/module_1302.js:331-340` |
| GetStudentAttendances | `analysis/modules/module_1332.js:385-394` |
| GetActivityStudentByWeek | `analysis/modules/module_2598.js:746-756` |

Caller GetBalance cũng có điều kiện này tại `analysis/modules/module_825.js:409-417`, nhưng CLI chưa có operation đó nên không thêm capability hoặc policy chưa dùng. Những nguồn phân tích trên nằm ngoài repository CLI.

News/notification đã có bằng chứng live trả 201 khi cùng session vẫn đọc được dữ liệu. Policy mới chỉ refresh khi message chính xác `Token invalid`; body 201 rỗng của hai route này vẫn là lỗi operation. GetSemester và các FAP read route khác được mở rộng theo cùng guard. Public bootstrap, tra tuần, survey, operation lạ, thao tác ghi và handshake không thuộc allowlist FAP read. Body `201` thiếu hoặc sai message vẫn là lỗi operation. HTTP 401 tiếp tục là tín hiệu expiry rõ ràng cho request đọc.

Allowlist được mở rộng từ bốn lên 17 operation theo yêu cầu QoL của maintainer. `AUTHENTICATED_READ_OPERATIONS` là nguồn dùng chung cho phân loại lỗi và policy retry, tránh danh sách lệch nhau. Bốn caller APK ở bảng trên là bằng chứng trực tiếp; expiry live của 13 operation bổ sung chưa được quan sát trong lượt này.

## Kiểm chứng

Đã tái hiện lỗi bằng fixture trước sửa: login v2 bị chặn, logout không parse được JSON, ID token lệch đồng hồ 0,5 giây bị từ chối, attendance gọi auth trước kiểm tra cờ và body 201 `Token invalid` không kích hoạt refresh.

Regression sau sửa bao gồm login/refresh với JWT ký RSA thật trong bộ test; biên leeway; claim sai kiểu/không hữu hạn; giữ bytes session cũ khi login thất bại; logout corrupt/missing/symlink/reparse; retry một lần với key/checksum mới; second expiry; refresh thất bại; operation/message không khớp và App Check/403/5xx không refresh. CLI schedule vẫn giữ stdout chỉ chứa JSON sau refresh.

Windows/Python 3.9.25 và 3.11 đều chạy 214 test: 210 pass, 4 skip mỗi môi trường theo quyền/mode POSIX hoặc symlink. Console entry point được chạy trực tiếp với file tạm giả: logout JSON hỏng exit 0, session/lock đều được xóa; attendance thiếu `--classname` exit 1, stdout rỗng, báo đúng cờ và không tạo auth lock. Review độc lập theo hai trục Standards/Spec không còn finding sau sửa tài liệu.

Các test xác minh contract APK và xử lý CLI, không chứng minh server live tự hết phiên trả envelope nào trong một phiên cụ thể. Không sửa token thật hoặc tạo lỗi server để lấy bằng chứng. Kết quả test, artifact và CI của commit cuối được cập nhật qua comment PR; PR tiếp tục giữ draft.

<a id="docs-phase2-verification"></a>

---

Đường dẫn ban đầu: `docs/phase2-verification.md`

Commit cuối thay đổi file tại commit gốc: `a01a1f4235343f425331cf080efac9492da10a4d`

# Kiểm chứng Phase 2

Ngày kiểm tra: 16/10/2026. Branch: `feat/phase2-oauth-session`; [PR #5](https://github.com/WindowScary321/myfap-api-cli/pull/5) giữ draft.

## Offline và artifact

Windows/Python 3.9.25 và 3.11 cùng chạy 179 unittest: 176 pass, 3 skip. Các skip liên quan mode POSIX và quyền tạo symlink trên Windows; trường hợp reparse point có fixture riêng. Test lock dùng process riêng, test JWT dùng key/token sinh riêng trong bộ test. Không test nào cần tài khoản FEID hoặc session thật.

Regression bao phủ callback trùng/sai state/cancel/timeout, chữ ký và claim ID token, binding, session cũ, file hỏng, read retry, request ghi không retry, redirect, lưu token trước validation và lỗi handshake sau rotation. Test cũng chặn command đang chạy nhận nhầm session do process khác đổi tài khoản, campus hoặc version.

`uv build` tạo wheel/sdist version `0.2.0`; Twine strict và artifact validator đều pass. Hai artifact được cài bằng pip vào hai venv sạch ngoài checkout, sau đó chạy `pip check`, `myfap version` và `myfap --help`. Artifact không chứa `docs/`, `tasks/`, fixture, capture hoặc file session.

[CI của commit triển khai `8a369d3`](https://github.com/WindowScary321/myfap-api-cli/actions/runs/38895605533) đã pass toàn bộ 11 job: scope, bốn source job, build, bốn artifact job và ready. Matrix gồm Ubuntu/Windows × Python 3.9/3.11. Kết quả commit tài liệu cuối được cập nhật vào PR khi hoàn tất.

## Live với session tạm trước bổ sung QoL

Người dùng tự đăng nhập trên cửa sổ FEID. CLI dùng `--config` trỏ đến file tạm ngoài repository, không đọc trực tiếp thư mục session cá nhân. Output được giữ trong RAM và chỉ xuất các trường đã cho phép: tên operation, HTTP/body code, kiểu dữ liệu, kết quả validation và exit code. Không lưu URL chứa query, token, MSSV/email, raw response, lịch học hoặc điểm.

| Luồng/command | Kết quả |
|---|---|
| `login --force` | Discovery, token endpoint và JWKS HTTP 200; ID token qua validation; handshake HTTP 200/body 200, data list; exit 0 |
| `semesters` | Probe và request GetSemester HTTP 200/body 200; exit 0 |
| `news --stdout`, timeout 20 giây | Lỗi mạng/timeout; exit 1; không gọi token endpoint |
| `news --stdout`, timeout 60 giây | HTTP 200/body 201, data null; exit 1; không refresh |
| `other notification --stdout` | HTTP 200/body 201, data null; exit 1; không refresh |
| `refresh` | Token endpoint/JWKS HTTP 200; ID token refresh được trả và qua validation; handshake HTTP 200/body 200; exit 0 |
| `info student --stdout` sau refresh | Probe và GetStudentById HTTP 200/body 200, data list; stdout parse được JSON; exit 0 |
| `--campus HCM login` với tài khoản chỉ có APHL | Handshake thật HTTP 200/body 201; exit 1; không gọi request nghiệp vụ; nội dung session được so sánh trong RAM và không đổi |
| `--campus APHL login` sau lần HCM thất bại | Probe GetSemester HTTP 200/body 200; exit 0 |
| Fault injection timeout tại handshake sau refresh thật | Refresh token mới được server trả và persist trước lỗi; binding giữ nguyên, FAP đánh dấu cần xác thực lại, exit 1 |
| `semesters` sau khi bỏ fault handshake | Handshake lại HTTP 200/body 200 rồi GetSemester HTTP 200/body 200; exit 0; không exchange token lần hai |
| Console entry point `myfap.exe` | Chạy trực tiếp `semesters` và `info student --stdout`, exit 0; JSON hợp lệ |
| Console entry point `logout` | Xóa session tạm, exit 0 |

Các luồng cần trace operation chạy qua Typer app với tham số CLI thật và Requests thật; console entry point được chạy thêm bằng subprocess để xác minh đường gọi của bản cài editable. Login, đổi campus, token exchange và request phục hồi đều gọi server thật; riêng phép thử lỗi handshake chặn request trong bộ nhớ trước khi gửi, không thay token hay file session bằng dữ liệu giả. Lần mở trình duyệt đầu chưa có callback; lần đăng nhập sau đã hoàn tất. Hai lỗi body 201 vẫn thuộc backend/contract và được giữ là lỗi operation.

## Phần chưa xác nhận live

Đổi campus thất bại với HCM đã được kiểm chứng live và giữ nguyên APHL. Chưa xác nhận chuyển campus thành công vì tài khoản mẫu chỉ có APHL. Phục hồi sau handshake lỗi đã được kiểm bằng fault injection trên session thật; chưa quan sát server tự trả lỗi handshake. FEID trả `expires_in: 3600` khi refresh, nhưng FAP `authenKey` không có contract TTL; hết hạn FEID access token không đồng nghĩa FAP credential hết hạn. Vì vậy HTTP 401 tự refresh/retry mới chỉ có fixture, chưa có bằng chứng phiên thật tự hết hạn. Đổi API version hoàn tất khi có adapter v2 ở Phase 3.

Session cũ chưa có subject OIDC đã xác minh cần `login --force` trước khi refresh. File session vẫn là JSON chứa credential; xem [quy tắc lưu session](docs/oauth-session.md#timeout-và-file-trên-máy). PR này không tạo tag, publish PyPI hoặc triển khai auto release.

## Kiểm chứng QoL trong PR #5

Sau khi bỏ probe `GetSemester`, thêm buffer 30 giây trước khi dùng FEID access token để handshake và dọn lock khi logout, Windows/Python 3.9 và 3.11 cùng chạy 191 test: 188 pass, 3 skip mỗi môi trường. Test số request dùng auth/client thật với HTTP giả; test biên thời hạn cố định đồng hồ; test cleanup dùng process riêng để giữ handle chờ và phát hiện hai khóa song song. POSIX được kiểm trong CI Ubuntu.

Đã đăng nhập mới bằng session tạm riêng và chạy Requests thật:

| Command | Trace sau QoL |
|---|---|
| `info student --stdout` | Chỉ GetStudentById HTTP 200/body 200; JSON hợp lệ, exit 0 |
| `semesters` | Chỉ một GetSemester HTTP 200/body 200; exit 0 |
| `login` với session đã lưu | Không phát sinh HTTP; exit 0 |
| `logout` | Exit 0; cả session tạm và `.lock` đều không còn |

Buffer 30 giây được kiểm bằng đồng hồ cố định, không sửa token thật để giả thời hạn. Buffer chỉ refresh sớm trước handshake/phục hồi binding; không kéo dài token hoặc suy thời hạn FAP từ FEID. Trên Windows, logout có thể giữ lock nếu process khác còn mở handle; hành vi này tránh phá đồng bộ giữa các process. Kết quả CI commit QoL được cập nhật qua comment PR.

<a id="docs-phase3-verification"></a>

---

Đường dẫn ban đầu: `docs/phase3-verification.md`

Commit cuối thay đổi file tại commit gốc: `35b5ea1d47c1c52ed814b78ab0cdc39fd59a576c`

# Kiểm chứng Phase 3

Baseline là `238c718` trên main, sau PR #5. Phase 3 được triển khai tại [PR #7](https://github.com/WindowScary321/myfap-api-cli/pull/7), giữ draft và version package `0.2.0`.

## Offline

Regression dùng credential giả, file session tạm và HTTP mock; không đọc thư mục session cá nhân. Bộ test giữ toàn bộ v1 và bổ sung:

- Header/body/query v2 cho hai bootstrap, handshake, GetSemester và schedule; signing identity đúng theo từng bước.
- HMAC-SHA256 dùng UTF-8 key, timestamp cố định và padding `%3d`; ngăn decode khóa hex hoặc encode padding hai lần.
- Precedence option → session → v1; state CLI không bị lẫn giữa các lần gọi. Public bootstrap đọc version mà không restore identity hoặc handshake.
- Đổi binding v1/v2 hai chiều; handshake lỗi giữ binding cũ; không gửi FAP key của version cũ vào request dữ liệu version mới. Cùng campus/account không được âm thầm đổi MSSV/email.
- Rotation persist trước validation/handshake, retry đọc tối đa một lần với key/chữ ký mới, App Check/403/5xx và route unsupported không gây fallback.
- Capability CLI được kiểm trước tra kỳ/tuần cho command chưa hỗ trợ; survey giữ contract riêng.

Windows/Python 3.9.25 và 3.11 chạy 261 test mỗi môi trường: 257 pass, 4 skip theo quyền/mode POSIX hoặc symlink. Build version `0.2.0` qua Twine strict và artifact validator; wheel/sdist được cài bằng pip vào hai venv sạch, `pip check`, version và help đều pass. Review độc lập không còn finding runtime; phần contract matrix đã bổ sung account/path/read-write/retry sau review.

## Live với session tạm

Ngày 17/10/2026, người dùng tự đăng nhập FEID và xác nhận tài khoản mẫu thuộc Hà Nội/Hòa Lạc. Output chỉ được giữ trong RAM và xuất metadata: operation, method, HTTP/body code, kiểu data, kết quả ID token validation, exit code hoặc tính hợp lệ JSON. Không ghi token, MSSV/email, query có credential, lịch học, điểm hay raw response vào repository.

| Phép thử | Kết quả |
|---|---|
| V2 GetAllActiveCampus | POST HTTP 200/body 200, data list |
| V2 GetApiActive gọi rõ để chẩn đoán | POST HTTP 200/body 200, data bool |
| Login v2 với campus APHL | FEID discovery/token/JWKS HTTP 200, ID token hợp lệ; handshake HTTP 200/body 401, exit 1; không lưu session v2 |
| Lấy mã campus từ bootstrap v2 | Có CT, DN, HCM, HN, QN; HN là Cơ sở Hà Nội, không có APHL |
| Login v2 với HN sau xác nhận của người dùng | FEID discovery/token/JWKS HTTP 200, ID token hợp lệ; handshake POST HTTP 200/body 200, data list, exit 0 |
| `--api-version v2 semesters` | Một GetSemester GET HTTP 200/body 200, data list, exit 0 |
| `--api-version v2 schedule --stdout` | GetSemester và GetActivityStudent GET HTTP 200/body 200, stdout JSON hợp lệ, exit 0 |
| `schedule --stdout` cùng session, bỏ option version | Chọn v2 đã lưu; hai operation trên HTTP 200/body 200, JSON hợp lệ, exit 0 |
| `--api-version v2 marks --stdout` | Exit 1, không phát sinh HTTP vì chưa hỗ trợ |
| Logout session tạm | Exit 0; session và sidecar lock đều được xóa |

Lần handshake APHL thất bại và lần HN thành công được giữ thành hai kết quả riêng. CLI không tự đổi campus, không đổi version hoặc thêm token App Check để vượt lỗi. Không kết luận mọi body 401 đều do campus; ở lần này mã campus đã được kiểm tra lại bằng bootstrap và người dùng xác nhận.

## Giới hạn

Live mới xác nhận bootstrap, login mới, kỳ học, schedule JSON và lựa chọn version từ session với một campus. Đổi version hai chiều, refresh v2 và các nhánh lỗi có fixture, chưa xác nhận live riêng trong lượt này. Chưa có bằng chứng một session v2 tự hết hạn. Khả năng import lịch ICS và parity các command còn lại thuộc Phase 4.

Kết quả Python 3.9/3.11, build, Twine, artifact validator, pip smoke và CI của commit cuối được cập nhật qua comment PR. Không có tag, GitHub Release hoặc publish PyPI trong Phase 3.

<a id="tasks-phase0"></a>

---

Đường dẫn ban đầu: `tasks/phase0.md`

Commit cuối thay đổi file tại commit gốc: `5efad9b8c2e8cdfb992db7ddc64b7ef085b5db6a`

# Phase 0 — CI và artifact cho mốc v0.2.0

PR theo dõi: [PR 2](https://github.com/WindowScary321/myfap-api-cli/pull/2). Mọi commit của phase này được push vào `feat/phase0-v0.2.0`; các comment ghi mốc kiểm tra, commit và kết quả CI.

## Phạm vi

Gia cố CI trước các phase sửa v1, OAuth/session và v2. Version package được chuẩn bị thành `0.2.0` trong PR này; chưa tạo tag, publish PyPI hoặc triển khai auto release của Phase 5. Kế hoạch migration uv `0.1.8` trong `tasks/plan.md` và `tasks/todo.md` là lịch sử đã hoàn tất, giữ nguyên.

## Công việc

- [x] Tách branch từ `origin/main`, tạo PR và đồng bộ version với lockfile.
- [x] Thêm nhóm dependency CI đã khóa; chuyển marker greenlet vào metadata runtime sau khi tái hiện lỗi pip Windows/Python 3.9 cần compiler.
- [x] Thêm artifact gate cho version, entry point, README/license, file allowlist và manifest SHA-256.
- [x] Kiểm tra cả wheel/sdist trong venv riêng ngoài checkout bằng pip; chạy check/version/help và ép UTF-8 cho subprocess.
- [x] Chuyển CI thành source matrix → build Ubuntu một lần → artifact matrix → gate cuối; hỗ trợ reusable workflow outputs.
- [x] Pin action theo commit SHA, giữ quyền `contents: read` và tắt persist Git credential.
- [x] Thêm unit test với archive giả, version/hash sai, đường dẫn nhạy cảm, symlink, smoke isolation và UTF-8.
- [x] Xác nhận source và artifact trên cả bốn môi trường GitHub Actions; tiếp tục kiểm tra lại khi PR có commit mới.
- [x] Ghi các mốc commit/kiểm tra bằng comment và tổng hợp bằng chứng trong PR.

## Kiểm chứng

- Unit suite local: 32 test pass sau phần mở rộng, gồm regression version và các case scope/ready. Thử đảo điều kiện kiểm manifest khiến test hash thất bại; khôi phục code và suite pass lại.
- `uv build`, `twine check --strict`, artifact validation và actionlint pass.
- Pip smoke thật trên Windows/Python 3.9 và 3.11 pass cho wheel lẫn sdist; bốn tổ hợp OS/Python trên GitHub Actions đều pass.
- [Run CI 38852306858](https://github.com/WindowScary321/myfap-api-cli/actions/runs/38852306858) của commit `393ced9`: 10/10 job thành công. Kết quả commit mới nhất được cập nhật trong PR.

## Giới hạn

CI không đăng nhập FEID hoặc gọi API FAP thật. Allowlist chỉ chặn đường dẫn/file ngoài chính sách; không chứng minh được không có secret hoặc PII ẩn trong nội dung mã Python. Kết quả Phase 0 không xác nhận OAuth/API v1/v2 đã được sửa.

## Mở rộng: docs/tasks chỉ lưu trong repository

- [x] Thêm `scope` lấy danh sách tên path Git, không đọc nội dung hai thư mục. Rename được xét như delete/add để đổi tên từ code sang docs hoặc ngược lại vẫn chạy đầy đủ CI.
- [x] Chỉ thay đổi `docs/**` hoặc `tasks/**`: bỏ qua source/build/smoke, không tạo artifact; `ready` vẫn trả success. Thay đổi code/mixed và mọi `workflow_call` chạy đủ gate.
- [x] `ready` dùng `always()` nhưng xác minh trạng thái từng job, không che lỗi/cancel hoặc trạng thái không xác định.
- [x] Sparse checkout chỉ giữ code/tests/helpers và file build; không checkout docs/tasks trong các job CI. README/license root vẫn được giữ.
- [x] Dùng `MANIFEST.in` loại hai thư mục khi build full checkout; validator từ chối docs/tasks trong wheel và sdist.
- [x] Bổ sung test docs-only/tasks-only, code/mixed, rename/delete, reusable call và gate lỗi; artifact giả kiểm tra cả hai định dạng.
- Kết quả pipeline của commit mở rộng trên GitHub Actions được theo dõi trong check của PR; comment ghi link run và commit tương ứng.

Phần mở rộng giữ nguyên runtime API, entry point, version và các workflow outputs artifact đã có. Không thêm tài liệu vào `package-data` hoặc `data-files`.

<a id="tasks-phase1"></a>

---

Đường dẫn ban đầu: `tasks/phase1.md`

Commit cuối thay đổi file tại commit gốc: `e2325f5542ea92c4acf7adde547ef4daafb98f1a`

# Phase 1: sửa v1 và lỗi dữ liệu

## Phạm vi

Tiếp nối Phase 0 trên phiên bản `0.2.0`, branch `fix/phase1-v1-data`. API v1 vẫn là mặc định. Công việc gồm query, payload, chọn kỳ học, survey, học phí, stdout và parser. OAuth/session đầy đủ, adapter v2 và auto release thuộc các phase sau.

**Trạng thái sau kiểm chứng API thật ngày 16/10/2026:** phần triển khai và kiểm thử offline đã xong; live còn ba command chưa hoạt động. Chi tiết nằm trong [báo cáo kiểm chứng live](#docs-phase1-live-verification).

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

<a id="tasks-phase2"></a>

---

Đường dẫn ban đầu: `tasks/phase2.md`

Commit cuối thay đổi file tại commit gốc: `96b4a2ee0d23854964f9ad6dad36c685e20dc92c`

# Phase 2: OAuth và session

## Phạm vi và thứ tự

Branch `feat/phase2-oauth-session` bắt đầu từ `main` sau PR #3. Giữ version `0.2.0`, API v1 và Playwright. PR riêng phải ở trạng thái draft; chỉ maintainer quyết định chuyển Ready for review hoặc merge.

1. Phân loại lỗi theo version/operation/HTTP/body. Code 201 chưa rõ nghĩa không gây refresh/logout; đọc chỉ retry một lần khi có tín hiệu hết phiên rõ ràng.
2. Kiểm tra callback chính xác, state/nonce và PKCE mới mỗi login. Dùng discovery và xác minh ID token RS256 bằng JWKS, issuer/audience/azp/exp/sub/nonce/at_hash.
3. Lưu session atomic và dùng lock xuyên suốt read → refresh → persist. Lưu refresh token mới trước validation/handshake tiếp theo; lỗi sau rotation không được quay về token cũ.
4. Chọn campus theo parameter → session → default khi login mới. Binding campus/version/account type phải hợp lệ trước request dữ liệu; identity lấy từ handshake, không decode access token để suy MSSV.
5. Giữ timeout đã có cho discovery/JWKS/token/handshake/API. Kiểm tra offline, build và smoke artifact trước gate live riêng.

## Hợp đồng giữa các phần

- `errors.py`: lỗi an toàn, không chứa credential, response hoặc URL có query; phân loại theo context của operation.
- `oidc.py`: discovery, login attempt, callback, token request và validation tách biệt để persist rotation trước bước có thể lỗi.
- `storage.py`: đọc JSON, ghi atomic và khóa file; chỉ auth orchestration điều phối transaction.
- `auth.py`: vòng đời OAuth/FAP session, binding, identity handshake và rotation; CLI không tự mở file session để refresh.
- `api.py`: kiểm binding và retry đọc có giới hạn; payload/output hiện có được giữ nguyên.

Các module mới phục vụ trust boundary và tránh circular import; không thêm framework hoặc adapter v2 trong Phase 2.

## Checklist

- [x] Regression cho hai body 201 và ma trận HTTP/body 401, App Check, timeout/5xx, read/write retry.
- [x] Callback/OIDC có test âm về chữ ký, issuer, audience/azp, nonce, expiry và at_hash; refresh có thể thiếu ID token nhưng nếu có phải cùng subject.
- [x] Session cũ thiếu version được hiểu là v1; đổi binding bị chặn trước HTTP dữ liệu, handshake lỗi không ghi nhầm binding.
- [x] Atomic write và lock được kiểm bằng file tạm/process riêng trên Windows và Unix; không đọc session thật trong test offline.
- [x] Test rotation chứng minh token mới được persist trước handshake và được giữ lại khi validation/handshake lỗi.
- [x] Matrix Ubuntu/Windows × Python 3.9/3.11, wheel/sdist, Twine và smoke cài bằng pip pass tại commit triển khai `8a369d3`.
- [x] Live gate ghi rõ phần đã kiểm chứng và phần còn thiếu trong [báo cáo](#docs-phase2-verification); đã kiểm campus ngoài tài khoản, phục hồi sau handshake fault injection và chỉ lưu metadata đã che dữ liệu.
- [x] Review độc lập, kiểm tra tiếng Việt và scan credential/PII trước commit/push; comment từng mốc vào draft PR.

Đã chạy 179 test trên Windows với Python 3.9.25 và 3.11: mỗi môi trường có 176 pass, 3 skip theo điều kiện hệ điều hành/quyền symlink. Build local qua Twine strict, artifact validator và smoke cài wheel/sdist bằng pip. [CI của commit triển khai](https://github.com/WindowScary321/myfap-api-cli/actions/runs/38895605533) đã pass toàn bộ 11 job, gồm đủ matrix; kết quả commit tài liệu cuối được cập nhật qua comment PR.

Live đã xác nhận login mới, ID token validation, handshake, refresh, đọc JSON sau refresh và logout session tạm. News/notification vẫn trả body 201 và không gây refresh. Kiểm tra HCM bằng tài khoản chỉ có APHL trả body 201 và giữ nguyên session; trở lại APHL thành công. Refresh thật kèm timeout handshake được tạo cục bộ giữ token đã rotate; bỏ fault thì handshake và đọc kỳ thành công mà không exchange token lần hai. Chuyển campus thành công, FAP session tự hết hạn và đổi version chưa được xác nhận live; đổi version chờ Phase 3. PR vẫn giữ draft.

## Giới hạn

Không đọc, liệt kê, sao chép hoặc kiểm tra trực tiếp thư mục session cá nhân. Live chỉ chạy CLI theo luồng thông thường; không lưu token, identity, lịch học, bảng điểm hoặc raw response vào Git. Không phát lại HAR/SAZ.

Phase 4 tiếp tục điều tra lỗi backend/contract của news, notification và fee; sửa phân loại 201 không làm các endpoint đó trở thành thành công. Binding chuyển v2 và live đổi API version hoàn tất khi có adapter Phase 3. Auto release vẫn thuộc Phase 5.

## QoL bổ sung trong PR #5

- [x] Bỏ `GetSemester` probe khỏi nạp session; chỉ tra kỳ khi command cần tự chọn kỳ hoặc chạy `semesters`. Các request dữ liệu giữ refresh/retry một lần trên HTTP 401.
- [x] Buffer 30 giây để refresh access token sớm trước handshake/phục hồi binding; không kéo dài thời hạn token hoặc thay xác minh ID token.
- [x] Logout dọn session và lock idle. POSIX kiểm lại inode sau acquire để process chờ không dùng khóa đã unlink; Windows giữ lock nếu process khác còn mở handle.
- [x] Regression command-level về số request, biên buffer và cleanup có process chờ; 191 test chạy trên Windows/Python 3.9/3.11, mỗi môi trường 188 pass và 3 skip.
- [x] Live QoL: `info student` không có `GetSemester`, `semesters` chỉ một request, `login` dùng session local và logout xóa session/lock tạm. CI commit mới được cập nhật qua comment PR; xem [báo cáo kiểm chứng](#docs-phase2-verification).

## Sửa lỗi sau review PR #5

- [x] Mở rộng expiry v1 cho 17 FAP read operation có `Authen`: body `201` cùng exact message `Token invalid` kích hoạt retry tối đa một lần. Public/survey, handshake, operation ghi và body 201 thiếu/sai message không refresh; news/notification rỗng vẫn là lỗi operation.
- [x] Login mới không bị binding v2/donor đã lưu chặn; chỉ kế thừa campus. Lệnh đọc và tham số yêu cầu v2/donor rõ ràng vẫn bị chặn trong Phase 2.
- [x] `myfap login` tự mở trình duyệt khi session cần xác thực lại hoặc binding không được hỗ trợ, thay vì yêu cầu gõ lại `--force`.
- [x] Thêm leeway 30 giây khi xác minh `exp/iat/nbf` của ID token, tách biệt buffer refresh sớm access token. Giữ strict type/finite và mọi kiểm tra chữ ký/identity.
- [x] Logout dọn JSON hỏng mà không parse nội dung, giữ lock và guard đường dẫn.
- [x] Attendance kiểm tra cặp `--subjectcode/--classname` trước khi nạp session hoặc gọi HTTP.
- [x] Gỡ dependency `pkce` không còn caller và đồng bộ lockfile.

Các lỗi có regression RED trước sửa và GREEN sau sửa. Tổng hợp kết luận, nguồn APK và kết quả kiểm chứng tại [báo cáo review](#docs-phase2-review-fixes); CI của commit cuối được cập nhật trong comment PR.

<a id="tasks-phase3"></a>

---

Đường dẫn ban đầu: `tasks/phase3.md`

Commit cuối thay đổi file tại commit gốc: `35b5ea1d47c1c52ed814b78ab0cdc39fd59a576c`

# Phase 3: adapter API v2 tối thiểu

Branch `feat/phase3-v2-adapter` bắt đầu từ `origin/main` tại `238c718`, sau khi PR #5 được merge. Version package giữ `0.2.0`. API v1 tiếp tục là mặc định; API v2 chỉ chạy khi được chọn bằng tham số hoặc đã được lưu trong session.

## Phạm vi

- Thêm option global `--api-version v1|v2` và tham số `api_version` cho các wrapper. Thứ tự chọn: tham số, session, mặc định v1. Không tự đổi version sau lỗi mạng hoặc backend.
- Giữ wrapper và định dạng output hiện tại. V2 hỗ trợ luồng campuses → login → semesters → schedule; GetApiActive phục vụ chẩn đoán. Operation chưa có adapter báo chưa hỗ trợ trước HTTP; parity đầy đủ thuộc Phase 4.
- Bootstrap dùng POST với JSON rỗng; handshake dùng FEID access token, request dữ liệu dùng FAP authenKey. Campus bootstrap theo từng operation, không lấy campus cố định cho toàn bộ request.
- Chữ ký v2 dùng HMAC-SHA256 với khóa UTF-8, timestamp giây và padding `%3d` theo APK. Giữ nguyên query/signature v1 và survey.
- Mọi request dùng timeout đã chọn và không follow redirect. Đọc chỉ retry một lần khi có tín hiệu hết phiên rõ; App Check là lỗi riêng. Không thêm thao tác ghi hoặc cơ chế né App Check.
- Đổi campus/version phải handshake trước khi lưu binding mới. Giữ token đã rotate nếu bước sau lỗi; không gửi FAP credential của session v1 vào request dữ liệu v2.

## Kiểm chứng

- [x] Contract matrix ghi method/path/query/body/header, nguồn Bearer và signing identity, account type, read/write và retry. Ghi đủ các route v2 giữ query Authen, kể cả route chưa triển khai.
- [x] Test chữ ký bằng dữ liệu giả, timestamp cố định; ngăn decode khóa hex và double-encoding padding.
- [x] Test bootstrap, handshake, kỳ học query rỗng, schedule và lỗi unsupported; giữ regression v1.
- [x] Test lựa chọn version, session legacy, chuyển v1/v2 hai chiều và rollback binding khi handshake lỗi.
- [x] Test CLI, stdout, timeout, HTTP/body 401, App Check và retry dùng key/chữ ký mới.
- [x] Local Windows/Python 3.9/3.11, build, Twine strict, artifact validator và pip smoke.
- [x] Live bằng session tạm riêng: campuses → login → semesters → schedule. Chỉ ghi metadata đã che; phần chưa kiểm chứng phải được ghi rõ.
- [x] Review độc lập và rà tiếng Việt cho tài liệu, commit, comment PR. PR giữ draft.

Local chạy 261 test trên mỗi phiên bản Python: 257 pass, 4 skip theo điều kiện Windows. Matrix CI Ubuntu/Windows × Python 3.9/3.11 của commit cuối được xác nhận trong [checks PR #7](https://github.com/WindowScary321/myfap-api-cli/pull/7/checks) và comment sau khi hoàn tất.

Live v2 thành công với campus HN sau khi người dùng xác nhận mã campus; lần APHL trả body 401 được ghi riêng. Đổi version và refresh v2 có fixture, chưa xác nhận live riêng. Xem [hướng dẫn version](docs/api-versions.md), [contract](docs/v2-contracts.md) và [báo cáo](#docs-phase3-verification).

Không đọc trực tiếp thư mục session cá nhân, không đưa token, query có credential, raw response, lịch học hoặc điểm thật vào Git. Nguồn contract là tài liệu và module APK trong workspace; capture không được phát lại. Không tạo tag, publish hoặc chuyển mặc định sang v2 trong phase này.

<a id="tasks-phase4"></a>

---

Đường dẫn ban đầu: `tasks/phase4.md`

Commit cuối thay đổi file tại commit gốc: `b013703a899a008fa0a4db7bd31008eaa142a46e`

# Phase 4: phủ các command đọc hiện có

Nhánh `feat/phase4-command-parity` bắt đầu từ main tại `74dd8e5`, sau khi PR #7 được merge. Giữ version package `0.2.0`, Python >=3.9 và entry point hiện có. V1 tiếp tục là mặc định; v2 được chọn bằng option hoặc session.

## Phạm vi triển khai

- Phủ v2 cho lịch học, lịch tuần, điểm tổng hợp/chi tiết, lịch thi, điểm danh tổng hợp/chi tiết, đơn từ, news, thông tin sinh viên/campus, fee, subjects và các lệnh kiểm tra feedback/profile/notification hiện có.
- Giữ host và checksum riêng của survey. Không biến trạng thái not-found thành danh sách rỗng hoặc kết luận không có khảo sát bắt buộc.
- Giữ JSON/ICS, tên trường, lựa chọn kỳ học theo ngày và stdout sạch. Mọi request dùng timeout đã chọn, không follow redirect hoặc fallback version.
- Giữ query theo từng operation, bao gồm CampusCode, Semester/semester, CourseId và bốn route hiện có vẫn mang Authen. Điểm danh chi tiết dùng GetCourseAttendance trên v2 và getCourseAttendance trên v1.
- Credential/signature/legacy Authen phải được dựng lại khi retry sau refresh. Chỉ retry đọc một lần khi có tín hiệu expiry rõ; App Check, timeout, 403 và 5xx không kích refresh.
- Bảng coverage phân biệt bằng chứng APK, capture, fixture, live thành công/thất bại và phần chưa kiểm chứng. HTTP 404 không tự chứng minh route đã ngừng hỗ trợ.

Không thêm transcript, balance, ảnh, news search, GetVersion, form feedback hoặc thao tác ghi vào CLI trong phase này. Những route đó thuộc Phase 6. Không phát hành, tạo tag hay đổi mặc định sang v2.

## Kiểm chứng

- [x] Contract test ở biên HTTP và wrapper cho các route đọc v1/v2; dữ liệu fixture hoàn toàn tổng hợp.
- [x] CLI test cho nhóm command hiện có, stdout JSON/ICS, capability, option và lỗi trước HTTP.
- [x] Regression cho retry dùng key/checksum/Authen mới và giới hạn một lần.
- [x] Kiểm tra ICS bằng dữ liệu tổng hợp và một reader độc lập; ghi rõ giới hạn của reader hiện tại nếu còn.
- [x] Live trên session tạm riêng, không đọc thư mục session cá nhân. Chỉ giữ metadata đã lọc, không giữ lịch/điểm/hồ sơ hoặc credential thật trong Git.
- [x] Chạy lại news, notification và fee của v1; ghi nguyên trạng lỗi còn lại và giới hạn theo version/campus. Không dùng CI xanh thay kết luận live.
- [x] Review độc lập, kiểm tra tiếng Việt, test Python 3.9/3.11, build, Twine, artifact validator và pip smoke.
- [x] Draft PR riêng, comment tiếng Việt sau các mốc quan trọng; maintainer quyết định Ready for review và merge.

Đã có bằng chứng cho 8 mục trong phạm vi kiểm chứng hiện tại. Theo quyết định của người dùng ngày 19/10/2026, positive fee/survey được chuyển sang [TODO chờ dữ liệu phù hợp](tasks/todo.md#kiểm-chứng-hoãn-chờ-dữ-liệu-phù-hợp), không chặn chuyển sang Phase 5. Contract và CLI được kiểm tra tại `tests/test_phase4_transport.py`, `tests/test_api_v2.py`, `tests/test_cli_v2_capabilities.py` và các regression v1. Test ICS dùng reader `icalendar` độc lập. Kết quả live v2 HN đã ghi 21 operation khác nhau, 23 request và dọn session/lock tạm; xem [coverage Phase 4](docs/phase4-coverage.md). Matrix Ubuntu/Windows × Python 3.9/3.11, build và cài artifact được ghi tại [checks PR #8](https://github.com/WindowScary321/myfap-api-cli/pull/8/checks).

Đã chạy lại ba lệnh v1/APHL ngày 19/10/2026 với login mới: news/notification vẫn trả HTTP 200/body 201, fee vẫn trả HTTP 404; lệnh đối chứng đọc thông tin sinh viên đạt 200/200 trước và sau. Session và lock tạm đã dọn. Mục chạy lại live được đánh dấu vì đã có kết quả và giới hạn, không có nghĩa ba lỗi response đã được sửa. Xem [kết quả v1](docs/phase4-coverage.md#chạy-lại-ba-lệnh-v1-ngày-19102026).

Positive fee/survey được hoãn, schema live vẫn chưa kiểm chứng: fee v2 trả HTTP/body 200 chưa đủ để kết luận positive case, còn survey trả body 404. Các lỗi response v1 vẫn mở trong TODO; chưa có cơ sở suy ra body 201 là rỗng hợp lệ hoặc HTTP 404 là route ngừng hỗ trợ toàn bộ. Các ô đã đánh dấu không có nghĩa mọi route đều đã hoạt động hoặc toàn bộ schema live đã được xác nhận.

Parser điểm đã được sửa cho cấu trúc ba cột `Item`, `Weight`, `Value` khi không có cột ghi chú, gồm cả dòng đầu tiên và dòng tiếp theo trong `rowspan`. Hàng ba `<td>` theo fallback category/item/value cũ vẫn được giữ để tránh thay đổi output tương thích.

Xuất ICS cũng đã xử lý khoảng trắng quanh dấu `-` và dấu ngoặc trong `slotTime`; regression xác nhận giờ bắt đầu/kết thúc không thay đổi. Hai lỗi parser được tái hiện và kiểm thử bằng dữ liệu tổng hợp, chưa dùng dữ liệu tài khoản thật trong lượt sửa này.

Các bản sửa bổ sung xử lý bảng Rich trên stdout `cp1252`, cho `login` tự phục hồi session sai cấu trúc và thêm nhóm dependency `ci` vào hai bước sync/test của workflow publish. Việc này sửa lỗi thiếu `icalendar` trên runner sạch; pipeline tag → reusable CI → publish → smoke → GitHub Release của Phase 5 vẫn chưa được triển khai. Không chạy publish hoặc thay đổi trigger release trong lượt sửa này.

Sau bàn giao 19/10/2026, đã sửa thêm refresh `invalid_grant` không đánh dấu cần đăng nhập lại, student session thiếu `mssv`/`email`, help trên stdout `cp1252` và ICS thiếu `DTSTAMP`. Bộ test có 313 case; các nhánh lỗi session dùng fixture. Live v2/HN đã xác nhận login, refresh, đọc dữ liệu và ICS có đủ `UID`/`DTSTAMP` UTC, sau đó dọn session/lock tạm. Xem [kết quả sau sửa](docs/phase4-coverage.md#kiểm-chứng-sau-bàn-giao-ngày-19102026); không dùng kết quả này đóng các TODO live v1 hoặc positive fee/survey.

## Quy tắc dữ liệu và thiết bị

Fiddler và Android chỉ phục vụ đối chiếu luồng đọc đã được cho phép. Dữ liệu request/response hoặc màn hình được xử lý cục bộ; chỉ tên operation, method, HTTP/body code, kiểu dữ liệu và kết quả kiểm tra được xuất ra. Không replay token từ capture, không đọc hoặc in token bằng tool, không gửi dữ liệu cá nhân ra ngoài PC. Không thay proxy, certificate, quyền truy cập hoặc dữ liệu tài khoản nếu không cần cho phép thử.

Các kết quả live chưa đạt vẫn phải được ghi trong coverage. Nếu backend chưa đáp ứng hoặc thiếu positive case, phạm vi phát hành cần maintainer quyết định; không đánh dấu parity đầy đủ chỉ từ fixture.

<a id="tasks-plan"></a>

---

Đường dẫn ban đầu: `tasks/plan.md`

Commit cuối thay đổi file tại commit gốc: `60c6a9c0193b00eed5fee7c4633abca816e6a569`

# Kế hoạch chuyển quy trình dev sang uv

## Phạm vi

Quản lý môi trường dev và dependencies bằng uv; sửa `myfap version` để đọc metadata của package `myfap`. Giữ setuptools, tên package và phạm vi Python >=3.9. Bump phiên bản lên 0.1.8 cho thay đổi này.

## Thứ tự thực hiện

1. Chọn Python 3.11 cho dev, tạo `uv.lock` và hướng dẫn README. Xác nhận `uv sync --locked` cài được package ở chế độ editable.
2. Thêm regression test qua lệnh CLI `version`, xác nhận test thất bại trước khi sửa tên distribution và thành công sau khi sửa.
3. Chuyển build CI sang uv, chạy test trên PR và giữ Trusted Publishing khi có release. Kiểm tra wheel và source distribution.
4. Review diff, kiểm tra tiếng Việt, tạo hai commit theo phạm vi và mở PR mới kèm bình luận kết quả kiểm tra.

## Rủi ro và cách kiểm tra

- Dependencies hiện chỉ có giới hạn phiên bản tối thiểu: lockfile cố định các phiên bản đã resolve; kiểm tra cài đặt và CLI trên Python 3.9/3.11.
- `greenlet` 3.2.5 thiếu wheel Python 3.9 trên Windows: giới hạn phiên bản qua cấu hình uv cho đúng môi trường này để tránh yêu cầu compiler C++.
- Playwright cần browser riêng khi đăng nhập: ghi rõ Chrome/Edge và Firefox dự phòng trong README; test version không đăng nhập hay gọi API.
- Môi trường dev và package phát hành khác nhau: kiểm tra `myfap version` cả sau editable install và sau cài wheel.

Danh sách công việc và trạng thái nằm trong [todo.md](tasks/todo.md).
