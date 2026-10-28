# Theo dõi lỗi PR #8 và kết quả kiểm chứng

Ngày bàn giao: **19/10/2026**. PR: <https://github.com/WindowScary321/myfap-api-cli/pull/8>.

Commit phát hiện lỗi ban đầu: `13cb6ef35c923d06c7b96acdf83eb7577aa3b4d6`, nhánh `feat/phase4-command-parity`. Số dòng và mô tả trước sửa bên dưới thuộc commit này.

Tại baseline ban đầu có **ba nhóm lỗi hành vi đã tái hiện qua CLI** và **một vi phạm định dạng ICS đã xác nhận**. Cả bốn đều tồn tại trước PR #8; đây là lỗi còn sót, không phải regression do commit sửa tài liệu `13cb6ef` gây ra. Mức P2 bên dưới là đề xuất ưu tiên sửa, không phải bằng chứng sự cố trên tài khoản thật.

## Kết quả kiểm tra lại ngày 19/10/2026

**Cả bốn finding đã được xử lý trong phạm vi kiểm chứng tại commit `eb8f0e302436c076a3a8644a4e7aa18718481fbb`.** Các mục 1–4 phía dưới giữ lại mô tả trước sửa và tiêu chí chấp nhận để truy nguyên. Không dùng các triệu chứng cũ làm kết luận về commit mới.

| Finding | Kết quả CLI sau sửa |
|---|---|
| Refresh `invalid_grant` | Trên v1/v2, lệnh đọc thất bại đúng dự kiến, session được đánh dấu `fap_needs_reauth=true`, `oidc_validated=false`; `login` thường đi tới bước yêu cầu mở browser. Credential được giữ; hủy ở bước browser không đổi file đã đánh dấu. |
| Thiếu identity | Với `email`/`mssv` bị bỏ hoặc là `null`, lệnh đọc dừng trước HTTP; `login` thường đi tới bước yêu cầu mở browser. File cũ được giữ khi hủy. |
| Help `cp1252` | Help root, nhóm `info`, `info student`, `other survey` và `schedule` đều exit 0, có đủ nội dung tiếng Việt. Root UTF-8 và JSON UTF-8 dưới stdout `cp1252` cũng đạt. |
| ICS `DTSTAMP` | CLI xuất stdout một sự kiện và file 250 sự kiện thành công. Reader độc lập xác nhận mỗi event có đúng một UID/DTSTAMP UTC, giữ DTSTART/DTEND, UTF-8 và CRLF. |

Kiểm tra đối chứng: refresh timeout trên v1/v2 không đổi file session, không lộ chuỗi lỗi giả và không tự mở browser khi chạy `login`. Regression trong repo cũng phủ lỗi OAuth khác, lỗi storage, các dạng identity sai và session cũ hợp lệ.

Đã chạy 25 tiến trình CLI độc lập và toàn bộ suite tại commit mới: **313 test, 309 đạt, 4 skip**. GitHub CI của commit này đạt 11/11 job: <https://github.com/WindowScary321/myfap-api-cli/actions/runs/39211433376>. Chưa thấy regression mới có đủ bằng chứng trong phần code sửa.

- [Lệnh, exit code, trạng thái session và kết quả ICS sau sửa](C:/Users/tubeo/Downloads/com.fuct-2.0.6-build31-analysis/work/pr8-cli-recheck-_8hm6jvn/results.json).
- [ICS 250 sự kiện sau sửa](C:/Users/tubeo/Downloads/com.fuct-2.0.6-build31-analysis/work/pr8-cli-recheck-_8hm6jvn/schedule-250.ics).

Các ca CLI độc lập vẫn chỉ dùng session/HTTP tổng hợp và sentinel chặn browser như mô tả ở dưới. Lượt này không gọi server thật hoặc thử nhập ICS vào ứng dụng lịch. Theo báo cáo mới của agent chính trong `docs/discovery/phase4-coverage.md`, ba lệnh v1 đã được chạy lại nhưng news/notification vẫn trả body 201 và fee vẫn HTTP 404; positive fee/survey còn mở. Đây là các giới hạn riêng, không bị đóng theo kết quả sửa bốn finding.

