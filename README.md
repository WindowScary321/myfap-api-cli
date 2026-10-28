# MyFAP API CLI

## Giới thiệu

Unofficial CLI tương tác với các API internal của ứng dụng myFAP giúp xem lịch học, lịch thi, điểm số (sự thất vọng của gia đình) và thông tin sinh viên

## Tính năng chính
- Hỗ trợ đa nền tảng
- Login thông qua FEID hoặc Google OAuth
- Xem lịch học (từng tuần hoặc cả Kỳ)
- Xem điểm (từng môn hoặc cả Kỳ)
- Check điểm danh (từng môn hoặc cả Kỳ)
- Check tình trạng đơn từ
- Xem thông báo của trường
- Check Info của sinh viên hoặc phòng dvsv
- Convert lịch học Kỳ sang **ICS**, dễ dàng import lịch học vào Google Calendar hoặc các dịch vụ tương tự
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

- Login vào myFAP api thông qua FEID
  ```
  myfap login --campus HN
  ```
  Sau khi hoàn thành login, phiên đăng nhập sẽ được lưu ở ``~/.myfap-api-cli/session.json``

- Login cho cơ sở Xavalo 
  ```
  myfap login -c HCM
  ```

- Lấy Lịch học *(tự động lấy kỳ mới nhất)*

  ```
  myfap schedule
  ```

## Danh sách các Command

| Command | Tác dụng |
|:--|:--|
| `version` | Hiển thị phiên bản CLI |
| `doctor` | Kiểm tra cấu hình; thêm `--online` để kiểm tra kết nối bootstrap v2. |
| `login` | Đăng nhập hoặc dùng session hiện có; thêm `--force` để đăng nhập lại |
| `logout` | Xóa session trên máy |
| `refresh` | Làm mới token và session |
| `campuses` | Liệt kê các cơ sở của API đang chọn |
| `semesters` | Liệt kê các kỳ học |
| `schedule` | Xem lịch học theo kỳ; dùng `--ics` để xuất lịch **ICS** |
| `week-timetable` | Xem lịch học theo tuần hoặc ngày |
| `exams` | Xem lịch thi; dùng `--ics` để xuất lịch, thêm `--full` để kèm thông tin phụ |
| `courses` | Xem danh sách khóa học theo kỳ |
| `marks` | Xem điểm theo kỳ, chi tiết theo môn hoặc tổng kết với `--summary` |
| `transcript` | Xem bảng điểm toàn khóa; `--pretty` phân tích dữ liệu bảng HTML sang JSON |
| `attendance` | Xem điểm danh theo kỳ hoặc theo môn và lớp |
| `applications` | Xem danh sách đơn đã gửi |
| `news` | Xem hoặc tìm kiếm tin tức |
| `info student` | Xem thông tin sinh viên |
| `info photo` | Lấy dữ liệu ảnh sinh viên ở dạng JSON |
| `info campus` | Xem thông tin phòng dịch vụ sinh viên |
| `other training` | Xem điểm phong trào theo kỳ |
| `other survey` | Kiểm tra khảo sát cần làm |
| `other feedback` | Kiểm tra feedback đang mở |
| `other feedbacks` | Xem danh sách feedback của sinh viên; chỉ hỗ trợ v2 |
| `other profile` | Kiểm tra yêu cầu cập nhật hồ sơ |
| `other notification` | Xem thông báo của sinh viên |
| `other fee` | Xem các khoản học phí và trạng thái thanh toán |
| `other balance` | Xem số dư tài khoản |
| `other subjects` | Xem danh sách môn; có thể lọc theo kỳ |
| `other rating list` | Xem danh sách đánh giá; chỉ hỗ trợ v1 |

## Biến môi trường
Gồm 2 biến mặc định
- ``MYFAP_TIMEOUT``: thay đổi thời gian timeout mặc định (mặc định: 10s), danh sách môn timeout 30s
- ``MYFAP_API_VER``: overide phiên bản api (mặc định: v2)

## Lưu ý
Khi thiếu `--semester`, cli chọn kỳ theo `startDate` gần đây. Với lịch tuần, `--date` quyết định năm nếu bạn không truyền `--year`

## Các Options
Ví dụ:
```sh
myfap --api-version v2 --campus HN schedule --ics
myfap schedule --ics --api-version v2 --campus HN
myfap info student --timeout 20 --stdout
```

Nếu khai báo cùng option ở nhiều cấp, giá trị ở lệnh con được ưu tiên; lặp trong cùng cấp thì dùng giá trị cuối

