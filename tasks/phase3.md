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

- [ ] Contract matrix ghi method/path/query/body/header, nguồn Bearer và signing identity, account type, read/write và retry. Ghi đủ các route v2 giữ query Authen, kể cả route chưa triển khai.
- [ ] Test chữ ký bằng dữ liệu giả, timestamp cố định; ngăn decode khóa hex và double-encoding padding.
- [ ] Test bootstrap, handshake, kỳ học query rỗng, schedule và lỗi unsupported; giữ regression v1.
- [ ] Test lựa chọn version, session legacy, chuyển v1/v2 hai chiều và rollback binding khi handshake lỗi.
- [ ] Test CLI, stdout, timeout, HTTP/body 401, App Check và retry dùng key/chữ ký mới.
- [ ] Matrix Ubuntu/Windows × Python 3.9/3.11, build, Twine strict, artifact validator và pip smoke.
- [ ] Live bằng session tạm riêng: campuses → login → semesters → schedule. Chỉ ghi metadata đã che; phần chưa kiểm chứng phải được ghi rõ.
- [ ] Review độc lập và rà tiếng Việt cho tài liệu, commit, comment PR. PR giữ draft.

Không đọc trực tiếp thư mục session cá nhân, không đưa token, query có credential, raw response, lịch học hoặc điểm thật vào Git. Nguồn contract là tài liệu và module APK trong workspace; capture không được phát lại. Không tạo tag, publish hoặc chuyển mặc định sang v2 trong phase này.