## Đánh giá chuyển từ Phase 4 sang Phase 5

Đối chiếu ngày 19/10/2026 tại cùng commit `eb8f0e3`: **có thể bắt đầu xây dựng và kiểm thử pipeline Phase 5, nhưng chưa đủ căn cứ tuyên bố nghiệm thu đầy đủ Phase 4 hoặc phát hành production**. Phần code cốt lõi và CI đã có; quyết định phạm vi hỗ trợ trước release vẫn còn thiếu.

| Tiêu chí trong kế hoạch | Bằng chứng hiện có | Kết luận |
|---|---|---|
| Adapter cho command đọc hiện có; giữ v1 mặc định, v2 opt-in | Allowlist 18 operation đọc, wrapper/CLI và bảng contract | Đã triển khai; chưa thấy command Phase 4 bị bỏ quên |
| Session, phân loại lỗi, retry, JSON/ICS | 313 test, 25 lượt CLI kiểm chứng độc lập và bốn finding đã sửa | Đạt phần kiểm tra offline hiện có |
| CI và artifact | 11/11 check tại đúng commit: source matrix, build/Twine/validator, wheel/sdist smoke | Đạt |
| Kiểm ICS bằng reader độc lập hoặc ứng dụng lịch | Reader `icalendar` kiểm mọi event trong lịch 250 sự kiện, gồm UID/DTSTAMP/UTC/CRLF | Đạt lựa chọn reader độc lập; không cần bắt buộc Google Calendar/Outlook để thỏa điều khoản này |
| Chạy lại ba lệnh v1 thất bại | Có báo cáo live v1/APHL ngày 19/10 và lệnh đối chứng | Đã chạy lại; news/notification vẫn body 201, fee vẫn HTTP 404 |
| Xác nhận schema có dữ liệu thật cho fee/survey | Fee v2 mới có HTTP/body 200; survey mới có not-found | Theo quyết định ngày 19/10/2026: hoãn vào TODO, không chặn chuyển Phase 5; schema vẫn chưa kiểm chứng |
| Chốt phạm vi cho ba lỗi v1 trước release | Đã có coverage và TODO, nhưng chưa thấy quyết định chấp nhận giới hạn trong PR/comments | Chưa hoàn tất quyết định release |
| Trạng thái PR | Draft, open, chưa merge; chưa có submitted review | Còn bước review/merge do maintainer quyết định |

**Căn cứ:** `../PLAN.md:118–120,139` và `../PLAN-PHASES.md:235–250,267–272`. Kế hoạch cho phép giữ kết quả thất bại/thiếu positive case ở trạng thái chưa kiểm chứng; nếu chưa giải quyết được lỗi v1 thì maintainer phải quyết định giới hạn hỗ trợ trước release. Vì vậy không tự biến thiếu positive case thành yêu cầu phải có tài khoản phù hợp ngay để bắt đầu viết pipeline, nhưng cũng không tự coi thiếu bằng chứng là parity đã hoàn tất.

Phần việc đầu tiên của Phase 5 cần giải quyết:

1. Chốt phạm vi release cho news/notification/fee v1: có bằng chứng sửa thành công, hoặc maintainer chấp nhận giới hạn cụ thể theo version/campus và ghi rõ trong release notes. Không tự đổi mặc định sang v2 hoặc fallback để che lỗi.
2. Positive fee/survey đã được người dùng đồng ý hoãn ngày 19/10/2026 vì chưa thể kiểm chứng hiện tại. Theo dõi tại `docs/discovery/todo.md`, giữ schema là chưa kiểm chứng và ghi rõ giới hạn trong release notes; mục này không chặn chuyển Phase 5.
3. Thêm `CHANGELOG.md` cùng known issues và phạm vi đã chốt. File này chưa có; đây là đầu việc được giao cho Phase 5, không phải tính năng bị bỏ sót của Phase 4.
4. Sau review/merge và quyết định phạm vi, mới tạo tag/publish theo kế hoạch. Không sử dụng workflow publish cũ như pipeline Phase 5 đã hoàn thành.

