# Các ví dụ sử dụng

## Lưu ý
- Do hầu hết các command đểu trả về json, ``*`` đánh dấu những command trả output ra màn hình.
- Nếu ko thêm flag _thời gian_ hoặc _kỳ_, ``myfap`` sẽ tự động lấy thời gian mới nhất.
- ``+`` nghĩa là bạn sẽ ko cần thêm flag ``--semester`` hoặc ``-s`` nếu gọi api vào đúng thời gian trong kỳ. Để xem thông tin của kỳ trước, bạn phải thêm flag này.

### Xem tất cả command ``*``
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
    version         Hiển thị phiên bản MyFap API CLI
    login           Đăng nhập vào hệ thống FEID
    logout          Đăng xuất (Xóa session)
    refresh         Làm mới token (Refresh Token)
    campuses        Xem danh sách các cơ sở (Campus)
    semesters       Xem danh sách kỳ học
    schedule        Xem lịch học
    marks           Xem bảng điểm
    exams           Xem lịch thi
    week-timetable  Xem lịch học theo tuần
    attendance      Xem thông tin điểm danh
    applications    Xem danh sách đơn từ đã gửi cho trường
    news            Xem 10 thông báo gần nhất
    info            Xem thông tin chung (sinh viên, campus)
    other           Các chức năng phụ trợ khác (survey, feedback, fee...)
  ```
  
### Xem danh sách kỳ ``*``
  ```
  myfap semesters
  ```
### Xem lịch học của Kỳ bất kỳ 
  ```
  myfap schedule -s Summer2026
  ```
### Convert lịch học sang **ICS** (import vào GG Calendar) 
  ```
  myfap schedule -s Summer2026 --ics
  ```
### Xem lịch thi của Kỳ bất kỳ
  ```
  myfap exams -s Summer2026
  ```
### Xem lịch từng tuần được chỉ định ``+``
  ```
  myfap week-timetable --week 22
  ```
### Xem lịch từng tuần bằng thời gian ngày ``+``
  ```
  myfap week-timetable --date 2026-6-7
  ```
### Xem danh sách điểm danh của Kỳ bất kỳ
  ```
  myfap attendance -s Spring2026
  ```
### Xem danh sách điểm danh của môn bất kỳ trong Kỳ ``+``
  ```
  myfap attendance -sc CSD201 -cn SE2026 -s Spring2026
  ```
### Xem ~~sự thất vọng của gia đinh~~ điểm số của Kỳ bất kỳ
  ```
  myfap marks -s Fall2025
  ```
### Xem điểm của môn bất kỳ (ví dụ: môn MAD101, xem mã môn ở command trên)
  ```
  myfap marks -cid 95619
  ```
### Xem điểm của môn bất kỳ (thêm ``-p`` hoặc ``--pretty`` cho đẹp)
  ```
  myfap marks -cid 95619 -p
  ```
### Xem tình trạng gửi đơn của Fap Web
  ```
  myfap applications
  ```
### Xem thông báo gửi toàn trường
  ```
  myfap news
  ```
### Xem thông tin sinh viên
  ```
  myfap info student
  ```
### Xem thông tin phòng dvsv
  ```
  myfap info campus
  ```
### Xem thông tin thêm ``*``
  ```
  myfap other --help
  Usage: myfap other [OPTIONS] COMMAND [ARGS]...

  Các chức năng phụ trợ khác (survey, feedback, fee...)

  Options:
    --help  Show this message and exit.

  Commands:
    survey        Kiểm tra các survey chưa thực hiện
    feedback      Kiểm tra Feedback
    profile       Kiểm tra Update Profile
    notification  Xem thông báo qua MSSV
    fee           Lấy danh sách học phí chưa thanh toán
    subjects      Lấy danh sách tất cả môn học
  ```
### Refresh thủ công ``authen_key`` trong trường hợp cli bị lỗi
  ```
  myfap refresh
  ```
### Đăng nhập lại, bỏ qua file ``session.json``
  ```
  myfap login -f
  ```
### Trỏ vào file ``session.json`` vào vị trí tuỳ chỉnh
  ```
  myfap login --config "%appdata%\myfap-api-cli\session.json"
  ```