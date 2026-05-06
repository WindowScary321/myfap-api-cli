import requests
import html
from .auth import FAP_HOST, MAGIC_ID, create_checksum

def check_api_error(data):
    if isinstance(data, dict):
        code = str(data.get("code", ""))
        if code == "201":
            msg = data.get("message", "Lỗi API (Mã 201)")
            raise Exception(f"FAP API báo lỗi: {msg}")
        if "data" in data and not data.get("data"): # Báo lỗi nếu data rỗng hoặc null
            raise Exception("Không có dữ liệu (Data rỗng) hoặc bạn chưa hoặc truyền sai flag --semester")
    return data

def clean_json(data):
    """Giải mã các ký tự HTML Entity (&ocirc;, &aacute;, ...) do server ASP.NET trả về"""
    if isinstance(data, dict):
        return {k: clean_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_json(v) for v in data]
    elif isinstance(data, str):
        return html.unescape(data)
    return data


class MyFapEssential:
    def __init__(self, auth=None):
        self.auth = auth
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "okhttp/4.9.2"})

    def get_campuses(self):
        """Lấy danh sách các cơ sở (không cần authenKey)"""
        url = f"{FAP_HOST}/GetAllActiveCampus"
        r = self.session.get(url)
        if r.status_code == 200:
            return clean_json(check_api_error(r.json())).get('data', [])
        return []

    def get_semesters(self, campus: str = None):
        """Lấy danh sách các kỳ học. Yêu cầu đối tượng auth hợp lệ."""
        if not self.auth:
            raise Exception("Lỗi: Cần đối tượng auth để lấy danh sách kỳ học.")
            
        target_campus = campus or self.auth.campus
        checksum = create_checksum(MAGIC_ID, target_campus)
        url = f"{FAP_HOST}/GetSemester?campusCode={target_campus}&Authen={self.auth.authen_key}&checksum={checksum}"
        r = self.session.get(url)
        if r.status_code == 200:
            semesters = check_api_error(r.json()).get('data', [])
            semesters.sort(key=lambda x: x['termID'], reverse=True)
            return semesters
        raise Exception(f"Lỗi lấy danh sách kỳ học: {r.text}")

    def get_week(self, date_str: str):
        """Lấy số tuần tương ứng với ngày (YYYY-MM-DD)"""
        url = f"{FAP_HOST}/GetWeekByDate?date={date_str}"
        r = self.session.get(url)
        if r.status_code == 200:
            return int(check_api_error(r.json()).get("data", 0))
        raise Exception(f"Lỗi lấy tuần: {r.text}")

    def get_news(self, news_type: int = 1):
        """Lấy 10 thông báo gần nhất (gửi toàn trường)"""
        if not self.auth:
            raise Exception("Lỗi: Không tìm thấy session xác thực (auth).")
        # Identifier cho API này chính là giá trị của 'type'
        checksum = create_checksum(str(news_type), self.auth.campus)
        url = f"{FAP_HOST}/GetTop10News?campusCode={self.auth.campus}&Authen={self.auth.authen_key}&type={news_type}&checksum={checksum}"
        r = self.session.get(url)
        if r.status_code == 200:
            return clean_json(check_api_error(r.json()))
        raise Exception(f"Lỗi lấy thông báo: {r.text}")

