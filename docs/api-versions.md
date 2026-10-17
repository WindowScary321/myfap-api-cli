# Chọn API v1 hoặc v2

[Quay lại README](../README.md) · [Đăng nhập và session](oauth-session.md)

## Dùng v2

API v1 vẫn là mặc định cho session mới. Đặt `--api-version v2` trước command để dùng adapter v2 tối thiểu:

```sh
myfap --api-version v2 campuses
myfap --api-version v2 --campus HN --config ./state-v2.json login --force
myfap --api-version v2 --config ./state-v2.json semesters
myfap --api-version v2 --config ./state-v2.json schedule --stdout
```

Nên dùng file session riêng khi thử v2 để giữ session v1 hiện tại. CLI chọn version theo option, version đã lưu trong session, rồi mới đến mặc định v1. Session cũ thiếu trường version được hiểu là v1. Sau khi login v2 thành công, cùng file session có thể chạy lệnh mà không cần lặp option version.

Lấy mã campus bằng `campuses` của version đang dùng. Lần kiểm chứng v2 trả `HN` cho Cơ sở Hà Nội và không có `APHL`; handshake với `APHL` trả body 401, còn `HN` đã login thành công với tài khoản được cho phép. CLI không tự quy đổi mã campus. `HN` trong ví dụ là lựa chọn rõ ràng; campus mặc định của session mới vẫn là `APHL`, nên cần chọn mã đúng khi đăng nhập v2.

`login --force` mở lại luồng đăng nhập nhưng vẫn kế thừa campus trong file session nếu không có `--campus`. Vì vậy, `myfap --api-version v2 login -f` có thể gửi mã campus của v1 sang proxy v2. Với Hà Nội, chỉ định `--campus HN` như ví dụ trên; dùng `--config` riêng nếu muốn giữ session v1. Thư mục đang chạy lệnh và branch Git không quyết định campus.

Nếu FEID cấp token nhưng handshake FAP bị từ chối, CLI hướng dẫn kiểm tra campus theo version. Thông báo này chưa chứng minh token hết hạn hoặc campus chắc chắn là nguyên nhân; cần kiểm tra lại mã campus trước khi đăng nhập lặp lại.

## Phạm vi Phase 3

| Chức năng | API v2 |
|---|---|
| `campuses` | Bootstrap POST với JSON rỗng |
| `login`, `refresh` | FEID/OIDC và handshake v2 |
| `semesters` | GetSemester với query rỗng |
| `schedule`, gồm JSON/ICS hiện có | GetActivityStudent |
| `other survey` | Giữ host, chữ ký và envelope riêng của survey |
| Các FAP operation đọc còn lại | Báo chưa hỗ trợ; không fallback sang v1 |

`MyFapEssential.get_api_active()` chỉ gọi khi cần chẩn đoán proxy v2. CLI không dùng kết quả này để tự chọn version hoặc campus. Ma trận method/path/query/body/header, credential và capability nằm trong [contract v2](v2-contracts.md).

Các lệnh chưa được hỗ trợ không gọi route đoán hoặc trả danh sách rỗng để giả thành công. Với marks, exams, lịch tuần và attendance, CLI kiểm capability trước khi tra kỳ hoặc tuần. Nạp session vẫn có thể handshake nếu binding cần đổi. Việc phủ toàn bộ command v2 thuộc Phase 4.

## Đổi version của session

```sh
myfap --api-version v1 --config ./state-v2.json semesters
```

Đổi version yêu cầu handshake bằng FEID access token trước request dữ liệu. CLI không dùng FAP key của v2 để gửi sang v1 hoặc ngược lại. Binding mới chỉ được lưu sau khi handshake thành công; nếu FEID refresh token đã rotate trước đó thì token mới vẫn được giữ khi bước sau lỗi.

Nếu đổi campus, dùng mã được version đích hỗ trợ. Với cùng campus và loại tài khoản, CLI từ chối handshake làm thay MSSV/email ngoài một lần login mới. Session chưa có subject OIDC đã xác minh cần đăng nhập lại để chuyển version.

## Lỗi và kiểm chứng

V2 phân biệt HTTP/body 401, lỗi operation và App Check. Request đọc chỉ refresh/retry tối đa một lần, dùng key và chữ ký mới. HTTP 403 không được mặc định hiểu là hết phiên; App Check bị từ chối được báo riêng, không có cơ chế né hoặc fallback.

Timeout vẫn theo `--timeout`, `MYFAP_TIMEOUT`, rồi mặc định hiện có. Mọi request mới giữ cấu hình đó và không follow redirect. Chữ ký v2 ở header, không đưa FEID token hay FAP Bearer token vào URL của các operation Phase 3.

Xem [kết quả kiểm chứng](phase3-verification.md) để biết phần nào đã chạy live và phần nào chỉ có fixture. Không đưa session hoặc dữ liệu xuất ra Git; file session vẫn chứa credential dạng JSON trên máy.
