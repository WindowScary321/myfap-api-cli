from bs4 import BeautifulSoup
import re

def _rowspan_rows(value):
    # rowspan rác từ server (VD "2.0", rỗng) coi như 1 để không crash parser.
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 1


def parse_marks_html(html_str: str):
    """Phân tích chuỗi HTML bảng điểm thành danh sách các đối tượng JSON (dict)"""
    soup = BeautifulSoup(html_str, 'html.parser')
    table = soup.find('table')
    if not table:
        return []

    result = []
    current_category = ""
    category_rows_remaining = 0
    # Header phân biệt ba cột điểm với hàng category/item/value cũ.
    data_only_header = False
    
    for tr in table.find_all('tr'):
        # Bỏ qua dòng tiêu đề chứa thẻ th
        if tr.find('th'):
            headers = [th.get_text(strip=True).casefold() for th in tr.find_all('th')]
            data_only_header = headers == ["item", "weight", "value"]
            continue
            
        tds = tr.find_all('td')
        if not tds:
            continue
            
        td_texts = [td.get_text(strip=True) for td in tds]
        
        # Nhận diện dòng có category mới (td đầu tiên có rowspan)
        if len(tds) >= 3 and tds[0].has_attr('rowspan'):
            current_category = td_texts[0]
            category_rows_remaining = _rowspan_rows(tds[0]['rowspan']) - 1
            data_tds = td_texts[1:]
        elif len(tds) >= 2 and tds[0].has_attr('colspan') and current_category:
            # Giữ cấu trúc output của dòng tổng kết hiện có.
            category_rows_remaining = 0
            data_tds = td_texts
        elif len(tds) >= 2 and category_rows_remaining > 0:
            # Dòng tiếp theo thuộc cùng category
            data_tds = td_texts
            category_rows_remaining -= 1
        elif len(tds) == 3 and data_only_header:
            data_tds = td_texts
        else:
            # Fallback
            current_category = td_texts[0] if len(td_texts) > 0 else ""
            data_tds = td_texts[1:] if len(td_texts) > 1 else []

        row_data = {
            "category": current_category,
        }
        
        # Map các cột dữ liệu theo cấu trúc của FAP
        if len(data_tds) >= 3:
            row_data.update({
                "item": data_tds[0],
                "weight": data_tds[1],
                "value": data_tds[2],
            })
            if len(data_tds) >= 4:
                row_data["comment"] = data_tds[3]
        elif len(data_tds) == 2:
            row_data.update({
                "item": data_tds[0],
                "value": data_tds[1]
            })
        elif len(data_tds) == 1:
            row_data.update({
                "item": data_tds[0]
            })
            
        result.append(row_data)

    return result

def parse_transcript_html(html_str: str):
    """Phân tích chuỗi HTML bảng điểm toàn khóa: mỗi bảng giữ header riêng và hàng dữ liệu keyed theo header."""
    def cell_text(node):
        # &nbsp; giải mã thành \xa0; chuẩn hoá thành space thường để JSON sạch.
        return node.get_text().replace('\xa0', ' ').strip()

    soup = BeautifulSoup(html_str, 'html.parser')
    tables = []
    for table in soup.find_all('table'):
        headers = []
        rows = []
        for tr in table.find_all('tr'):
            if tr.find('th'):
                headers = [cell_text(th) for th in tr.find_all('th')]
                continue
            tds = tr.find_all('td')
            if not tds or not headers:
                continue
            row = {}
            for index, td in enumerate(tds):
                key = headers[index] if index < len(headers) else f"Column{index + 1}"
                row[key] = cell_text(td)
            rows.append(row)
        if headers or rows:
            tables.append({"headers": headers, "rows": rows})
    return tables