Hạ tầng có thể tái sử dụng: `.github/workflows/ci.yml` đã có `workflow_call`, input `ref` và outputs `artifact_name`, `package_version`, `manifest_sha256`. Workflow `publish.yml` hiện vẫn chạy từ `release.published`, test/build/publish chung một job; chưa có tag validation, nhận artifact từ reusable CI, post-publish smoke hay job tạo GitHub Release. Đó là phạm vi triển khai kế tiếp, không phải blocker kỹ thuật mới của PR #8.

Đã đọc metadata công khai từ <https://pypi.org/pypi/myfap/json> ngày 19/10/2026: distribution khớp repository này, bản mới nhất là `0.1.8`, chưa có file phát hành `0.2.0`. Tại thời điểm kiểm tra chưa có xung đột version; cần kiểm tra lại ngay trước publish. Transcript, balance, ảnh, feedback đầy đủ, push và donor/employee thuộc Phase 6, không chặn Phase 5.

## Bằng chứng và giới hạn kiểm chứng

Đã chạy **15 tiến trình riêng bằng `.venv/Scripts/myfap.exe`** trên Windows/Python 3.11. Tất cả kiểm tra đều dùng session và dữ liệu tổng hợp. HTTP được chặn và trả response giả lập ngay trong tiến trình con; không gọi server thật, không đọc session cá nhân. Logic CLI, storage, nạp session, refresh và xử lý response OAuth chạy nguyên bản.

Riêng `MyFapAuth._authorize` được thay bằng một hàm báo `REVIEW_BROWSER_REQUESTED` để xác nhận chương trình đã đi tới bước yêu cầu mở browser. Exit 1 có sentinel này là điểm dừng chủ động của phép thử, **không phải một lỗi đăng nhập mới**.

- [Toàn bộ lệnh, exit code và HTTP trace đã lọc](C:/Users/tubeo/Downloads/com.fuct-2.0.6-build31-analysis/work/pr8-cli-verification-efcl8s7o/results.json).
- [File ICS do CLI xuất từ fixture tổng hợp](C:/Users/tubeo/Downloads/com.fuct-2.0.6-build31-analysis/work/pr8-cli-verification-efcl8s7o/schedule.ics).
- Thư mục chứa stdout/stderr riêng cho từng ca: `C:/Users/tubeo/Downloads/com.fuct-2.0.6-build31-analysis/work/pr8-cli-verification-efcl8s7o/`.

Các lệnh có `--config` trong phần dưới được chạy với đường dẫn session tạm riêng. Để tái hiện lỗi cần server phản hồi, phải dựng đúng HTTP fixture đã mô tả; chỉ chạy lệnh bằng tài khoản thật không bảo đảm gặp điều kiện đó.

## 1. P2 — Login không phục hồi sau khi refresh trả `invalid_grant`

**Vị trí:** `myfap/auth.py:249` (`_refresh_locked`), đặc biệt nhánh bắt lỗi tại dòng 271–273; caller tại `refresh_session`, `myfap/api.py` và `myfap/cli.py:200`.

**Điều kiện tái hiện:**

1. Session có đủ identity, binding, FAP key, FEID access token và refresh token tổng hợp; `fap_needs_reauth` đang là `false`.
2. Chạy `myfap --config ... info student --stdout`.
3. HTTP fixture trả 401 cho `GetStudentById`; OIDC discovery trả metadata hợp lệ; token endpoint trả HTTP 400 với `{"error":"invalid_grant"}`.
4. Chạy tiếp `myfap --config ... login` bằng cùng file session.

