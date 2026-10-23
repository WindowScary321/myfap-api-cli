# Phase 5: chuẩn bị và tự động phát hành 0.2.0

Nhánh `feat/phase5-release-automation` bắt đầu từ `origin/main` tại `06d98e115bb63a244d793236f81d7b62f63a5dc7`, sau khi PR #8 đã merge. Package giữ `0.2.0`, Python >=3.9, v1 mặc định và v2 opt-in.

Phạm vi phase là chuẩn bị release notes, gate tag/version/artifact, Trusted Publishing, post-publish smoke và GitHub Release; thêm endpoint mới thuộc Phase 6 theo kế hoạch workspace. Người dùng đã xác nhận commit và push **nhánh tính năng** sau kiểm tra. Nhánh đang được theo dõi trong [Draft PR #9](https://github.com/WindowScary321/myfap-api-cli/pull/9). Tạo/push tag, upload và thay đổi cấu hình dịch vụ cần maintainer cho phép riêng; chưa tạo tag, publish hoặc GitHub Release.

Mapping command → method → endpoint → URL → capability được hợp nhất tại [command-endpoints.md](../docs/command-endpoints.md), kèm danh sách route còn chưa tích hợp. Không dùng trạng thái triển khai pipeline hoặc live command cốt lõi để tuyên bố đã thêm toàn bộ endpoint.

Hai commit mã nguồn đã kiểm: `671ca5f06b63ce4ae826732fb4f1a3a64c252f62` (công cụ và regression release) và `e0178737b07de80878231f9875a049e755953939` (pipeline và regression workflow). Commit tài liệu bàn giao nằm tiếp sau, không đổi code đã test.

## Phạm vi hỗ trợ cần duyệt trước tag

- [ ] Maintainer duyệt mục `0.2.0` trong [CHANGELOG.md](../CHANGELOG.md), coverage và known issues.
- [ ] Ghi rõ quyết định với ba lỗi live v1/APHL còn mở: news/notification HTTP 200/body 201, fee HTTP 404. Không tuyên bố đã sửa hoặc parity đầy đủ.
- [ ] Giữ positive fee/survey là TODO hoãn chờ dữ liệu phù hợp; schema live có dữ liệu chưa kiểm chứng. Quyết định hoãn ngày 19/10/2026 cho phép chuyển Phase 5, không chứng minh backend đạt.
- [ ] Giữ giới hạn ICS: reader độc lập đã kiểm; import vào ứng dụng lịch thật chưa kiểm chứng.

Các finding v1 và positive case nằm trong [TODO](todo.md) và [coverage Phase 4](../docs/phase4-coverage.md). Phase 6 không chặn `0.2.0`.

## Gate kỹ thuật

- [ ] Tag stable đúng `vX.Y.Z`, không prerelease/zero đứng đầu; tag, source, lockfile và artifact cùng version.
- [ ] Fetch rõ `origin/main`; SHA tag đã resolve thuộc lịch sử `main` trước build/upload.
- [ ] Gọi reusable CI trên đúng SHA, nhận `artifact_name`, `package_version`, `manifest_sha256`; không build lại trong workflow publish.
- [x] Matrix source và cài wheel/sdist đạt Ubuntu/Windows × Python 3.9/3.11; artifact không có docs/tasks/tests/session/capture. [CI PR #9 tại commit bc8a7ee](https://github.com/WindowScary321/myfap-api-cli/actions/runs/39960229451) đạt đủ 11 job; không đồng nghĩa pipeline tag/publish đã chạy.
- [ ] Mọi download đối chiếu inventory và hash; notes lấy đúng mục version, được ràng buộc digest.
- [ ] Preflight đối chiếu từng file/hash trên index, phân biệt missing/partial/complete; chỉ upload file thiếu đã xác minh, dừng khi có xung đột.
- [ ] Chỉ job upload có OIDC và environment `pypi`; không checkout/chạy source dự án trong job đặc quyền.
- [ ] Post-publish smoke cài đúng version từ PyPI trong venv sạch ngoài checkout, không cache/extra index; tối đa 6 lần chờ index, cách 10 giây, mỗi job 15 phút.
- [ ] GitHub Release chỉ sau toàn bộ smoke, job riêng `contents: write`, không OIDC; notes/asset cùng artifact, xử lý rerun idempotent.
- [ ] Workflow TestPyPI thủ công dùng tag/ref bất biến, publisher/environment riêng và không trộn index dependency.
- [ ] Runbook ghi rõ partial upload, retry hậu publish, version mới/yank và không di chuyển tag.

## Kiểm tra local và offline

Kiểm tra local hoàn tất ngày **23/10/2026**, trên nền commit `06d98e115bb63a244d793236f81d7b62f63a5dc7` cùng thay đổi Phase 5 sau đó được lưu trong hai commit mã nguồn nêu trên. Chưa tạo tag hay phát hành. CI PR đã chạy trên GitHub Actions và đạt tại commit `bc8a7ee`; các gate workflow tag/publish và Trusted Publisher vẫn để mở vì chưa nghiệm thu phát hành thật.

Các lệnh dưới đây chạy từ checkout CLI; với workspace gốc dùng `uv --directory myfap-phase2-review-fixes ...` để giữ đúng working directory. Chỉ `--project` chọn môi trường mà không đổi thư mục làm việc sẽ khiến các test import `tests`/`scripts` và validator metadata thất bại; các lượt sai thư mục trước đó không được tính là đạt.

| Nhóm | Lệnh | Exit code | Kết quả và giới hạn |
|---|---|---|---|
| Đồng bộ CI | `uv sync --locked --group ci` | 0 | Không đổi dependency/lockfile |
| Regression release helper | `uv run --locked --group ci python -m unittest discover -s tests -p test_release_tools.py -v` | 0 | 12 test; Git/HTTP/artifact tổng hợp |
| Hợp đồng workflow | `uv run --locked --group ci python -m unittest discover -s tests -p test_release_workflows.py -v` | 0 | 23 test; thực thi inline verifier/reconcile/Release bằng biên mạng giả, gồm draft và phân trang |
| Bộ unittest Python 3.11 Windows | `uv run --locked --group ci python -m unittest discover -s tests -v` | 0 | 360 test: 356 đạt, 4 skip theo môi trường |
| Bộ unittest Python 3.9 Windows | `uv run --python 3.9 --locked --group ci python -m unittest discover -s tests -v` với `UV_PROJECT_ENVIRONMENT` trỏ venv tạm riêng | 0 | 360 test: 356 đạt, 4 skip theo môi trường; không thay `.venv` dev |
| Build | `uv build --out-dir dist-phase5` | 0 | Wheel/sdist version 0.2.0; một bộ artifact được giữ để kiểm lại |
| Twine | `uv run --locked --group ci python -m twine check --strict dist-phase5/*.whl dist-phase5/*.tar.gz` | 0 | Cả wheel và sdist đạt |
| Artifact validator | `uv run --locked --group ci python scripts/check_artifacts.py --dist-dir dist-phase5 --verify-manifest --expected-version 0.2.0 --manifest-sha256 9f2c7edbdcf27e49f528b0d45ab8988d2209cc45bf8dc5e6845fba278f6c2000` | 0 | Metadata/inventory/hash khớp; docs/tasks/tests không nằm trong artifact |
| Pip smoke wheel/sdist | `uv run --locked --group ci python scripts/smoke_install.py --artifact-dir dist-phase5 --expected-version 0.2.0` | 0 | Hai venv sạch ngoài checkout trên Windows/Python 3.11; dependency từ metadata, không dùng lockfile |
| Workflow lint | `actionlint ci.yml publish.yml testpypi.yml` với đường dẫn workflow đầy đủ | 0 | actionlint 1.7.12 cục bộ; không thay kiểm chứng GitHub Actions thật |
| `git diff --check` | `git diff --check` | 0 | Không lỗi whitespace; Git có cảnh báo chuyển LF/CRLF, không phải lỗi nội dung |

Bốn skip là ba phép tạo symlink thiếu quyền trên Windows và một phép kiểm mode POSIX không áp dụng với ACL Windows. Chưa chạy matrix Ubuntu hoặc pip smoke Python 3.9 của artifact trong lượt local này; matrix đó đã được cấu hình cho CI, không được ghi nhận đã đạt từ test Windows.

Regression mới cho smoke index kiểm TestPyPI tải wheel bằng `--no-deps`, đối chiếu bytes SHA-256 trước khi cài wheel local và chỉ lấy dependency từ PyPI. Fixture cũng phủ index hiện một phần rồi đầy đủ, tối đa 6 lần chờ, metadata sai/duplicate/yanked và lỗi cài không tự retry. Mutation check trên bản sao tạm đảo điều kiện so hash làm test wheel hỏng thất bại như mong đợi; harness exit 0 với `mutation_detected=true`, không sửa source trong checkout.

Review đã phát hiện và sửa: tìm draft Release qua endpoint published-tag không thành công; rehearsal vô tình yêu cầu version có trước trên production; wheel tải chưa so hash; index hiện một phần không được retry. Regression đã được bổ sung cho các trường hợp này. Job publish cũng đọc lại index ngay trước upload để rerun không dùng danh sách preflight đã cũ.

### Đối chiếu index công khai, không upload

- Bộ ba file wheel/sdist/`SHA256SUMS` được copy sang thư mục tạm đúng như download artifact CI rồi chạy `release_tools.py verify`: exit 0. `.gitignore` do `uv build` sinh ra bị verifier download từ chối đúng thiết kế; không nới inventory để cho file ngoài danh sách đi qua.
- `release_tools.py pypi-state` với version 0.2.0 và manifest đã kiểm trả `state: missing`, exit 0 ở lượt ngày 20/10/2026; đây là đọc metadata, không upload.
- `smoke_index.py --expected-version 0.1.8 --attempts 1 --delay 0` đã cài bản đang tồn tại từ PyPI và kiểm CLI thành công, exit 0 trong lượt đầu ngày 20/10/2026 và lượt kiểm lại helper cuối ngày 23/10/2026. Không suy ra post-publish smoke 0.2.0 đã đạt.
- SHA-256 manifest bộ artifact local: `9f2c7edbdcf27e49f528b0d45ab8988d2209cc45bf8dc5e6845fba278f6c2000`. Đây là artifact kiểm tra local, không phải bằng chứng đã upload từ GitHub Actions.

## Kiểm tra CLI thật cục bộ

Ngày 20/10/2026, chạy CLI thật trên **v2/HN** bằng browser FEID cục bộ, session tạm riêng và timeout HTTP 30 giây. Nền mã runtime là commit `06d98e115bb63a244d793236f81d7b62f63a5dc7`; thay đổi Phase 5 đang ở working tree và không sửa logic API/auth. Payload và output nhạy cảm chỉ được xử lý trong RAM cục bộ, ngoài kết nối FEID/FAP cần thiết; chỉ metadata đã lọc được xuất ra. Không dùng dữ liệu thật làm fixture.

| Lệnh | Exit code | Kiểm định dạng / trạng thái quan sát |
|---|---|---|
| `login` | 0 | Browser login hoàn tất; session tạm được tạo |
| `info student --stdout` trước và sau refresh | 0 | JSON hợp lệ; body code 200 |
| `semesters` | 0 | CLI bảng; không lưu nội dung kỳ học |
| `schedule --stdout` | 0 | JSON hợp lệ; body code 200 |
| `schedule --ics --stdout` | 0 | Reader `icalendar` đọc được, có sự kiện, UID/DTSTAMP và CRLF |
| `marks`, `exams`, `attendance`, `applications`, `news` với `--stdout` | 0 | JSON hợp lệ; body code 200 |
| `info campus`, `other fee`, `other notification` với `--stdout` | 0 | JSON hợp lệ; body code 200 |
| `other survey --stdout` | 0 | JSON hợp lệ; body code 404, giữ trạng thái not-found |
| `refresh` | 0 | Đọc `info student` sau refresh vẫn đạt |
| `logout` | 0 | File session đã xóa; thư mục tạm chứa lock được dọn sau harness |

Không ghi nhận HTTP status ở harness này, không suy ra HTTP 200 chỉ từ body code. Không kiểm tra nội dung positive fee/survey; các TODO đó vẫn mở. Không chạy lại v1 trong lượt Phase 5 này và không thay thế kết quả thất bại v1 ngày 19/10. Lượt đầu dùng `python -m myfap.cli` không gọi entry point đã bị loại bỏ; toàn bộ kết quả trong bảng là lượt gọi đúng `app()`.

### Lượt live mới và CI của PR #9

Ngày 23/10/2026, trên commit `bc8a7ee3131093432de427e1954743ee34618f45`, đã login mới hoàn toàn rồi chạy 22 lần command trên v2/HN: tất cả exit 0; 28 request FAP/survey thuộc 19 operation. Lượt này ghi được HTTP/body code tại biên HTTP thật, không thay response. ICS và JSON hợp lệ; refresh và đọc sau refresh đạt. Hai nhóm chi tiết điểm/điểm danh bị skip vì không lấy được tham số phù hợp. Fee có data không rỗng nhưng schema nghiệp vụ chưa được đối chiếu; survey vẫn HTTP 200/body 404. Session/lock tạm đã dọn; chỉ metadata đã lọc được lưu. Xem [mapping và kết quả chi tiết](../docs/command-endpoints.md#lượt-live-mới-ngày-23102026).

[CI run 39960229451](https://github.com/WindowScary321/myfap-api-cli/actions/runs/39960229451) của Draft PR #9 trên commit `bc8a7ee` đã đạt 11/11 job, gồm source và artifact smoke Ubuntu/Windows × Python 3.9/3.11. Đây là CI của PR, không phải một lượt push tag → PyPI → GitHub Release. Lượt local trước đó vẫn có giới hạn môi trường như đã ghi, không được đổi thành kết quả Ubuntu local.

## Gate dịch vụ và phát hành thực tế

Các mục này **chưa kiểm chứng**, không tự đánh dấu từ test offline/local:

- [ ] Trusted Publisher production khớp owner `WindowScary321`, repo `myfap-api-cli`, workflow `publish.yml`, environment `pypi`, distribution `myfap`.
- [ ] Environment `pypi` có required reviewers và giới hạn ref/tag phù hợp; maintainer duyệt phạm vi trước tag.
- [ ] Trusted Publisher/environment TestPyPI riêng: workflow `testpypi.yml`, environment `testpypi`.
- [ ] Rehearsal TestPyPI được cho phép và ghi kết quả nếu cần; không coi là nghiệm thu API.
- [ ] PR chuẩn bị release đã merge, tag stable do maintainer tạo/push và trỏ tới commit thuộc `main`.
- [ ] Upload PyPI, post-publish matrix và GitHub Release cùng artifact đã có bằng chứng thành công.
- [ ] Retry/partial upload được nghiệm thu mà không build lại, republish file đã có hoặc di chuyển tag.

## Bàn giao

Xem [runbook phát hành](../docs/releasing.md). Khi báo kết quả, ghi đúng commit và trạng thái working tree, lệnh/exit code đã chạy, phần chưa chạy và mọi giới hạn. Không khẳng định hoàn tất phát hành `0.2.0` nếu PyPI/GitHub Release chưa được kiểm chứng.
