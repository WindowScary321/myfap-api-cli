# Kiểm chứng CLI với API thật, ngày 16/10/2026

## Kết quả

Đã chạy executable CLI từ checkout commit `07fb289`, dùng session mẫu qua luồng nạp session thông thường. Đợt kiểm chứng chuẩn gồm 25 lần chạy command, phủ 20 route: 22 lần exit 0, 3 lần exit 1. Có thử điểm ở một kỳ có dữ liệu để kiểm tra điểm chi tiết; không ghi kỳ, mã môn hoặc nội dung điểm vào báo cáo.

Phase 1 đã có kiểm chứng live cho các luồng đọc chính, nhưng còn ba lỗi ở `news`, `other notification` và `other fee`. Kết quả unit test và CI thành công không thay thế việc giải quyết ba lỗi này.

| Command hoặc biến thể | HTTP / body code | Kết quả |
|---|---|---|
| `version`, `--help` | Không gọi HTTP | Exit 0 |
| `campuses`, `semesters` | 200 / 200 | Exit 0, bảng hiển thị được |
| `info student`, `info campus` | 200 / 200 | Exit 0, JSON hợp lệ |
| `schedule` tự chọn kỳ | 200 / 200 | Exit 0, JSON hợp lệ |
| `schedule --ics` | 200 / 200 | Exit 0, cấu trúc ICS hợp lệ |
| `marks` tự chọn kỳ và chỉ định kỳ | 200 / 200 | Exit 0, xử lý được cả danh sách rỗng và có dữ liệu |
| `marks --courseid <ID>` | 200 / 200 | Exit 0, giữ HTML trong JSON |
| `marks --courseid <ID> --pretty` | 200 / 200 | Exit 0, HTML được chuyển thành danh sách JSON |
| `exams` | 200 / 200 | Exit 0, danh sách rỗng vẫn hợp lệ |
| `week-timetable --date <DATE>` | 200 / 200 | Exit 0, tra tuần và lấy lịch được |
| `attendance`, điểm danh chi tiết | 200 / 200 | Exit 0, JSON hợp lệ |
| `applications` | 200 / 200 | Exit 0, JSON hợp lệ |
| `other survey` | 200 / 404 | Exit 0, giữ `Data Not Found` và `data: null` |
| `other feedback`, `other profile` | 200 / 200 | Exit 0, giữ kiểu boolean |
| `other subjects` | 200 / 200 | Exit 0, JSON hợp lệ |
| `news` | 200 / 201 | Exit 1, `data: null` |
| `other notification` | 200 / 201 | Exit 1, `data: null` |
| `other fee` với `GeFeeByRoll` | 404 / không có envelope FAP | Exit 1, không diễn giải thành không nợ |

Các command JSON đều được chạy với `--stdout`. Khi thành công, toàn bộ stdout parse được thành JSON; khi ba command thất bại, stdout rỗng. Progress và lỗi nằm trên stderr.

ICS có thể parse lại trong process kiểm tra riêng sau khi tăng recursion limit của Python. Parser thư viện `ics` ở giới hạn mặc định đã gặp `RecursionError` với output live; command xuất ICS vẫn exit 0. Chưa kiểm tra import vào Google Calendar hoặc ứng dụng lịch khác.

## Ba vấn đề chưa giải quyết

### Thông báo trả code 201

`GetTop10News` và `GetNotificationByRoll` đều trả HTTP 200, body code 201, `data: null` và `message: null` trong các lần thử. Kiểm tra session bằng `GetSemester` ngay trước đó vẫn trả 200/200; các route dữ liệu khác cũng chạy được.

CLI hiện phân loại code 201 thành `ApiSessionExpiredError`. Bằng chứng live chưa đủ để kết luận hai lỗi này là hết phiên: cần phân biệt lỗi theo operation với tín hiệu session hết hạn rõ ràng. Không refresh cưỡng bức hoặc thay credential để che lỗi. Chưa xác định nguyên nhân ở backend, tài khoản hay contract request.

### Học phí trả HTTP 404

Contract APK v1 dùng `GeFeeByRoll`, nhưng route này trả HTTP 404 trong lần thử thực tế. Một phép chẩn đoán chỉ đọc, chạy riêng ngoài mã runtime, dùng lại request để so sánh tên cũ `GetFeeByRoll`; route cũ cũng trả 404. Không triển khai fallback hoặc thay route theo suy đoán.

Chưa có response học phí v1 thành công để kiểm chứng `IsPaid`, invoice và amount trên backend hiện tại. Các kiểm tra bảo toàn trường vẫn dựa trên fixture tổng hợp. Không suy ra trạng thái thanh toán từ HTTP 404.

### Điều kiện chốt kiểm chứng live

- [ ] Xác định và xử lý nguyên nhân code 201 của hai route thông báo; bổ sung regression tổng hợp khi có contract rõ.
- [ ] Xác nhận endpoint học phí v1 đang hoạt động hoặc ghi nhận unsupported có căn cứ; cần một response thành công để kiểm chứng schema thực.
- [ ] Kiểm tra lại ba command sau khi có thay đổi phù hợp. Giữ kết quả thất bại hiện tại trong lịch sử kiểm chứng.

## Giới hạn và bảo vệ dữ liệu

Bạn có thể dùng báo cáo này để đánh giá route và output CLI, chưa thể coi đó là kiểm chứng đầy đủ mọi tài khoản hoặc campus. Survey mới được kiểm chứng trạng thái not-found, chưa có trường hợp thành công có survey bắt buộc. Login mới, OAuth callback, refresh rotation, đổi campus, API v2 và thao tác ghi nghiệp vụ chưa được kiểm thử trong lượt này.

Không đọc, liệt kê, sao chép hoặc kiểm tra trực tiếp thư mục session của người dùng. Chỉ executable CLI tự nạp session theo hành vi sẵn có. Command chạy tuần tự; không chạy `login`, `logout` hoặc `refresh` thủ công.

Stdout/stderr và response thật chỉ được xử lý trong RAM. Chương trình kiểm tra chỉ xuất metadata trong danh sách cho phép: route, mã HTTP/body, loại dữ liệu, exit code và kết quả kiểm tra định dạng. Không lưu response, header, query có giá trị, lịch học, bảng điểm, đơn từ, identity, credential hoặc biến môi trường bí mật vào repo, fixture, commit hay comment PR. Không phát lại HAR/SAZ.

Các script chạy live nằm ngoài repository và không được đưa lên GitHub. Báo cáo này và bản cập nhật checklist chỉ chứa kết quả đã che dữ liệu. `docs/` và `tasks/` vẫn là repository-only, không nằm trong artifact PyPI.
