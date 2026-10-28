# Chọn API v1 hoặc v2

[Quay lại README](../README.md) · [Đăng nhập và session](oauth-session.md)

## Chọn version

CLI chọn API theo thứ tự ưu tiên:

```text
--api-version (option CLI)  >  MYFAP_API_VER (biến môi trường)  >  version trong session  >  v2
```

Trong mã nguồn hiện tại, **v2 là mặc định** khi chưa có option, biến môi trường hoặc session; bản đã cài từ PyPI có thể chưa bao gồm thay đổi này. Đặt `MYFAP_API_VER=v1` (hoặc dùng `--api-version v1`) để chọn v1. Nếu chuyển từ session v2, cần handshake lại và có thể phải đăng nhập lại; hãy chọn campus phù hợp hoặc dùng session riêng:

```powershell
$env:MYFAP_API_VER = "v1"; myfap semesters
myfap --api-version v2 --campus HN --config ./state-v2.json login --force
```

Biến môi trường nhận `v1` hoặc `v2`; giá trị khác bị từ chối trước khi nạp session hoặc gọi mạng. Option CLI luôn thắng biến môi trường; biến môi trường thắng version đã lưu trong session. Session cũ **tồn tại** nhưng thiếu trường `api_version` tiếp tục được hiểu là v1 để không dùng credential v1 sang v2; chỉ khi chưa có file session mới rơi tới mặc định v2.

Đổi version vẫn yêu cầu handshake lại và giữ mọi ràng buộc binding/campus như trước; CLI không tự đổi campus (không chuyển `APHL` thành `HN`) và không fallback version khi gặp lỗi. Nên dùng file session riêng khi thử v2 để giữ session v1 hiện tại. Các option chung `--api-version`, `--campus`, `--config` và `--timeout` đều dùng được trước hoặc sau command, kể cả lệnh con. Option ở lệnh con ưu tiên hơn option ở nhóm cha; nếu lặp trong cùng cấp thì lấy giá trị cuối. Sau khi login v2 thành công, cùng file session có thể chạy lệnh mà không cần lặp option version. `doctor` giữ hành vi riêng: không đọc session, chọn version theo option/biến môi trường rồi v2.

Lấy mã campus bằng `campuses` của version đang dùng. Lần kiểm chứng v2 trả `HN` cho Cơ sở Hà Nội và không có `APHL`; handshake với `APHL` trả body 401, còn `HN` đã login thành công với tài khoản được cho phép. CLI không tự quy đổi mã campus. V1 vẫn có mặc định `APHL`; login v2 yêu cầu `--campus` nếu profile mới hoặc session cũ chỉ có `APHL` — kể cả khi v2 được chọn qua mặc định hoặc biến môi trường.

`login --force` mở lại luồng đăng nhập nhưng vẫn kế thừa campus trong file session nếu không có `--campus`. Khi dùng v2 mà không chỉ định campus, CLI chặn `APHL` trước khi mở trình duyệt, handshake hoặc refresh, kể cả với `login` không có `--force`. Session đã lưu mã khác `APHL` vẫn được kế thừa. Với Hà Nội, chỉ định `--campus HN` như ví dụ trên; dùng `--config` riêng nếu muốn giữ session v1. Thư mục đang chạy lệnh và branch Git không quyết định campus.

Nếu FEID cấp token nhưng handshake FAP bị từ chối, CLI hướng dẫn kiểm tra campus theo version. Thông báo này chưa chứng minh token hết hạn hoặc campus chắc chắn là nguyên nhân; cần kiểm tra lại mã campus trước khi đăng nhập lặp lại.

## Phạm vi hiện tại

| Chức năng | API v2 |
|---|---|
| `campuses` | Bootstrap POST với JSON rỗng |
| `login`, `refresh` | FEID/OIDC và handshake v2 |
| `semesters` | GetSemester với query rỗng |
| `schedule`, gồm JSON/ICS hiện có | GetActivityStudent |
| `other survey` | Dùng dịch vụ survey riêng cho cả v1/v2; có thông báo trên stderr khi dùng v2 |
| Các command đọc FAP khác đã có trong CLI | Đã có adapter v2 trong Phase 4; xem [bảng coverage](phase4-coverage.md) |
| Operation chưa có capability | Chặn trước khi nạp session; không fallback sang v1 |

`MyFapEssential.get_api_active()` chỉ gọi khi cần chẩn đoán proxy v2. CLI không dùng kết quả này để tự chọn version hoặc campus. Ma trận method/path/query/body/header, credential và capability nằm trong [contract v2](v2-contracts.md).

CLI kiểm tra capability của operation chính trước khi nạp session cho các command đọc cần session qua proxy, gồm `applications`, `news`, nhóm `info` và nhóm `other`. Lệnh chưa hỗ trợ dừng trước handshake, refresh, tra kỳ/tuần hoặc request dữ liệu. Lệnh được hỗ trợ vẫn có thể handshake nếu binding cần đổi. Survey dùng contract độc lập tại `survey.fpt.edu.vn`, giữ nguyên chữ ký và envelope riêng; thông báo trên stderr giúp phân biệt dịch vụ này với proxy v2.

## Đổi version của session

```sh
myfap --api-version v1 --config ./state-v2.json semesters
```

Đổi version yêu cầu handshake bằng FEID access token trước request dữ liệu. CLI không dùng FAP key của v2 để gửi sang v1 hoặc ngược lại. Binding mới chỉ được lưu sau khi handshake thành công; nếu FEID refresh token đã rotate trước đó thì token mới vẫn được giữ khi bước sau lỗi.

Nếu đổi campus, dùng mã được version đích hỗ trợ. Với cùng campus và loại tài khoản, CLI từ chối handshake làm thay MSSV/email ngoài một lần login mới. Session chưa có subject OIDC đã xác minh cần đăng nhập lại để chuyển version.

## Lỗi và kiểm chứng

V2 phân biệt HTTP/body 401, lỗi operation và App Check. Request đọc chỉ refresh/retry tối đa một lần, dùng key và chữ ký mới. HTTP 403 không được mặc định hiểu là hết phiên; App Check bị từ chối được báo riêng, không có cơ chế né hoặc fallback.

Timeout vẫn theo `--timeout`, `MYFAP_TIMEOUT`, rồi mặc định hiện có. Mọi request mới giữ cấu hình đó và không follow redirect. Chữ ký v2 ở header, không đưa FEID token hay FAP Bearer token vào URL của các operation Phase 3.

Xem [kết quả kiểm chứng](../history.md#docs-phase3-verification) để biết phần nào đã chạy live và phần nào chỉ có fixture. Không đưa session hoặc dữ liệu xuất ra Git; file session vẫn chứa credential dạng JSON trên máy.
