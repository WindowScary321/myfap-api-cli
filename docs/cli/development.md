# Phát triển và kiểm tra

## Phát triển với uv

Cài [uv](https://docs.astral.sh/uv/getting-started/installation/). Repo dùng Python 3.11 cho môi trường dev

Clone this shit
```sh
git clone https://github.com/WindowScary321/myfap-api-cli.git
cd myfap-api-cli
uv sync --locked --group ci
```
Test các chức năng cơ bản
```sh
uv run myfap --help
uv run myfap version
uv run --locked --group ci python -m unittest discover -s tests -v
uv build
```

### Cài đặt trình browser cần thiết cho Playwright

CLI mở cửa sổ trình duyệt để đăng nhập, ưu tiên Chrome rồi đến Edge. Nếu không dùng dc cả 2, hãy cài firefox của Playwright:

```sh
uv run playwright install firefox
```

### Cập nhật dependency

Dùng `uv add <tên-package>` hoặc `uv remove <tên-package>` để cập nhật dependency. Nếu sửa trực tiếp trong `pyproject.toml`, chạy `uv lock` rồi `uv sync --locked` để đồng bộ lại môi trường

## CI và kiểm tra artifact

- **Cảnh báo: AI SLOP, đọc như đấm vào mồm**

Với PR hoặc push `main` chỉ sửa `docs/`, CI bỏ qua luôn; quy tắc cũng giữ hỗ trợ đường dẫn `tasks/` cũ. Nếu có thay đổi ở code hoặc file khác, CI vẫn chạy. `README.md` và `LICENSE` ở root vẫn thuộc phạm vi kiểm tra vì cần cho metadata package

Khi chạy đầy đủ, CI kiểm tra source trên Ubuntu và Windows, mỗi hệ điều hành dùng Python 3.9 và 3.11. Job build tạo một bộ wheel/sdist trên Ubuntu, kiểm metadata bằng Twine rồi tạo `SHA256SUMS`. Sau đó, cả bốn môi trường cài wheel và sdist bằng pip vào hai venv, chạy `pip check`, `myfap version` và `myfap --help`. Các bước này không đăng nhập FEID, gọi API FAP hoặc cài trình duyệt Playwright (nặng vl, mấy ô muốn đợi à)

### Kiểm tra trên máy local

```sh
uv sync --locked --group ci
uv run --locked --group ci python -m unittest discover -s tests -v
uv build --out-dir dist
uv run --locked --group ci python -m twine check --strict dist/*.whl dist/*.tar.gz
uv run --locked --group ci python scripts/check_artifacts.py --dist-dir dist
uv run --locked --group ci python scripts/smoke_install.py --artifact-dir dist --expected-version 0.2.0
```

Thư mục artifact phải chỉ chứa wheel/sdist của version hiện tại và manifest. Nếu còn file build cũ, copy ra ngoài trước khi chạy

Smoke test dùng pip để resolve dependency từ metadata package, không áp dụng `uv.lock`. Marker `greenlet` cho Windows/Python 3.9 nằm trong dependency runtime để cả pip và uv cùng nhận ràng buộc

### Phạm vi package và kết quả CI

**Quy tắc đóng gói:** Thư mục `docs/` chỉ lưu ở repo và được `MANIFEST.in` loại khỏi sdist (kể cả khi build local); quy tắc cũng loại `tasks/` cũ. CI không đọc các thư mục này khi build/test; artifact validator sẽ báo lỗi nếu chúng xuất hiện trong wheel hoặc sdist

**Reusable workflow (`workflow_call`):** Nhận input `ref`. Job `ready` sẽ fail nếu bước `scope`, source, build hoặc smoke test thất bại. Khi toàn bộ kiểm tra thành công, workflow xuất ra `artifact_name`, `package_version` và `manifest_sha256`

Artifact gồm wheel, sdist và `SHA256SUMS` cùng run, lưu retention 14 ngày phục vụ release

Validator chặn file theo allowlist, ngăn rò rỉ session, credential và file capture. *Lưu ý:* Validator chỉ đối soát đường dẫn, không quét nội dung file để tìm secret/PII
Workflow chạy với quyền read-only, không có quyền publish

### Regression cho API v1 và dữ liệu

**Độ bao phủ:** Unit test kiểm tra query/encoding, chọn kỳ theo ngày, survey/học phí, phân loại lỗi, parser HTML và xuất stdout định dạng JSON/ICS

**Dữ liệu test & Bảo mật:**
Toàn bộ fixture trong `tests/fixtures/` là dữ liệu giả lập (mock credential, domain `example.invalid`)

Test chạy offline/độc lập: không đăng nhập, không parse HAR/SAZ và không gọi API thật

Bộ test và fixture chỉ nằm trong repo, không đóng gói vào wheel/sdist

**Môi trường & Timezone:** File ICS sử dụng timezone Việt Nam từ `pytz`, không phụ thuộc vào timezone database của hệ điều hành trên Windows

Chi tiết trạng thái và giới hạn kiểm chứng xem tại [tasks/phase1.md](https://github.com/WindowScary321/myfap-api-cli/blob/467df1edb2220261dcd21392fbe3eaf008d6c662/tasks/phase1.md)

## Chuẩn bị phát hành Phase 5

Quy trình tag → reusable CI → Trusted Publishing → post-publish smoke → GitHub Release nằm trong [runbook phát hành](releasing.md). Theo dõi kết quả và các gate chưa kiểm chứng tại [docs/discovery/phase5.md](../discovery/phase5.md); release notes và known issues nằm trong [CHANGELOG.md](../../CHANGELOG.md).

Chỉ maintainer tạo/push tag sau khi PR chuẩn bị release đã merge và phạm vi hỗ trợ đã được duyệt. Test offline hoặc cài artifact thành công không xác nhận Trusted Publisher, publish thật hay nghiệm thu backend.
