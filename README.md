# MyFAP API CLI

## Giới thiệu

Chào mứng đến với dự án đầu tiên của kế hoạch lật đổ FBTU. Cli này tương tác giống hoàn toàn với APP MYFAP trên điện thoại. Bạn có thể xem lịch học, lịch thi, điểm số (sự thất vọng của gia đình), thông tin cá nhân, v.v. 1 cách thuận tiện, không bị gò bó trong giao diện app. <br>
- Lưu ý: repo này được thực hiện cùng với sự hỗ trợ của Ai (Gemini 3.1 Pro Preview)

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

Do dự án đang trong quá trình phát triển nên chưa thể đem lên pip. Bạn có thể tải sauce về và chạy:

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

- Lấy Lịch học (tự động lấy kỳ mới nhất).

  ```
  myfap schedule
  ```

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
|-r, --refresh|Refresh thủ công ``authen_key`` trong file ``session.json``, chỉ có ở command ``login``|
|-f, --force|Buộc đăng nhập lại, bỏ qua file ``session.json``, chỉ có ở command ``login``|

## Các ví dụ sử dụng
- Lưu ý: 
    - Do hầu hết các command đểu trả về json, ``*`` đánh dấu những command trả output ra màn hình.
    - Nếu ko thêm flag _thời gian_ hoặc _kỳ_, ``myfap`` sẽ tự động lấy thời gian mới nhất.
    - ``+`` nghĩa là bạn sẽ ko cần thêm flag ``--semester`` hoặc ``-s`` nếu gọi api vào đúng thời gian trong kỳ. Để xem thông tin của kỳ trước, bạn phải thêm flag này.
- Xem tất cả command ``*``
  ```
  myfap --help  
  Usage: myfap [OPTIONS] COMMAND [ARGS]...

    CLI Tool dựa trên MyFAP dành cho Sinh Viên FPTU

  Options:
    -c, --campus TEXT  Mã cơ sở (VD: APHL, HCM, DN)  [default: APHL]
    --config TEXT      Đường dẫn file session tùy chỉnh (thay vì mặc định
                      ~/.myfap-api-cli/session.json)
    --help             Show this message and exit.

  Commands:
    login           Đăng nhập vào hệ thống FEID
    campuses        Xem danh sách các cơ sở (Campus)
    semesters       Xem danh sách kỳ học
    schedule        Xem lịch học (xuất JSON)
    marks           Xem bảng điểm (xuất JSON)
    exams           Xem lịch thi (xuất JSON)
    week-timetable  Xem lịch học theo tuần (xuất JSON)
    attendance      Xem thông tin điểm danh (xuất JSON)
    applications    Xem danh sách đơn từ đã gửi cho trường (xuất JSON)
    news            Xem 10 thông báo gần nhất (xuất JSON)
    info            Xem thông tin chung (sinh viên, campus)
    other           Các chức năng phụ trợ khác (survey, feedback, fee...)
- Xem danh sách kỳ ``*``
  ```
  myfap semesters
  ```
- Xem lịch học của Kỳ bất kỳ 
  ```
  myfap schedule -s Summer2026
  ```
- Convert lịch học sang **ICS** (import vào GG Calendar) 
  ```
  myfap schedule -s Summer2026 --ics
  ```
- Xem lịch thi của Kỳ bất kỳ
  ```
  myfap exams -s Summer2026
  ```
- Xem lịch từng tuần được chỉ định ``+``
  ```
  myfap week-timetable --week 22
  ```
- Xem lịch từng tuần bằng thời gian ngày ``+``
  ```
  myfap week-timetable --date 2026-6-7
  ```
- Xem danh sách điểm danh của Kỳ bất kỳ
  ```
  myfap attendance -s Spring2026
  ```
- Xem danh sách điểm danh của môn bất kỳ trong Kỳ ``+``
  ```
  myfap attendance -sc CSD201 -cn SE2026 -s Spring2026
  ```
- Xem ~~sự thất vọng của gia đinh~~ điểm số của Kỳ bất kỳ
  ```
  myfap marks -s Fall2025
  ```
- Xem điểm của môn bất kỳ (ví dụ: môn MAD101, xem mã môn ở command trên)
  ```
  myfap marks -cid 95619
  ```
- Xem điểm của môn bất kỳ (thêm ``-p`` hoặc ``--pretty`` cho đẹp)
  ```
  myfap marks -cid 95619 -p
  ```
- Xem tình trạng gửi đơn của Fap Web
  ```
  myfap applications
  ```
- Xem thông báo gửi toàn trường
  ```
  myfap news
  ```
- Xem thông tin sinh viên
  ```
  myfap info student
  ```
- Xem thông tin phòng dvsv
  ```
  myfap info campus
  ```
- Xem thông tin thêm ``*``
  ```bash
  myfap other --help
  Usage: myfap other [OPTIONS] COMMAND [ARGS]...

  Các chức năng phụ trợ khác (survey, feedback, fee...)

  Options:
    --help  Show this message and exit.

  Commands:
    survey        Kiểm tra các survey chưa thực hiện (xuất JSON)
    feedback      Kiểm tra Feedback (xuất JSON)
    profile       Kiểm tra Update Profile (xuất JSON)
    notification  Xem thông báo qua MSSV (xuất JSON)
    fee           Lấy danh sách học phí chưa thanh toán (xuất JSON)
  ```
- Refresh thủ công ``authen_key`` trong trường hợp cli bị lỗi
  ```
  myfap login -r
  ```
- Đăng nhập lại, bỏ qua file ``session.json``
  ```
  myfap login -f
  ```
- Trỏ vào file ``session.json`` vào vị trí tuỳ chỉnh
  ```
  myfap login --config "%appdata%\myfap-api-cli\session.json"
  ```