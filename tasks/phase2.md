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
- `session_store.py`: đọc JSON, ghi atomic và khóa file; chỉ auth orchestration điều phối transaction.
- `auth.py`: vòng đời OAuth/FAP session, binding, identity handshake và rotation; CLI không tự mở file session để refresh.
- `api.py`: kiểm binding và retry đọc có giới hạn; payload/output hiện có được giữ nguyên.

Các module mới phục vụ trust boundary và tránh circular import; không thêm framework hoặc adapter v2 trong Phase 2.

## Checklist

- [ ] Regression cho hai body 201 và ma trận HTTP/body 401, App Check, timeout/5xx, read/write retry.
- [ ] Callback/OIDC có test âm về chữ ký, issuer, audience/azp, nonce, expiry và at_hash; refresh có thể thiếu ID token nhưng nếu có phải cùng subject.
- [ ] Session cũ thiếu version được hiểu là v1; đổi binding bị chặn trước HTTP dữ liệu, handshake lỗi không ghi nhầm binding.
- [ ] Atomic write và lock được kiểm bằng file tạm/process riêng trên Windows và Unix; không đọc session thật trong test offline.
- [ ] Test rotation chứng minh token mới được persist trước handshake và được giữ lại khi validation/handshake lỗi.
- [ ] Matrix Ubuntu/Windows × Python 3.9/3.11, wheel/sdist, Twine và smoke cài bằng pip pass.
- [ ] Live gate ghi rõ phần đã kiểm chứng và phần cần thao tác đăng nhập; chỉ lưu metadata đã che dữ liệu.
- [ ] Review độc lập, kiểm tra tiếng Việt và scan credential/PII trước commit/push; comment từng mốc vào draft PR.

## Giới hạn

Không đọc, liệt kê, sao chép hoặc kiểm tra trực tiếp thư mục session cá nhân. Live chỉ chạy CLI theo luồng thông thường; không lưu token, identity, lịch học, bảng điểm hoặc raw response vào Git. Không phát lại HAR/SAZ.

Phase 4 tiếp tục điều tra lỗi backend/contract của news, notification và fee; sửa phân loại 201 không làm các endpoint đó trở thành thành công. Binding chuyển v2 và live đổi API version hoàn tất khi có adapter Phase 3. Auto release vẫn thuộc Phase 5.