|Option|Chú thích|
|:-|:-|
|--help|Hiển thị bảng Commands và Options|
|--config <đường dẫn>|Đường dẫn tới file cấu hình session tùy chỉnh (mặc định: ~/.myfap-api-cli/session.json)|
|--timeout <giây>|Tăng hoặc giảm thời gian chờ dữ liệu gửi về từ server, có thể dùng biến môi trường ``MYFAP_TIMEOUT``|
|--api-version <v1 hoặc v2>|Chọn API; ưu tiên option, biến môi trường `MYFAP_API_VER`, version trong session, rồi mặc định v2. Session cũ thiếu version vẫn là v1|
|-c, --campus <cơ sở>|Mã cơ sở; ưu tiên option rồi session. APHL chỉ mặc định cho v1; v2 cần chọn campus nếu chưa có mã phù hợp trong session|
|-s, --semester <kỳ học>|Tên kỳ học (VD: ``Fall2026``)|
|-cid, --courseid <mã môn>|Chọn mã môn, chỉ có ở command ``marks``. (VD: 82934, lấy từ bảng điểm của kỳ, ko phải mã môn như PRO192, SWE201c, ...)|
|-w, --week <số tuần>|Chọn tuần, chỉ có ở command ``week-timetable``|
|-y, --year <số năm>|Chọn năm học, chỉ có ở command ``week-timetable``|
|-d, --date \<YYYY-MM-DD\>|Chỉ định ngày chính xác, chỉ có ở command ``week-timetable``|
|-sc, --subjectcode <mã môn>|Chọn môn học,  chỉ có ở command ``attendance``|
|-cn, --classname <mã lớp>|Chọn lớp học, chỉ có ở command ``attendance``|
|--ics|Convert Sang **ICS**, dễ dàng import lịch vào Google Calendar hoặc các dịch vụ tương tự, áp dụng cho command ``schedule`` (lịch học) và ``exams`` (lịch thi)|
|--full|Kèm toàn bộ thông tin phụ khi xuất ICS ở command ``exams``, mặc định xuất các thông tin quan trọng (môn, phòng thi, ngày công bố)|
|-p, --pretty|Format lại bảng điểm gốc của trường sang dạng json, chỉ có ở command ``marks`` và ``transcript``|
|--output, -o <thư mục>|Thư mục xuất file thay vì thư mục hiện tại|
|--stdout|In kết quả trực tiếp ra màn hình thay vì lưu file|
|-f, --force|Buộc đăng nhập lại, bỏ qua file ``session.json``, chỉ có ở command ``login``|


## Thông tin thêm
- [Chọn API v1 hoặc v2](./docs/api-versions.md): v2 là mặc định khi chưa có session; xem thứ tự ưu tiên và cách dùng v1
- [Các ví dụ sử dụng](./docs/Example.md)
- [Tạo môi trường dev bằng uv](./docs/development.md)
- [CI và kiểm tra artifact](./docs/development.md#ci-và-kiểm-tra-artifact)

## Ghi công
- Api đã dc reverse engineered từ [myFAP android](https://play.google.com/store/apps/details?id=com.fuct): phiên bản *2.0.6*, versionCode: *31*
- [JADX](https://github.com/skylot/jadx): decompile và unpack apk android
- [Hermes decomp](https://github.com/SymbioticSec/hermes-decomp): decompile index.android.bundle về js có thể đọc dc
- [Burp Suite Community Edition](https://portswigger.net/burp): bắt gói tin và phân tích động ứng dụng myFAP
- [Playwright](https://playwright.dev/): chịu trắch nhiệm chính trong quy trình login
- [Typer](https://typer.tiangolo.com/) & [Rich](https://rich.readthedocs.io/): nền tảng giao diện cli của repo này
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/): bóc tách và xử lý dữ liệu html
- [ics.py](https://icspy.readthedocs.io/): tạo và chuẩn hóa định dạng iCalendar giúp dễ dàng import vào các ứng dụng lịch

## Các model đã sử dụng
- [Gemini 3 Pro Preview](https://openrouter.ai/google/gemini-3-pro-preview): Hoàn thành phiên bản myFAP đầu tiên (trước v0.2.0), tích hợp API v1
- [GPT-6.1 Sol](https://openrouter.ai/openai/gpt-6.1-sol): Agent chính lên kế hoạch cho việc tích hợp API v2, viết testcase dành cho unittesting và viết script CI/CD 
- [Gemini 3.8 Flash](https://openrouter.ai/google/gemini-3.8-flash), [DeepSeek V4.1 Flash](https://openrouter.ai/deepseek/deepseek-v4.1-flash), [GLM 5.3 Flash](https://openrouter.ai/z-ai/glm-5.3-flash): Các subagent thực hiện code và test
