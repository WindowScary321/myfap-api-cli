# Các ví dụ sử dụng

## Lưu ý
- Do hầu hết các command đểu trả về json, ``*`` đánh dấu những command trả output ra màn hình.
- Khi thiếu `--semester`, CLI chọn kỳ có `startDate` mới nhất. Nếu ngày bị thiếu hoặc sai định dạng, bạn cần chỉ định kỳ bằng `--semester` hoặc `-s`.
- Với `week-timetable`, năm được chọn theo `--year`, rồi năm trong `--date`, sau cùng là năm hiện tại. `--week` ưu tiên hơn việc tra số tuần từ ngày.
- Dấu `+` đánh dấu command có thể tự chọn kỳ. Để xem kỳ trước, bạn cần truyền `--semester` hoặc `-s`.

### Xem tất cả command ``*``
  ```
  myfap --help  
  Usage: myfap [OPTIONS] COMMAND [ARGS]...

    CLI Tool dựa trên MyFAP dành cho Sinh Viên FPTU

  Options:
    -c, --campus TEXT  Mã cơ sở; dùng session, APHL chỉ mặc định cho v1
    --config TEXT      Đường dẫn file session tùy chỉnh (thay vì mặc định
                      ~/.myfap-api-cli/session.json)
    --timeout SECONDS  Timeout HTTP theo giây; ưu tiên hơn MYFAP_TIMEOUT
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

### Điều chỉnh timeout HTTP

Bạn có thể đặt `--timeout` trước hoặc sau command, kể cả khi gọi nhóm `other` hoặc `info`:

```sh
myfap --timeout 20 schedule --stdout
myfap --timeout 2.5 campuses
myfap --timeout 45 other subjects --stdout
myfap schedule --stdout --timeout 20
myfap info student --timeout 20 --stdout
```

Để dùng chung cho nhiều lệnh trong PowerShell:

```powershell
$env:MYFAP_TIMEOUT = "20"
myfap schedule --stdout
myfap --timeout 40 other subjects --stdout
Remove-Item Env:MYFAP_TIMEOUT
```

Thứ tự ưu tiên là `--timeout` → `MYFAP_TIMEOUT` → mặc định. Cả hai cách nhận số giây hữu hạn lớn hơn 0, gồm số thập phân. Giá trị sai trả lỗi qua stderr trước khi gọi HTTP; option hợp lệ vẫn dùng được khi biến môi trường sai.

| Request | Khi không cấu hình | Khi có option hoặc biến môi trường |
|---|---|---|
| Dữ liệu FAP và survey | 10 giây | Giá trị đã chọn |
| Danh sách môn `other subjects` | 30 giây | Giá trị đã chọn, tối thiểu 30 giây |
| Discovery/JWKS, lấy token và handshake FEID/FAP | 10 giây | Giá trị đã chọn |

Trước đây biến môi trường chỉ áp dụng cho request dữ liệu; nay cả biến môi trường và option đều áp dụng cho HTTP ở bước xác thực. Theo cách xử lý của Requests, timeout giới hạn chờ kết nối và chờ dữ liệu giữa các lần đọc, không giới hạn tổng thời gian chạy command. Thời gian chờ đăng nhập trên trình duyệt vẫn là 120 giây.
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
  myfap week-timetable --date 2026-06-07
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
    fee           Lấy danh sách học phí và trạng thái thanh toán từng khoản
    subjects      Lấy danh sách tất cả môn học
  ```
### Refresh thủ công ``authen_key`` trong trường hợp cli bị lỗi
  ```
  myfap refresh
  ```

### Xuất JSON hoặc ICS qua stdout

Bạn có thể chuyển output vào file hoặc pipe sang công cụ khác. Log và lỗi đi qua stderr; lỗi trả exit code khác 0.

```sh
myfap schedule --stdout > schedule.json
myfap schedule --ics --stdout > schedule.ics
```

`other fee` giữ mọi dòng server trả về, gồm `IsPaid`, số tiền và thông tin hóa đơn. HTTP 404 là lỗi API, không có nghĩa là tài khoản không nợ. `other survey` giữ nguyên body `code: "404"`, `message: "Data Not Found"`, `data: null` khi server trả HTTP 200; trạng thái này chưa xác nhận còn hay hết survey bắt buộc.

### Đăng nhập lại bằng trình duyệt
  ```
  myfap login -f
  ```

Session chỉ được thay sau khi đăng nhập và handshake thành công. Xem [quy tắc session và refresh](oauth-session.md) trước khi dùng lại session từ phiên bản cũ.
### Trỏ vào file ``session.json`` vào vị trí tùy chỉnh
  ```
  myfap --config "%appdata%\myfap-api-cli\session.json" login
  ```
