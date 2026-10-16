# MyFAP API CLI

## Giới thiệu

Đây là cli tương tác giống hoàn toàn với APP MYFAP trên điện thoại. Bạn có thể xem lịch học, lịch thi, điểm số (sự thất vọng của gia đình), thông tin cá nhân, v.v. 1 cách thuận tiện, không bị gò bó trong giao diện app. <br>
- Lưu ý: repo này được thực hiện cùng với sự hỗ trợ của AI.

## Tính năng chính
- Hỗ trợ đa nền tảng.
- Login thông qua FEID hoặc Google OAuth.
- Xem lịch học (từng tuần hoặc cả Kỳ).
- Xem điểm (từng môn hoặc cả Kỳ).
- Check điểm danh (từng môn hoặc cả Kỳ).
- Check tình trạng đơn từ.
- Xem thông báo của trường.
- Check Info của sinh viên hoặc phòng dvsv.
- Convert lịch học Kỳ sang **ICS**, dễ dàng import lịch học vào Google Calendar hoặc các dịch vụ tương tự.
- Và nhiều hơn nữa ...

## Cách sử dụng

Bạn có thể cài ứng dụng bằng pip theo hướng dẫn bên dưới. Để phát triển từ mã nguồn, xem mục dùng uv.

- Cài đặt ứng dụng.

  ```
  pip install myfap
  ```

- Lấy danh sách cơ sở.

  ```
  myfap campuses
  ```

- Login vào feid (chỉ cần làm 1 lần, mặc định chọn cơ sở Hola).
  ```
  myfap login
  ```
  Sau khi hoàn thành login, phiên đăng nhập sẽ dc lưu ở ``~/.myfap-api-cli/session.json`` <br>
- Login cho cơ sở Xavalo.
  ```
  myfap login -c HCM
  ```

- Lấy Lịch học *(tự động lấy kỳ mới nhất)*.

  ```
  myfap schedule
  ```

## Phát triển với uv

