# Phát hành myfap bằng tag

Tài liệu này là runbook Phase 5 cho distribution `myfap`. Pipeline được chuẩn bị trong mã nguồn không đồng nghĩa đã được nghiệm thu trên GitHub Actions hoặc đã publish. Chỉ maintainer tạo/push tag sau khi PR chuẩn bị release đã merge và phạm vi hỗ trợ đã được duyệt. Không tự phát hành theo push `main`.

Xem [release notes](../CHANGELOG.md), [checklist Phase 5](../tasks/phase5.md) và [coverage API](phase4-coverage.md).

## 1. Quyết định phạm vi trước release

`0.2.0` giữ v1 mặc định, v2 opt-in và không fallback im lặng. Trước tag, maintainer phải xác nhận:

- Chấp nhận phạm vi và known issues trong mục `0.2.0` của `CHANGELOG.md`.
- Ba finding v1 vẫn được ghi đúng: news/notification HTTP 200/body 201, fee HTTP 404 trên APHL; nguyên nhân chưa biết. Không gọi chúng là đã sửa, empty hợp lệ hoặc unsupported trên mọi campus.
- Positive fee/survey được hoãn theo quyết định ngày 19/10/2026; schema live có dữ liệu vẫn chưa kiểm chứng. Việc hoãn không chặn chuyển Phase 5 nhưng không phải bằng chứng backend đạt.
- Reader độc lập đã kiểm ICS (lịch học `schedule --ics` và lịch thi `exams --ics`); import vào ứng dụng lịch thật đã kiểm chứng. Theo quyết định ngày 23/10/2026, phát hành `v0.2.0` sau khi hoàn thiện và nghiệm thu phạm vi Phase 6 (toàn bộ read student v1+v2, doctor, transcript --pretty, exams --ics; các thao tác ghi mục 4–5 giữ gate do thiếu dữ liệu tài khoản).

Việc yêu cầu tiếp tục Phase 5 không tự cho phép publish, tạo GitHub Release hoặc chấp nhận mọi giới hạn hỗ trợ. Ghi quyết định duyệt phạm vi trong PR chuẩn bị release trước khi tag; duyệt environment là gate cuối, không thay thế quyết định đó.

## 2. Thiết lập một lần ngoài repository

Cấu hình sau cần được maintainer kiểm tra trực tiếp; file workflow không chứng minh cấu hình dịch vụ đã tồn tại hoặc đúng quyền.

| Thành phần | Production | Rehearsal |
|---|---|---|
| Distribution | `myfap` | `myfap` trên TestPyPI |
| Owner | `WindowScary321` | `WindowScary321` |
| Repository | `myfap-api-cli` | `myfap-api-cli` |
| Workflow filename | `publish.yml` | `testpypi.yml` |
| GitHub environment | `pypi` | `testpypi` |
| Upload endpoint | PyPI mặc định | `https://test.pypi.org/legacy/` |

- Đăng ký Trusted Publisher riêng cho từng index, khớp đầy đủ identity trong bảng. Không thêm API token dài hạn.
- Bật required reviewers cho environment và giới hạn tag/ref được phép; maintainer đối chiếu commit, version, hash và known issues trước khi duyệt.
- Giữ quyền workflow mặc định read-only. Chỉ job upload có `id-token: write`; chỉ job tạo GitHub Release có `contents: write`.
- Kiểm tra bảo vệ `main`, quyền tạo tag và required checks. Không bỏ qua gate bằng cách di chuyển tag hoặc sửa quyền khi publish đang chạy.

**Trạng thái thiết lập:** chưa được xác nhận chỉ từ thay đổi mã nguồn Phase 5. Ghi người kiểm tra và kết quả tại checklist trước lần phát hành đầu tiên.

## 3. Chuẩn bị commit và tag