**Kết quả đã quan sát trên cả v1 và v2:**

- Lệnh đọc exit 1 và báo: `Phiên FAP hết hạn hoặc không hợp lệ. Hãy đăng nhập lại.`
- Refresh token endpoint được gọi đúng một lần.
- File session vẫn giữ `fap_needs_reauth: false`.
- `login` tiếp theo exit 0, báo `Đã có session được lưu...`, không đi vào luồng browser.
- `login --force` đi tới sentinel `REVIEW_BROWSER_REQUESTED`.

Bằng chứng trong `results.json`: các ca `v1_expired_read`, `v1_expired_login`, `v1_expired_force` và ba ca tương ứng của v2.

**Nguyên nhân:** khi token request thất bại trước `_set_tokens`, `_refresh_locked` trả `False` mà không phản ánh việc session cần đăng nhập lại vào trạng thái lưu. Lần `login` sau chỉ xét trạng thái cục bộ và tiếp tục coi session là sẵn sàng.

**Hướng sửa:** xử lý riêng lỗi xác thực không thể phục hồi như `invalid_grant`, lưu trạng thái cần đăng nhập lại và để `login` thường mở lại luồng đăng nhập. Không gộp timeout, lỗi mạng tạm thời hoặc lỗi storage vào cùng cách vô hiệu hóa session; giữ cơ chế bảo toàn token đã rotate và khóa file hiện có.

**Tiêu chí chấp nhận:**

- [ ] Regression v1/v2 tái hiện chuỗi đọc → FAP 401 → refresh `invalid_grant` → `login` thường.
- [ ] Sau lỗi xác thực nói trên, `login` đi vào luồng browser mà không cần `--force`.
- [ ] Timeout/lỗi mạng không tự mở browser hoặc làm mất credential đang lưu.
- [ ] Hủy hoặc thất bại khi đăng nhập mới vẫn giữ file session theo hợp đồng hiện có; không phát sinh refresh/retry vô hạn.

## 2. P2 — Session thiếu identity vẫn được coi là dùng được

**Vị trí:** `myfap/auth.py:98–111` (`_restore`), `ensure_bound`, `load_session` và `myfap/cli.py:200`.

**Điều kiện tái hiện:** tạo session tổng hợp còn campus, version v2 và `authen_key`, nhưng bỏ `email` hoặc `mssv`. Không cần gọi HTTP để tái hiện.

| Session | Chuỗi lệnh CLI | Kết quả hiện tại |
|---|---|---|
| Thiếu `email` | `login`, sau đó `other survey --stdout` | Login exit 0; survey exit 1, báo thiếu email và yêu cầu chạy login lại |
| Thiếu `mssv` | `login`, sau đó `info student --stdout` | Login exit 0; lệnh đọc exit 1, báo query v2 không hợp lệ |

Thêm `--config` trỏ tới cùng file session tạm cho từng lệnh. `login --force` trong cả hai ca đều đi tới bước yêu cầu mở browser. Bằng chứng: `missing_email_login/read/force` và `missing_mssv_login/read/force` trong `results.json`.

**Nguyên nhân:** điều kiện `value is not None and not _text(value)` chỉ chặn giá trị sai khi trường có mặt và khác `None`. Trường bị bỏ hoặc mang giá trị `null` vẫn được chấp nhận; readiness sau đó chỉ xét key/binding. Handshake thành công vốn yêu cầu cả FAP key, roll number và email, nên những identity này khác với metadata OAuth có thể thiếu ở session cũ.

**Hướng sửa:** xác nhận identity cần cho session student trước khi coi session là sẵn sàng. Cho `login` phục hồi trường hợp thiếu identity bằng cơ chế lỗi cấu trúc/binding hiện có. Không bắt mọi metadata OAuth trở thành trường bắt buộc chỉ để xử lý hai ca này.