Bạn cần cài [uv](https://docs.astral.sh/uv/getting-started/installation/) trước khi bắt đầu. Repo dùng Python 3.11 cho môi trường dev, được chọn trong `.python-version`; package vẫn hỗ trợ Python từ 3.9. Cả `.python-version` và `uv.lock` được commit để các máy dùng cùng cấu hình và phiên bản dependency.

Clone repo và cài môi trường theo lockfile:

```sh
git clone https://github.com/WindowScary321/myfap-api-cli.git
cd myfap-api-cli
uv sync --locked
```

`uv sync` tạo `.venv` và cài package ở chế độ editable, nên thay đổi mã nguồn có hiệu lực khi chạy CLI. Bạn dùng `uv run` để chạy trong môi trường này, không cần activate thủ công hay chạy `uv init` trong repo đã có cấu hình.

```sh
uv run myfap --help
uv run myfap version
uv run python -m unittest discover -s tests -v
uv build
```

### Trình duyệt cho đăng nhập

Đăng nhập mở cửa sổ trình duyệt và ưu tiên Chrome đã cài trên máy, sau đó thử Edge. Nếu có Chrome hoặc Edge chạy được, bạn không cần cài thêm trình duyệt. Để dùng Firefox làm phương án dự phòng, cài trình duyệt của Playwright bằng lệnh sau:

```sh
uv run playwright install firefox
```

Bước cài Firefox là tùy chọn; việc build package không cần trình duyệt.

### Cập nhật dependency

Bạn dùng `uv add <tên-package>` hoặc `uv remove <tên-package>` để cập nhật dependency trong `pyproject.toml` và `uv.lock`. Nếu sửa dependency trực tiếp trong `pyproject.toml`, chạy `uv lock` rồi `uv sync --locked`. Sau khi kiểm tra, commit cả thay đổi cấu hình và lockfile cùng nhau. Không commit thư mục `.venv`.

## CI và kiểm tra artifact

CI dùng job `scope` để so sánh tên path thay đổi. Nếu PR hoặc push `main` chỉ thay đổi `docs/` hoặc `tasks/`, source/build/smoke được bỏ qua, không tạo artifact và check cuối vẫn thành công. PR có cả code lẫn tài liệu vẫn chạy đầy đủ; reusable workflow dùng cho release luôn chạy đầy đủ gate. Nếu scope hoặc gate code thất bại, check cuối thất bại.

Khi cần kiểm tra code, CI chạy trên Ubuntu/Windows với Python 3.9/3.11, build một bộ wheel/sdist trên Ubuntu, kiểm metadata bằng Twine và tạo `SHA256SUMS`. Cả bốn môi trường cài wheel và sdist vào hai venv tạm riêng ngoài checkout bằng pip, rồi chạy `pip check`, `myfap version` và `myfap --help`. Các bước này không đăng nhập FEID, gọi API FAP hoặc cài browser Playwright.

`docs/` và `tasks/` là tài liệu chỉ lưu trong repository: CI không checkout/đọc nội dung hai thư mục này để test hoặc build. `MANIFEST.in` loại chúng khỏi sdist cả khi build local từ checkout đầy đủ; artifact gate từ chối nếu chúng xuất hiện trong wheel/sdist. `README.md` và `LICENSE` ở root vẫn cần cho metadata package.

Cài nhóm công cụ CI và chạy các kiểm tra local bằng Python 3.11:

```sh
uv sync --locked --group ci
uv run --locked --group ci python -m unittest discover -s tests -v
uv build --out-dir dist
uv run --locked --group ci python -m twine check --strict dist/*.whl dist/*.tar.gz
uv run --locked --group ci python scripts/check_artifacts.py --dist-dir dist
uv run --locked --group ci python scripts/smoke_install.py --artifact-dir dist --expected-version 0.2.0
```

Thư mục artifact phải chỉ chứa đúng wheel/sdist của version hiện tại và manifest; không trộn file build cũ. Smoke dùng resolver pip từ metadata package, không áp dụng `uv.lock`. Marker `greenlet` cho Windows/Python 3.9 được khai báo trong dependency runtime để cả pip và uv cùng nhận ràng buộc.

Workflow hỗ trợ `workflow_call` với input `ref`; chỉ sau khi mọi gate pass mới trả `artifact_name`, `package_version` và `manifest_sha256`. Artifact chứa wheel, sdist và `SHA256SUMS` của cùng run, được giữ 14 ngày để dùng lại trong bước phát hành sau này.

Validator chặn các đường dẫn session, credential, capture và file ngoài allowlist; nó không đọc nội dung dữ liệu nhạy cảm và không thay thế review secret/PII trong mã nguồn Python hợp lệ. Toàn bộ CI chỉ có quyền đọc repository, không có quyền publish.

## Các Options
|Option|Chú thích|
|:-|:-|
|--help|Hiển thị bảng Commands và Options|
|--config <đường dẫn>|Đường dẫn tới file cấu hình session tùy chỉnh (mặc định: ~/.myfap-api-cli/session.json)|
|-c, --campus <cơ sở>|Mã cơ sở (VD: APHL, HCM, DN)  [default: APHL]|
|-s, --semester <kỳ học>|Tên kỳ học (VD: Summer2026)|
|-cid, --courseid <mã môn>|Chọn mã môn, chỉ có ở command ``marks``. (VD: 82934, lấy từ bảng điểm của kỳ, ko phải mã môn như PRO192, SWE201c, ...)|
|-w, --week <số tuần>|Chọn tuần, chỉ có ở command ``week-timetable``|
|-y, --year <số năm>|Chọn năm học, chỉ có ở command ``week-timetable``|
|-d, --date \<YYYY-MM-DD\>|Chỉ định ngày chính xác, chỉ có ở command ``week-timetable``|
|-sc, --subjectcode <mã môn>|Chọn môn học,  chỉ có ở command ``attendance``|
|-cn, --classname <mã lớp>|Chọn lớp học, chỉ có ở command ``attendance``|
|--ics|Convert Sang **ICS**, dễ dàng import lịch học vào Google Calendar hoặc các dịch vụ tương tự, chỉ có ở command ``schedule``)|
|-p, --pretty|Format lại bảng điểm gốc của trường sang dạng json, chỉ có ở command ``marks``)|
|--output, -o <thư mục>|Thư mục xuất file thay vì thư mục hiện tại|
|--stdout|In kết quả trực tiếp ra màn hình thay vì lưu file|
|-f, --force|Buộc đăng nhập lại, bỏ qua file ``session.json``, chỉ có ở command ``login``|

## [Các ví dụ sử dụng](./docs/Example.md)