1. Kiểm working tree sạch, PR chuẩn bị release đã merge và lấy `main`/tag mới nhất.
2. Đối chiếu `[project].version`, root package trong `uv.lock`, CLI và artifact. Baseline đã là `0.2.0`; không bump lại từ `0.1.8`. Chỉ chạy `uv lock` khi metadata thực sự đổi, không sửa tay lockfile hoặc dùng `--upgrade` cho release thông thường.
3. Kiểm PyPI để biết version mục tiêu đã tồn tại hay chưa. Nếu version đã phát hành trước đó mà không phải đang phục hồi cùng release/artifact, dừng và để maintainer chọn version mới.
4. Chạy regression, build, Twine, validator và cài artifact theo [hướng dẫn phát triển](development.md#kiểm-tra-trên-máy-local). Ghi commit, lệnh, exit code và các phần chưa kiểm chứng.
5. Duyệt mục version trong `CHANGELOG.md`, coverage và quyết định phạm vi ở mục 1. Tag phải trỏ tới commit thuộc `origin/main`.

Các lệnh dưới đây **chỉ do maintainer chạy sau khi đã duyệt**, không phải bằng chứng đã thực hiện:

```powershell
git fetch origin main --tags
git switch main
git pull --ff-only origin main
git status --short --branch
# Xác nhận version, notes, CI và phạm vi trước hai lệnh tiếp theo.
git tag -a v0.2.0 -m "Phát hành myfap 0.2.0"
git push origin v0.2.0
```

Không dùng `--force`, không di chuyển/xóa tag để sửa một release đã upload. Stable pipeline chỉ nhận tag chuẩn `vX.Y.Z`, không nhận prerelease hoặc thành phần số có zero đứng đầu.

## 4. Luồng production

```text
push tag stable
  → validate tag/version/lockfile và commit thuộc origin/main
  → reusable CI trên đúng SHA đã resolve
  → đối chiếu artifact và trạng thái file trên PyPI
  → Trusted Publishing chỉ những file còn thiếu
  → kiểm cài từ PyPI trên matrix
  → tạo hoặc hoàn tất GitHub Release
```

### Validate và CI

- `publish.yml` bỏ trigger `release.published`; tag glob chỉ lọc sơ bộ. Helper xác minh format stable, metadata source/lockfile và SHA của tag.
- Workflow fetch đủ lịch sử và fetch rõ `origin/main`, rồi kiểm commit tag là ancestor của ref vừa fetch. Không checkout `main` thay cho commit tag khi test/build.
- `ci.yml` được gọi bằng `workflow_call` với input `ref` là SHA đã resolve. Output gồm `artifact_name`, `package_version`, `manifest_sha256`.
- Source tests và cài wheel/sdist chạy Ubuntu/Windows × Python 3.9/3.11. Chỉ tạo một bộ distribution phát hành; `publish.yml` không build lại.
- Mọi bước tải artifact đối chiếu version và manifest. `manifest_sha256` là SHA-256 của **bytes file `SHA256SUMS`**, không phải digest ZIP của GitHub artifact.
- Release notes lấy đúng mục version trong `CHANGELOG.md` và được ràng buộc hash; không dùng toàn bộ changelog làm notes.

### Đối chiếu PyPI và upload

Preflight đọc JSON metadata của đúng version trên PyPI và đối chiếu **từng tên file/hash** với bộ artifact đã kiểm:

| Trạng thái | Hành vi |
|---|---|
| Chưa có version/file | Upload bộ file còn thiếu đã xác minh |
| Upload một phần, file đã có đúng hash | Chỉ chuyển các file thiếu sang bước upload |
| Có đủ file, tất cả đúng hash | Bỏ qua upload, tiếp tục smoke/release |
| Có file lạ hoặc hash không khớp | Dừng; không ghi đè, không bỏ qua lỗi |

Job có quyền publish chỉ tải artifact, kiểm inventory/hash bằng verifier inline, đọc lại metadata index rồi gọi action Trusted Publishing. Việc đọc lại ngay trước upload là bắt buộc khi rerun job thất bại: output preflight của lần trước có thể đã cũ nếu server nhận được một phần hoặc toàn bộ file. File đã có đúng hash được loại khỏi thư mục upload; nếu không còn file thiếu thì bỏ qua action upload. Metadata lỗi hoặc hash xung đột phải dừng. Không checkout hoặc chạy mã nguồn dự án trong job này. Không bật `skip-existing` để che xung đột. Concurrency theo tag và không hủy publish đang chạy.

### Kiểm sau upload

- Job verify không có OIDC, giới hạn 15 phút, chạy Ubuntu/Windows × Python 3.9/3.11.
- Chờ index tối đa 6 lần, cách nhau 10 giây. Retry dành cho độ trễ xuất hiện package trên index; lỗi dependency, metadata, CLI hoặc hash không được coi là index chưa sẵn sàng.
- Cài đúng `myfap==X.Y.Z` trong venv sạch ngoài checkout, không cache, chỉ dùng `https://pypi.org/simple/`; loại bỏ cấu hình extra index và đường dẫn import bên ngoài.
- Chạy `pip check`, đối chiếu metadata/version CLI và `myfap --help`. Không đăng nhập FEID hoặc gọi API FAP trong post-publish smoke.

### GitHub Release

Chỉ tạo Release sau khi toàn bộ matrix post-publish đạt. Job riêng có `contents: write`, không OIDC và không checkout/chạy source dự án. Release gắn với tag đã kiểm, dùng notes tiếng Việt của đúng version và đính wheel, sdist, `SHA256SUMS` của cùng artifact đã publish.

Bước tạo mới dùng `gh release create --draft` với `GH_TOKEN` lấy từ `GITHUB_TOKEN`, không dùng token cá nhân dài hạn. Chỉ publish draft sau khi đọc lại đủ ba asset và xác minh hash. Để phục hồi draft, workflow tìm đúng tag qua danh sách release có quyền truy cập và phân trang; không dùng endpoint lấy published release theo tag để tìm draft. Bước này phải idempotent: Release đúng tag với asset đúng hash có thể được kiểm tra/hoàn tất; khác tag/commit hoặc hash phải dừng. Không thay tag, ghi đè asset xung đột hoặc tạo version mới để che lỗi workflow.

## 5. Retry và sự cố

### PyPI đã thành công, smoke hoặc Release thất bại

- Xác nhận version/file/hash trên PyPI khớp artifact của run.
- Chỉ rerun job thất bại và các job phụ thuộc cần thiết; không rerun build hoặc publish chỉ để thử lại hậu kiểm.
- Nếu phải phục hồi toàn pipeline, giữ đúng tag/SHA và đúng bộ artifact đã upload; preflight phải nhận diện đủ file cùng hash và bỏ upload. Build mới cho cùng version có thể khác bytes và phải bị chặn, không được xem là artifact thay thế.

### Upload một phần hoặc kết quả upload chưa rõ

1. Không vội retry action upload; server có thể đã nhận một file trước khi job báo lỗi.
2. Tải lại đúng wheel/sdist/manifest của **cùng run**, kiểm manifest và inventory trước.
3. Đọc lại metadata PyPI, đối chiếu từng tên file/hash. Nếu file đã có đúng hash, preflight có thể chuẩn bị chỉ file còn thiếu để tiếp tục upload.
4. Hash khác, file lạ, mất artifact gốc hoặc không xác định được nguồn bytes: dừng và điều tra. Không dùng `skip-existing`, build lại, đổi file hoặc di chuyển tag.
5. Khi đủ file cùng hash, chạy lại smoke/release; không upload lại file đã có.

Artifact GitHub có retention hữu hạn; lưu thông tin run/SHA/digest và hoàn tất phục hồi trước khi artifact hết hạn. Không tự coi một artifact build mới là cùng artifact chỉ vì tên version giống nhau.

### Version đã phát hành bị lỗi

PyPI không cho ghi đè file của version đã phát hành. Sửa lỗi bằng version mới, cập nhật source/lockfile/changelog, chạy lại gate và tạo tag mới. Maintainer cân nhắc yank bản lỗi, ghi rõ lý do và ảnh hưởng; yank không xóa dữ liệu đã cài và không phải rollback code trên máy người dùng.

## 6. TestPyPI rehearsal thủ công

`testpypi.yml` dùng `workflow_dispatch` với input tag rõ ràng; resolve tag thành SHA bất biến và gọi cùng reusable CI. Không chạy mỗi PR, không tự publish production và không tạo GitHub Release production.

- Dùng environment `testpypi` và Trusted Publisher riêng, upload tới `https://test.pypi.org/legacy/`.
- Giữ kiểm artifact/hash, đối chiếu file đã có và xử lý partial upload như production.
- Chỉ tải wheel đúng version từ TestPyPI bằng `--no-deps`; sau đó cài wheel local trong venv sạch, resolve dependency **chỉ từ PyPI**.
- Không trộn hai index bằng `--extra-index-url`. TestPyPI có catalog không đầy đủ, có thể bị dọn dẹp và không phải nơi lưu release lâu dài.
- Chạy `pip check`, metadata/version CLI và help. Kết quả rehearsal không chứng minh OAuth/API FAP hoạt động và không tự promote artifact sang PyPI.

TestPyPI upload cũng là hành động ra dịch vụ ngoài; chỉ chạy sau khi maintainer cho phép. Chưa có kết quả rehearsal/publish chỉ từ việc thêm workflow.

## 7. Ghi nhận nghiệm thu

Ghi kết quả tại [tasks/phase5.md](../tasks/phase5.md): commit, lệnh, exit code, matrix đã chạy và phần bị skip/chưa kiểm chứng. Phân biệt rõ:

- **Offline:** fixture tổng hợp và kiểm cấu hình; không gọi FEID/FAP.
- **Local live:** CLI thật với session tạm được phép, payload chỉ xử lý cục bộ; chỉ metadata đã lọc được ghi vào báo cáo.
- **Dịch vụ release:** Trusted Publisher/environment, TestPyPI, PyPI và GitHub Release phải có bằng chứng riêng.

Không ghi credential, raw response, query có giá trị, HAR/SAZ hoặc PII vào log, artifact, commit hay notes. Không dùng CI xanh, exit 0 của harness rỗng hoặc schema fixture để thay kết quả live.

## Tham chiếu

- [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
- [Cấu hình Trusted Publisher](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)
- [GitHub: reusable workflows](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows)
- [PyPA: dùng TestPyPI](https://packaging.python.org/en/latest/guides/using-testpypi/)
