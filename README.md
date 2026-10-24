# MyFAP API CLI

## Giới thiệu

CLI tương tác với các API myFAP để xem lịch học, lịch thi, điểm và thông tin sinh viên. Phạm vi hỗ trợ phụ thuộc API version, campus và capability từng endpoint; CLI chưa thay thế đầy đủ mọi chức năng của app. Xem [mapping command/endpoint](./docs/command-endpoints.md) và [coverage Phase 6](./docs/phase6-coverage.md) để biết phần đã triển khai, đã kiểm thử và còn chưa xác minh. <br>
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

- Cài đặt cli

  ```
  pip install myfap
  ```

- Lấy danh sách cơ sở

  ```
  myfap campuses
  ```

- Login vào feid (chỉ cần làm 1 lần, mặc định chọn Hola)
  ```
  myfap login
  ```
  Sau khi hoàn thành login, phiên đăng nhập sẽ dc lưu ở ``~/.myfap-api-cli/session.json`` <br>

- Login cho cơ sở Xavalo 
  ```
  myfap login -c HCM
  ```

- Lấy Lịch học *(tự động lấy kỳ mới nhất)*.

  ```
  myfap schedule
  ```

## Command mở rộng trên nhánh phát triển

Các command sau đang review trong Phase 6, **chưa phát hành lên PyPI**:

```sh
myfap courses --semester Fall2026 --stdout
myfap other subjects --semester Fall2026 --stdout
myfap other balance --stdout
myfap news --search "lịch thi" --type 1 --stdout
myfap transcript --stdout
myfap training --semester Fall2026 --stdout
myfap marks --summary --stdout
myfap info photo --stdout
myfap rating list --api-version v1 --stdout
myfap doctor --stdout
myfap doctor --api-version v2 --online --stdout
```

`marks --summary` không nhận kỳ học/courseid/pretty. Photo chỉ xuất JSON, không tự tải hoặc giải mã ảnh. Doctor mặc định không đọc session hoặc gọi mạng; `--online` chỉ probe bootstrap proxy v2, không xác nhận tài khoản đã đăng nhập. `rating list` chỉ hỗ trợ student/v1; v2 là stub và bị chặn. Khác với các lệnh đọc này, rating submit/push/feedback submit còn có gate riêng và chưa được mở.

## Thông tin thêm
- [Chọn API v1 hoặc v2](https://github.com/WindowScary321/myfap-api-cli/blob/main/docs/api-versions.md): v1 vẫn mặc định; v2 hỗ trợ các command đọc hiện có trong Phase 4.
- [Các ví dụ sử dụng](./docs/Example.md)
- [Tạo môi trường dev bằng uv](./docs/development.md)
- [CI và kiểm tra artifact](./docs/development.md#ci-và-kiểm-tra-artifact)

## Lưu ý
Khi thiếu `--semester`, cli chọn kỳ theo `startDate` gần đây. Với lịch tuần, `--date` quyết định năm nếu bạn không truyền `--year` <br>


## Các Options

Các option chung `--campus` (`-c`), `--config`, `--timeout` và `--api-version` có thể đặt trước hoặc sau command, kể cả giữa nhóm lệnh và lệnh con. Option của riêng từng command vẫn đặt sau command đó.

```sh
myfap --api-version v2 --campus HN schedule --ics
myfap schedule --ics --api-version v2 --campus HN
myfap info student --timeout 20 --stdout
```

Nếu khai báo cùng option ở nhiều cấp, giá trị ở lệnh con được ưu tiên; lặp trong cùng cấp thì dùng giá trị cuối.

|Option|Chú thích|
|:-|:-|
|--help|Hiển thị bảng Commands và Options|
|--config <đường dẫn>|Đường dẫn tới file cấu hình session tùy chỉnh (mặc định: ~/.myfap-api-cli/session.json)|
|--timeout <giây>|Timeout HTTP; ưu tiên hơn biến `MYFAP_TIMEOUT`|
|--api-version <v1 hoặc v2>|Chọn API; ưu tiên option, session, rồi v1. V2 hỗ trợ các command đọc hiện có trong Phase 4.|
|-c, --campus <cơ sở>|Mã cơ sở; ưu tiên option rồi session. APHL chỉ mặc định cho v1; v2 cần chọn campus nếu chưa có mã phù hợp trong session.|
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
|--timeout <giây>|Tăng hoặc giảm thời gian chờ dữ liệu gửi về từ server, có thể dùng biến môi trường ``MYFAP_TIMEOUT``|

## Ghi công
- Api đã dc reverse engineered từ [myFAP android](https://play.google.com/store/apps/details?id=com.fuct): phiên bản *2.0.6*, versionCode: *31*
- [JADX](https://github.com/skylot/jadx): decompile và unpack apk android
- [Hermes decomp](https://github.com/SymbioticSec/hermes-decomp): decompile index.android.bundle về js có thể đọc dc
- [Burp Suite Community Edition](https://portswigger.net/burp): bắt gói tin và phân tích động ứng dụng myFAP
- [Playwright](https://playwright.dev/): chịu trắch nhiệm chính trong quy trình login
- [Typer](https://typer.tiangolo.com/) & [Rich](https://rich.readthedocs.io/): nền tảng giao diện cli của repo này
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/): bóc tách và xử lý dữ liệu html
- [ics.py](https://icspy.readthedocs.io/): tạo và chuẩn hóa định dạng iCalendar giúp dễ dàng import vào các ứng dụng lịch