**Tiêu chí chấp nhận:**

- [ ] Kiểm tra cả trường bị bỏ và giá trị `null` của `email`/`mssv`; các giá trị sai kiểu hoặc rỗng vẫn bị chặn.
- [ ] `login` thường phục hồi được session thiếu identity; không còn vòng lặp lệnh đọc yêu cầu login nhưng login chỉ báo đã có session.
- [ ] Session v1/v2 đầy đủ identity và session cũ hợp lệ vẫn dùng được.
- [ ] Hủy luồng đăng nhập mới không thay nội dung file cũ; lỗi cấu trúc không gây request dữ liệu thiếu identity.

## 3. P2 — `--help` lỗi khi stdout dùng `cp1252`

**Vị trí:** cấu hình Typer/Rich tại `myfap/cli.py:63–67` và các nội dung help tiếng Việt. Xử lý UTF-8 trong `save_output`/`print_table` hiện chưa bao phủ help.

**Lệnh tái hiện độc lập:** chạy đoạn PowerShell sau từ root repository. Nó chỉ đặt encoding cho hai tiến trình con, không đổi encoding toàn máy.

```powershell
@'
import os
import subprocess

for encoding, utf8 in [('cp1252:strict', '0'), ('utf-8', '1')]:
    env = dict(os.environ, PYTHONIOENCODING=encoding, PYTHONUTF8=utf8)
    result = subprocess.run(
        ['.venv/Scripts/myfap.exe', '--help'],
        env=env, capture_output=True, timeout=20,
    )
    print(encoding, 'exit=', result.returncode,
          'stdout_bytes=', len(result.stdout),
          'UnicodeEncodeError=', b'UnicodeEncodeError' in result.stderr)
'@ | .venv/Scripts/python.exe -
```

**Kết quả đã ghi nhận:** `cp1252` exit 1, stdout 244 byte rồi dừng với `UnicodeEncodeError`; UTF-8 exit 0, stdout 3406 byte. Kích thước output chỉ là bằng chứng tại baseline này, không phải giá trị cần hardcode vào test. Bằng chứng: `help_cp1252` và `help_utf8`.

**Hướng sửa:** bảo đảm các đường render help hỗ trợ tiếng Việt khi output bị pipe/capture; dùng cách xử lý ít thay đổi nhất phù hợp Typer/Rich hiện có. Giữ stdout JSON và byte/CRLF của ICS đã được kiểm chứng.

**Tiêu chí chấp nhận:**

- [ ] Root `--help` và help của command/nhóm lệnh có tiếng Việt exit 0 trong subprocess với stdout `cp1252:strict` và UTF-8.
- [ ] Output có đủ nội dung help, không chỉ nuốt exception để trả exit 0.
- [ ] Các regression JSON, bảng dữ liệu và ICS hiện có tiếp tục đạt.

## 4. P2 — ICS thiếu trường bắt buộc `DTSTAMP`

**Vị trí:** `myfap/parsers.py:106`, nơi tạo `Event()` trong `convert_schedule_to_ics`.

**Điều kiện tái hiện:** cho HTTP fixture `GetActivityStudent` trả nội dung `tests/fixtures/schedule_valid.json`, sau đó chạy CLI với session tổng hợp:

```text
myfap --config <file-session-tạm> schedule --semester Fall2026 --ics --stdout
```

Đây là ký hiệu cho lệnh đã chạy trong harness; `<file-session-tạm>` phải là đường dẫn fixture riêng, không dùng session cá nhân để giả lập response.

**Kết quả:** CLI exit 0, xuất một VEVENT có `UID`, `DTSTART`, `DTEND` nhưng thiếu `DTSTAMP`. Reader `icalendar` đọc được file và cho `required=('UID', 'DTSTAMP')`; danh sách trường thiếu là `['DTSTAMP']`. Bằng chứng: ca `schedule_ics` và file `schedule.ics` đã liên kết ở đầu tài liệu.

