from bs4 import BeautifulSoup

def parse_marks_html(html_str: str):
    """Phân tích chuỗi HTML bảng điểm thành danh sách các đối tượng JSON (dict)"""
    soup = BeautifulSoup(html_str, 'html.parser')
    table = soup.find('table')
    if not table:
        return []

    result = []
    current_category = ""
    
    for tr in table.find_all('tr'):
        # Bỏ qua dòng tiêu đề chứa thẻ th
        if tr.find('th'):
            continue
            
        tds = tr.find_all('td')
        if not tds:
            continue
            
        td_texts = [td.get_text(strip=True) for td in tds]
        
        # Nhận diện dòng có category mới (td đầu tiên có rowspan)
        if len(tds) >= 3 and tds[0].has_attr('rowspan'):
            current_category = td_texts[0]
            data_tds = td_texts[1:]
        elif len(tds) >= 2 and not tds[0].has_attr('rowspan') and current_category != "":
            # Dòng tiếp theo thuộc cùng category
            data_tds = td_texts
        else:
            # Fallback
            current_category = td_texts[0] if len(td_texts) > 0 else ""
            data_tds = td_texts[1:] if len(td_texts) > 1 else []

        row_data = {
            "category": current_category,
        }
        
        # Map các cột dữ liệu theo cấu trúc của FAP
        if len(data_tds) >= 4:
            row_data.update({
                "item": data_tds[0],
                "weight": data_tds[1],
                "value": data_tds[2],
                "comment": data_tds[3]
            })
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

import json
from datetime import datetime
from zoneinfo import ZoneInfo
from ics import Calendar, Event

def convert_schedule_to_ics(data: dict) -> str:
    """Chuyển đổi dữ liệu lịch học JSON thành chuỗi ICS"""
    if "data" not in data or not isinstance(data["data"], list):
        raise ValueError("Invalid JSON format")

    c = Calendar()
    tz = ZoneInfo("Asia/Ho_Chi_Minh")

    for session in data["data"]:
        # Parse date: "5/11/2026 12:00:00 AM" -> "5/11/2026"
        date_str = session["date"].split(" ")[0]
        
        # Parse time: "(7:30-9:50)" -> "7:30", "9:50"
        time_str = session["slotTime"].strip("()")
        start_time_str, end_time_str = time_str.split("-")
        
        # Parse full datetime
        start_dt = datetime.strptime(f"{date_str} {start_time_str}", "%m/%d/%Y %H:%M").replace(tzinfo=tz)
        end_dt = datetime.strptime(f"{date_str} {end_time_str}", "%m/%d/%Y %H:%M").replace(tzinfo=tz)
        
        # Create event
        e = Event()
        
        # Title
        title = session['subjectCode']
        if session.get("isOnline") == "True":
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
