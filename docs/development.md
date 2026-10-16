# Phát triển và kiểm tra

[Quay lại README](../README.md)

## Phát triển với uv

Cài [uv](https://docs.astral.sh/uv/getting-started/installation/) trước khi bắt đầu. Repo dùng Python 3.11 cho môi trường dev, theo `.python-version`; package vẫn hỗ trợ Python từ 3.9. File `uv.lock` lưu phiên bản dependency. Cả hai file được commit để các máy dùng cùng cấu hình.

Clone repo và tạo môi trường theo lockfile:

```sh
git clone https://github.com/WindowScary321/myfap-api-cli.git
cd myfap-api-cli
uv sync --locked
```

`uv sync` tạo `.venv` và cài package ở chế độ editable. Khi sửa mã nguồn, bạn có thể chạy lại CLI để dùng thay đổi đó ngay. Dùng `uv run` để chạy lệnh trong môi trường này mà không cần activate thủ công. Repo đã có cấu hình nên không cần chạy `uv init`.

Chạy các lệnh sau từ thư mục gốc của repo:

```sh
uv run myfap --help
uv run myfap version
uv run python -m unittest discover -s tests -v
uv build
```

### Trình duyệt cho đăng nhập

CLI mở cửa sổ trình duyệt để đăng nhập, ưu tiên Chrome đã cài trên máy rồi đến Edge. Nếu dùng được một trong hai, bạn không cần cài thêm trình duyệt. Để có Firefox làm phương án dự phòng, chạy:

```sh
uv run playwright install firefox
```

Chỉ cần bước này khi muốn dùng Firefox; build package không cần trình duyệt.

### Cập nhật dependency

Dùng `uv add <tên-package>` hoặc `uv remove <tên-package>` để cập nhật cả `pyproject.toml` và `uv.lock`. Nếu sửa dependency trực tiếp trong `pyproject.toml`, chạy `uv lock` rồi `uv sync --locked` để đồng bộ lại môi trường.

Sau khi kiểm tra, commit thay đổi cấu hình cùng lockfile. Giữ `.venv` ở máy local, không commit thư mục này.

## CI và kiểm tra artifact

Job `scope` chỉ so sánh tên path thay đổi. Với PR hoặc push `main` chỉ sửa `docs/` hoặc `tasks/`, CI bỏ qua source/build/smoke, không tạo artifact và job `ready` trả kết quả thành công. Nếu có thay đổi ở code hoặc file khác, CI chạy đầy đủ. `README.md` và `LICENSE` ở root vẫn thuộc phạm vi kiểm tra vì cần cho metadata package.

Khi chạy đầy đủ, CI kiểm tra source trên Ubuntu và Windows, mỗi hệ điều hành dùng Python 3.9 và 3.11. Job build tạo một bộ wheel/sdist trên Ubuntu, kiểm metadata bằng Twine rồi tạo `SHA256SUMS`. Sau đó, cả bốn môi trường cài wheel và sdist bằng pip vào hai venv tạm riêng ngoài checkout, chạy `pip check`, `myfap version` và `myfap --help`. Các bước này không đăng nhập FEID, gọi API FAP hoặc cài trình duyệt Playwright.

### Kiểm tra trên máy local

Cài nhóm công cụ CI và chạy các lệnh sau bằng Python 3.11 từ thư mục gốc của repo:

```sh
uv sync --locked --group ci
uv run --locked --group ci python -m unittest discover -s tests -v
uv build --out-dir dist
uv run --locked --group ci python -m twine check --strict dist/*.whl dist/*.tar.gz
uv run --locked --group ci python scripts/check_artifacts.py --dist-dir dist
uv run --locked --group ci python scripts/smoke_install.py --artifact-dir dist --expected-version 0.2.0
```

Thư mục artifact phải chỉ chứa wheel/sdist của version hiện tại và manifest. Nếu còn file build cũ, chuyển chúng ra ngoài trước khi chạy kiểm tra. Các lệnh local kiểm tra môi trường Python đang dùng; matrix trên GitHub Actions kiểm tra đủ hai hệ điều hành và hai phiên bản Python.

Smoke test dùng pip để resolve dependency từ metadata package, không áp dụng `uv.lock`. Marker `greenlet` cho Windows/Python 3.9 nằm trong dependency runtime để cả pip và uv cùng nhận ràng buộc.

### Phạm vi package và kết quả CI

`docs/` và `tasks/` chỉ lưu trong repository. CI không checkout hoặc đọc nội dung hai thư mục này để test/build. `MANIFEST.in` loại chúng khỏi sdist cả khi build local từ checkout đầy đủ; artifact validator báo lỗi nếu chúng xuất hiện trong wheel hoặc sdist.

Reusable workflow hỗ trợ `workflow_call` với input `ref` và luôn chạy đầy đủ các bước kiểm tra. Job `ready` báo lỗi nếu `scope` hoặc source/build/smoke thất bại. Chỉ khi tất cả bước bắt buộc thành công, workflow mới trả `artifact_name`, `package_version` và `manifest_sha256`. Artifact gồm wheel, sdist và `SHA256SUMS` của cùng run, được giữ 14 ngày để dùng trong bước phát hành sau này.

Artifact validator chặn đường dẫn session, credential, capture và file ngoài allowlist. Validator không đọc nội dung dữ liệu nhạy cảm; vẫn cần review secret/PII có thể nằm trong mã Python hợp lệ. Workflow CI chỉ có quyền đọc repository, không có quyền publish.