class MyFapOther:
    def __init__(self, auth):
        self.auth = auth
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "okhttp/4.9.2"})

    def get_required_survey(self):
        """Lấy các survey chưa thực hiện"""
        if not getattr(self.auth, 'email', None):
            raise Exception("Lỗi: Không tìm thấy email trong session. Vui lòng chạy 'myfap login' lại để lấy thông tin.")
        # Identifier cho API này là email (username)
        checksum = create_checksum(self.auth.email, self.auth.campus)
        url = f"https://survey.fpt.edu.vn/API/myFAP/GetRequiredSurvey?username={self.auth.email}&checksum={checksum}"
        r = self.session.get(url)
        if r.status_code == 200:
            return clean_json(check_api_error(r.json()))
        raise Exception(f"Lỗi lấy Survey: {r.text}")

    def check_open_feedback(self):
        """Kiểm tra Feedback"""
        checksum = create_checksum(self.auth.mssv, self.auth.campus)
        url = f"{FAP_HOST}/CheckOpenFeedBack?campusCode={self.auth.campus}&rollNumber={self.auth.mssv}&Authen={self.auth.authen_key}&checksum={checksum}"
        r = self.session.get(url)
        if r.status_code == 200:
            return clean_json(check_api_error(r.json()))
        raise Exception(f"Lỗi lấy Feedback: {r.text}")

    def check_update_profile(self):
        """Kiểm tra Update Profile"""
        checksum = create_checksum(self.auth.mssv, self.auth.campus)
        url = f"{FAP_HOST}/CheckUpdateProfile?campusCode={self.auth.campus}&rollNumber={self.auth.mssv}&Authen={self.auth.authen_key}&checksum={checksum}"
        r = self.session.get(url)
        if r.status_code == 200:
            return clean_json(check_api_error(r.json()))
        raise Exception(f"Lỗi lấy Update Profile: {r.text}")

    def get_notification(self):
        """Lấy thông báo qua MSSV"""
        checksum = create_checksum(self.auth.mssv, self.auth.campus)
        url = f"{FAP_HOST}/GetNotificationByRoll?campusCode={self.auth.campus}&rollNumber={self.auth.mssv}&Authen={self.auth.authen_key}&checksum={checksum}"
        r = self.session.get(url)
        if r.status_code == 200:
            return clean_json(check_api_error(r.json()))
        raise Exception(f"Lỗi lấy Notification: {r.text}")

    def get_fee(self):
        """Lấy danh sách học phí chưa thanh toán"""
        checksum = create_checksum(self.auth.mssv, self.auth.campus)
        url = f"{FAP_HOST}/GetFeeByRoll?campusCode={self.auth.campus}&rollNumber={self.auth.mssv}&Authen={self.auth.authen_key}&checksum={checksum}"
        r = self.session.get(url)
        if r.status_code == 200:
            return clean_json(check_api_error(r.json()))
        if r.status_code == 404:
            return {"status": "Không có khoản nợ học phí nào cần thanh toán."}
        raise Exception(f"Lỗi lấy Fee: {r.text}")