def convert_exams_to_ics(data: dict, full: bool = False) -> str:
    """Chuyển dữ liệu lịch thi JSON thành chuỗi ICS.

    Mặc định (full=False) chỉ đưa thông tin quan trọng (Môn, Ngày công bố);
    ẩn mã slot UUID, phòng thi, ghi chú và các trường phụ.
    Khi full=True đưa toàn bộ thông tin phụ vào sự kiện lịch.
    """
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise ValueError("Invalid JSON format")

    c = Calendar()
    tz = pytz.timezone("Asia/Ho_Chi_Minh")

    for exam in data["data"]:
        if (not isinstance(exam, dict)
                or any(not isinstance(exam.get(field), str) or not exam[field].strip()
                       for field in ("date", "time", "subjectCode"))):
            raise ValueError("Invalid exam: date, time and subjectCode are required")
        try:
            day = datetime.strptime(exam["date"].split("T")[0].strip(), "%Y-%m-%d")
            normalized = exam["time"].strip().strip("()").replace(" ", "")
            match = re.fullmatch(r"(\d{1,2})h(\d{2})-(\d{1,2})h(\d{2})", normalized)
            if match is None:
                raise ValueError
            start_dt = tz.localize(datetime.strptime(
                f"{day:%Y-%m-%d} {match.group(1)}:{match.group(2)}", "%Y-%m-%d %H:%M"))
            end_dt = tz.localize(datetime.strptime(
                f"{day:%Y-%m-%d} {match.group(3)}:{match.group(4)}", "%Y-%m-%d %H:%M"))
        except ValueError:
            raise ValueError(
                "Invalid exam: date hoặc time không hợp lệ (date dạng YYYY-MM-DD, time dạng 7h30-9h50).") from None
        # Kỳ thi kết thúc trước giờ bắt đầu nghĩa là vượt nửa đêm: kết thúc sang ngày hôm sau.
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)

        e = Event(created=datetime.now(timezone.utc))
        title = exam["subjectCode"]
        kythi = exam.get("kythi")
        if isinstance(kythi, str) and kythi.strip():
            title += f" ({kythi.strip()})"
        e.name = title
        e.begin = start_dt
        e.end = end_dt

        if full:
            e.location = exam.get("roomNo") or ""
            fields_to_add = (
                ("Môn", "subjectName"),
                ("Ngày công bố", "dateofPublication"),
                ("Phòng", "roomNo"),
                ("Mã slot", "slot"),
                ("Ghi chú", "note"),
                ("Ghi chú điểm danh", "note_Attendance"),
                ("Đã tốt nghiệp", "isGraduated"),
            )
        else:
            e.location = ""
            fields_to_add = (
                ("Môn", "subjectName"),
                ("Ngày công bố", "dateofPublication"),
            )

        desc = []
        for label, field in fields_to_add:
            value = exam.get(field)
            if value is None:
                continue
            if isinstance(value, bool):
                desc.append(f"{label}: {'Có' if value else 'Không'}")
            elif isinstance(value, str) and value.strip():
                clean_val = value.strip().replace("T00:00:00", "")
                desc.append(f"{label}: {clean_val}")
        e.description = "\n".join(desc)

        c.events.add(e)

    # Trả về chuỗi ICS
    return "".join(c.serialize_iter())


from datetime import datetime, timedelta, timezone
import pytz
from ics import Calendar, Event

def convert_schedule_to_ics(data: dict) -> str:
    """Chuyển đổi dữ liệu lịch học JSON thành chuỗi ICS"""
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise ValueError("Invalid JSON format")

    c = Calendar()
    tz = pytz.timezone("Asia/Ho_Chi_Minh")

    for session in data["data"]:
        if not isinstance(session, dict) or any(
            not isinstance(session.get(field), str) or not session[field].strip()
            for field in ("date", "slotTime", "subjectCode")
        ):
            raise ValueError("Invalid schedule session: date, slotTime and subjectCode are required")
        # Parse date: "5/11/2026 12:00:00 AM" -> "5/11/2026"
        date_str = session["date"].split(" ")[0]
        
        # Parse time: "(7:30-9:50)" -> "7:30", "9:50"
        time_str = session["slotTime"].strip().strip("()").strip()
        try:
            start_time_str, end_time_str = (part.strip() for part in time_str.split("-", 1))
        except ValueError:
            raise ValueError("slotTime phải có dạng (giờ bắt đầu-giờ kết thúc), ví dụ (7:30-9:50).") from None

        # Parse full datetime
        start_dt = tz.localize(datetime.strptime(f"{date_str} {start_time_str}", "%m/%d/%Y %H:%M"))
        end_dt = tz.localize(datetime.strptime(f"{date_str} {end_time_str}", "%m/%d/%Y %H:%M"))
        # Slot kết thúc trước giờ bắt đầu nghĩa là vượt nửa đêm: kết thúc sang ngày hôm sau.
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)
        
        # Create event
        e = Event(created=datetime.now(timezone.utc))
        
        # Title
        title = session['subjectCode']
        is_online = session.get("isOnline")
        if is_online is True or is_online == "True":
            title += " (Online)"
        e.name = title
        
        e.begin = start_dt
        e.end = end_dt
        
        # Location
        e.location = session.get("roomNo", "")
        
        # Description
        desc = []
        desc.append(f"Group: {session.get('groupName', '')}")
        desc.append(f"Session: {session.get('sessionNo', '')}")
        desc.append(f"Lecturer: {session.get('lecturer', 'N/A')}")
        desc.append(f"Room: {session.get('roomNo', '')}")
        if session.get("meetURL"):
            desc.append(f"Meet URL: {session.get('meetURL')}")
            
        e.description = "\n".join(desc)
        
        c.events.add(e)

    # Trả về chuỗi ICS
    return "".join(c.serialize_iter())
