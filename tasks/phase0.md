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
- [ ] Xác nhận toàn bộ matrix GitHub Actions trên commit cuối của PR.
- [ ] Cập nhật PR body và comment kết quả cuối; giữ working tree sạch.

## Kiểm chứng

- Unit suite local: 18 test pass, gồm regression version hiện có.
- `uv build`, `twine check --strict`, artifact validation và actionlint pass.
- Pip smoke thật trên Windows/Python 3.9 và 3.11 đang được kiểm tra; Ubuntu do GitHub Actions xác nhận.

## Giới hạn

CI không đăng nhập FEID hoặc gọi API FAP thật. Allowlist chỉ chặn đường dẫn/file ngoài chính sách; không chứng minh được không có secret hoặc PII ẩn trong nội dung mã Python. Kết quả Phase 0 không xác nhận OAuth/API v1/v2 đã được sửa.
