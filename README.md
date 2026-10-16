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

Bạn có thể cài ứng dụng bằng pip theo hướng dẫn bên dưới. Để phát triển từ mã nguồn, xem [tài liệu phát triển](https://github.com/WindowScary321/myfap-api-cli/blob/main/docs/development.md).

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

## Tài liệu phát triển

- [Phát triển với uv](https://github.com/WindowScary321/myfap-api-cli/blob/main/docs/development.md#phát-triển-với-uv): tạo môi trường dev, chạy CLI và cập nhật dependency.
- [CI và kiểm tra artifact](https://github.com/WindowScary321/myfap-api-cli/blob/main/docs/development.md#ci-và-kiểm-tra-artifact): phạm vi kiểm tra, build wheel/sdist và smoke test bằng pip.

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

Với `--stdout`, bạn nhận JSON hoặc ICS trên stdout; log và lỗi đi qua stderr. Khi thiếu `--semester`, CLI chọn kỳ theo `startDate` mới nhất. Với lịch tuần, `--date` quyết định năm nếu bạn không truyền `--year`.
