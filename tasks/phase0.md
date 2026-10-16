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