[RFC 5545, mục 3.6.1](https://www.rfc-editor.org/rfc/rfc5545.html#section-3.6.1) quy định `DTSTAMP` và `UID` là bắt buộc với VEVENT. **Đã xác nhận vi phạm định dạng; chưa xác nhận Google Calendar, Outlook hoặc ứng dụng cụ thể nào từ chối file này.** Không ghi nhận xét này thành lỗi crash hay lỗi import chắc chắn.

**Nguyên nhân:** event không được gán thuộc tính để thư viện `ics` xuất `DTSTAMP`. Reader vẫn parse được nên chỉ kiểm parse thành công hoặc `event.errors == []` chưa bắt được lỗi.

**Hướng sửa:** gán thời điểm UTC hợp lệ khi dựng event bằng API thư viện hiện có, đồng thời kiểm trường bắt buộc qua reader độc lập. Không cần đổi thư viện runtime chỉ để thêm trường này.

**Tiêu chí chấp nhận:**

- [ ] Mỗi VEVENT có đúng một `UID` và một `DTSTAMP` hợp lệ ở UTC.
- [ ] Test kiểm mọi event, không chỉ event đầu; vẫn giữ DTSTART/DTEND, timezone, UTF-8 và CRLF hiện có.
- [ ] CLI vẫn xuất được ICS qua stdout và file; bộ dữ liệu tổng hợp 250 sự kiện tiếp tục đọc được.

## Phạm vi bàn giao và kiểm tra sau sửa

Ưu tiên hai lỗi session trước, sau đó help và ICS. Sửa tại code dùng chung sau khi rà caller; thêm regression cho từng điều kiện đã chứng minh. Không đổi thông số phiên bản hoặc triển khai tính năng mới chỉ để đóng các lỗi này.

Bản sửa dependency trong hướng dẫn dev tại `13cb6ef` đã đúng. Trong môi trường tạm sạch có UTF-8, hướng dẫn cài nhóm `ci` chạy được help/version và toàn bộ 306 test: 302 đạt, 4 skip. Không mở lại finding thiếu `icalendar` đã được xử lý.

Sau các bản sửa runtime, chạy regression liên quan rồi chạy bộ test hiện có:

```powershell
uv sync --locked --group ci
uv run --locked --group ci python -m unittest discover -s tests -v
git diff --check
```

Các command đọc trong phạm vi Phase 4 chưa có thiếu sót tích hợp nào được xác nhận. Những phần sau vẫn là công việc riêng theo kế hoạch, không gộp vào bốn lỗi ở trên:

- Kết quả live: đã chạy lại news/notification/fee v1 và luồng v2 có đăng nhập sau sửa; ba response lỗi v1 vẫn mở. Positive fee/survey chuyển sang TODO hoãn theo quyết định ngày 19/10/2026, không chặn chuyển Phase 5.
- Phase 5: pipeline tag → validate → reusable CI → publish → kiểm tra sau publish → GitHub Release.
- Phase 6: transcript, điểm tổng kết/phong trào, môn/khóa học theo kỳ, balance, ảnh, tìm news, server `GetVersion`, feedback list/form/submit, rating, push và donor/employee.

Nguồn phạm vi: [`tasks/phase4.md`](https://github.com/WindowScary321/myfap-api-cli/blob/467df1edb2220261dcd21392fbe3eaf008d6c662/tasks/phase4.md), `docs/discovery/todo.md`, `docs/cli/v2-contracts.md` và `../PLAN-PHASES.md`. Không đóng các mục live bằng fixture hoặc CI xanh; không coi backlog Phase 5/6 là regression của PR #8.

Tài liệu này bàn giao kết quả kiểm chứng để sửa code. Chưa có xác nhận live trên tài khoản thật hoặc thử nhập ICS vào ứng dụng lịch.