class MyFapClient:
    def __init__(self, auth):
        self.auth = auth
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "okhttp/4.9.2"})

    def get_schedule(self, semester: str):
        """Lấy lịch học theo kỳ"""
        checksum = create_checksum(self.auth.mssv, self.auth.campus)
        url = f"{FAP_HOST}/GetActivityStudent?campusCode={self.auth.campus}&rollNumber={self.auth.mssv}&Semester={semester}&Authen={self.auth.authen_key}&checksum={checksum}"
        r = self.session.get(url)
        if r.status_code == 200:
            return clean_json(check_api_error(r.json()))
        raise Exception(f"Lỗi lấy lịch học: {r.text}")

    def get_marks(self, semester: str):
        """Lấy bảng điểm theo kỳ"""
        checksum = create_checksum(self.auth.mssv, self.auth.campus)
        url = f"{FAP_HOST}/GetStudentMark?campusCode={self.auth.campus}&rollNumber={self.auth.mssv}&Semester={semester}&Authen={self.auth.authen_key}&checksum={checksum}"
        r = self.session.get(url)
        if r.status_code == 200:
            return clean_json(check_api_error(r.json()))
        raise Exception(f"Lỗi lấy bảng điểm: {r.text}")

    def get_mark_by_course(self, course_id: str):
        """Lấy điểm chi tiết của một môn học"""
        checksum = create_checksum(self.auth.mssv, self.auth.campus)
        url = f"{FAP_HOST}/GetMarkByCourse?campusCode={self.auth.campus}&CourseId={course_id}&rollNumber={self.auth.mssv}&Authen={self.auth.authen_key}&checksum={checksum}"
        r = self.session.get(url)
        if r.status_code == 200:
            return clean_json(check_api_error(r.json()))
        raise Exception(f"Lỗi lấy điểm môn học: {r.text}")

    def get_exams(self, semester: str):
        """Lấy lịch thi theo kỳ"""
        checksum = create_checksum(self.auth.mssv, self.auth.campus)
        url = f"{FAP_HOST}/GetScheduleExam?campusCode={self.auth.campus}&rollNumber={self.auth.mssv}&Authen={self.auth.authen_key}&checksum={checksum}&Semester={semester}"
        r = self.session.get(url)
        if r.status_code == 200:
            return clean_json(check_api_error(r.json()))
        raise Exception(f"Lỗi lấy lịch thi: {r.text}")

    def get_schedule_by_week(self, week: int, semester: str, year: int):
        """Lấy lịch học theo tuần"""
        checksum = create_checksum(self.auth.mssv, self.auth.campus)
        url = f"{FAP_HOST}/GetActivityStudentByWeek?campusCode={self.auth.campus}&week={week}&rollNumber={self.auth.mssv}&Semester={semester}&year={year}&Authen={self.auth.authen_key}&checksum={checksum}"
        r = self.session.get(url)
        if r.status_code == 200:
            return clean_json(check_api_error(r.json()))
        raise Exception(f"Lỗi lấy lịch học tuần: {r.text}")

    def get_attendances(self, semester: str):
        """Lấy danh sách trạng thái điểm danh tổng quát của kỳ"""
        checksum = create_checksum(self.auth.mssv, self.auth.campus)
        url = f"{FAP_HOST}/GetStudentAttendances?campusCode={self.auth.campus}&Semester={semester}&rollNumber={self.auth.mssv}&Authen={self.auth.authen_key}&checksum={checksum}"
        r = self.session.get(url)
        if r.status_code == 200:
            return clean_json(check_api_error(r.json()))
        raise Exception(f"Lỗi lấy trạng thái điểm danh: {r.text}")

    def get_course_attendance(self, semester: str, subject_code: str, class_name: str):
        """Lấy chi tiết điểm danh của một môn học"""
        checksum = create_checksum(self.auth.mssv, self.auth.campus)
        url = f"{FAP_HOST}/getCourseAttendance?campusCode={self.auth.campus}&rollNumber={self.auth.mssv}&Semester={semester}&SubjectCode={subject_code}&ClassName={class_name}&Authen={self.auth.authen_key}&checksum={checksum}"
        r = self.session.get(url)
        if r.status_code == 200:
            return clean_json(check_api_error(r.json()))
        raise Exception(f"Lỗi lấy chi tiết điểm danh môn học: {r.text}")

    def get_applications(self):
        """Lấy danh sách các đơn từ đã gửi cho trường"""
        checksum = create_checksum(self.auth.mssv, self.auth.campus)
        url = f"{FAP_HOST}/GetApplication?campusCode={self.auth.campus}&rollNumber={self.auth.mssv}&Authen={self.auth.authen_key}&checksum={checksum}"
        r = self.session.get(url)
        if r.status_code == 200:
            return clean_json(check_api_error(r.json()))
        raise Exception(f"Lỗi lấy danh sách đơn từ: {r.text}")

    def get_student_info(self):
        """Lấy thông tin sinh viên"""
        checksum = create_checksum(self.auth.mssv, self.auth.campus)
        url = f"{FAP_HOST}/GetStudentById?campusCode={self.auth.campus}&rollNumber={self.auth.mssv}&Authen={self.auth.authen_key}&checksum={checksum}"
        r = self.session.get(url)
        if r.status_code == 200:
            return clean_json(check_api_error(r.json()))
        raise Exception(f"Lỗi lấy thông tin sinh viên: {r.text}")

    def get_campus_info(self):
        """Lấy thông tin phòng Dịch vụ sinh viên"""
        checksum = create_checksum(self.auth.mssv, self.auth.campus)
        url = f"{FAP_HOST}/GetCampusInfo?campusCode={self.auth.campus}&rollNumber={self.auth.mssv}&Authen={self.auth.authen_key}&checksum={checksum}"
        r = self.session.get(url)
        if r.status_code == 200:
            return clean_json(check_api_error(r.json()))
        raise Exception(f"Lỗi lấy thông tin campus: {r.text}")

