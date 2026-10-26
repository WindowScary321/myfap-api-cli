import json
import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from icalendar import Calendar as IndependentCalendar
from ics import Calendar

from myfap.cli import save_output
from myfap.parsers import convert_schedule_to_ics, parse_marks_html


FIXTURES = Path(__file__).parent / "fixtures"


class MarksParserTests(unittest.TestCase):
    def test_category_stops_at_the_end_of_rowspan(self):
        html = (FIXTURES / "marks_rowspan.html").read_text(encoding="utf-8")

        self.assertEqual(parse_marks_html(html), [
            {"category": "Quiz", "item": "Q1", "weight": "10%", "value": "8", "comment": ""},
            {"category": "Quiz", "item": "Q2", "weight": "10%", "value": "7", "comment": "Completed"},
            {"category": "Final", "item": "FE", "weight": "80%", "value": "6", "comment": "Passed"},
        ])

    def test_colspan_summary_preserves_compatibility_snapshot(self):
        html = (FIXTURES / "marks_colspan.html").read_text(encoding="utf-8")

        self.assertEqual(parse_marks_html(html), [
            {"category": "Final", "item": "FE", "weight": "100%", "value": "7.3", "comment": "Passed"},
            {"category": "Final", "item": "Average", "value": "7.3"},
            {"category": "Final", "item": "Status", "value": "Passed"},
        ])

    def test_missing_table_returns_empty_list(self):
        self.assertEqual(parse_marks_html("<p>No marks</p>"), [])

    def test_three_data_columns_preserve_item_weight_and_value(self):
        html = """
        <table>
          <tr><th>Category</th><th>Item</th><th>Weight</th><th>Value</th></tr>
          <tr><td rowspan="2">Quiz</td><td>Q1</td><td>10%</td><td>8</td></tr>
          <tr><td>Q2</td><td>20%</td><td>7</td></tr>
          <tr><td>Final</td><td>FE</td><td>70%</td><td>9</td></tr>
        </table>
        """

        self.assertEqual(parse_marks_html(html), [
            {"category": "Quiz", "item": "Q1", "weight": "10%", "value": "8"},
            {"category": "Quiz", "item": "Q2", "weight": "20%", "value": "7"},
            {"category": "Final", "item": "FE", "weight": "70%", "value": "9"},
        ])

    def test_three_columns_without_category_keep_all_values(self):
        html = """
        <table>
          <tr><th>Item</th><th>Weight</th><th>Value</th></tr>
          <tr><td>Q1</td><td>10%</td><td>8</td></tr>
        </table>
        """

        self.assertEqual(parse_marks_html(html), [
            {"category": "", "item": "Q1", "weight": "10%", "value": "8"},
        ])

    def test_legacy_three_columns_with_category_are_preserved(self):
        html = "<table><tr><td>Final</td><td>FE</td><td>7.3</td></tr></table>"

        self.assertEqual(parse_marks_html(html), [{"category": "Final", "item": "FE", "value": "7.3"}])

    def test_garbage_rowspan_does_not_crash_and_keeps_own_row(self):
        for rowspan in ("2.0", "abc", ""):
            with self.subTest(rowspan=rowspan):
                html = ("<table><tr><th>Item</th><th>Weight</th><th>Value</th></tr>"
                        f"<tr><td rowspan='{rowspan}'>Quiz</td><td>Q1</td><td>10%</td><td>8</td></tr>"
                        "<tr><td>Q2</td><td>20%</td><td>7</td></tr></table>")
                rows = parse_marks_html(html)
                self.assertEqual(rows[0], {"category": "Quiz", "item": "Q1", "weight": "10%", "value": "8"})


class TranscriptHtmlTests(unittest.TestCase):
    MAIN_HEADERS = ["No", "Term", "Semester", "Subject Code", "prerequisite",
                    "Replaced Subject", "Subject Name", "Credit", "Grade", "Status"]
    EXTRA_HEADERS = ["No", "Semester", "SubjectCode", "SubjectName", "Credit", "Grade", "Status"]

    @staticmethod
    def fixture():
        main = (
            "<tr>" + "".join(f"<td>{v}</td>" for v in
                ("1", "202", "Fall2026", "PRO192", "", "", "Object Oriented Programming", "3", "8.5", "Passed")) + "</tr>"
            "<tr>" + "".join(f"<td>{v}</td>" for v in
                ("2", "202", "Fall2026", "MAL202", "PRO192", "", "Linear Algebra", "3", "", "Not Passed")) + "</tr>"
        )
        extra = (
            "<tr>" + "".join(f"<td>{v}</td>" for v in
                ("1", "Spring2027", "SSG103", "Soft Skill", "2", "7.0", "Passed")) + "</tr>"
        )
        def header(names):
            return "<tr>" + "".join(f"<th>{n}</th>" for n in names) + "</tr>"
        return (
            "<TABLE class='table table-hover'><tbody>" + header(TranscriptHtmlTests.MAIN_HEADERS) + main + "</tbody></TABLE>"
            "<TABLE class='table table-hover'><tbody>" + header(TranscriptHtmlTests.EXTRA_HEADERS) + extra + "</tbody></TABLE>"
        )

    def setUp(self):
        from myfap.parsers import parse_transcript_html
        self.parse = parse_transcript_html

    def test_each_table_keeps_own_headers_and_keyed_rows(self):
        tables = self.parse(self.fixture())
        self.assertEqual([table["headers"] for table in tables], [self.MAIN_HEADERS, self.EXTRA_HEADERS])
        self.assertEqual(tables[0]["rows"][0], {
            "No": "1", "Term": "202", "Semester": "Fall2026", "Subject Code": "PRO192",
            "prerequisite": "", "Replaced Subject": "", "Subject Name": "Object Oriented Programming",
            "Credit": "3", "Grade": "8.5", "Status": "Passed",
        })
        self.assertEqual(len(tables[0]["rows"]), 2)
        self.assertEqual(tables[1]["rows"][0]["SubjectName"], "Soft Skill")
        self.assertEqual(len(tables[1]["rows"]), 1)

    def test_html_entities_are_decoded_and_extra_cells_get_stable_keys(self):
        tables = self.parse("<table><tr><th>A</th><th>B</th></tr>"
                            "<tr><td>Số&nbsp;1</td><td>x</td><td>thừa</td></tr></table>")
        self.assertEqual(tables[0]["rows"][0], {"A": "Số 1", "B": "x", "Column3": "thừa"})

    def test_input_without_table_returns_empty_list(self):
        self.assertEqual(self.parse("<div>PRIVATE [not a table]</div>"), [])
        self.assertEqual(self.parse(""), [])

    def test_data_rows_before_header_are_ignored(self):
        tables = self.parse("<table><tr><td>1</td></tr><tr><th>Only</th></tr><tr><td>ok</td></tr></table>")
        self.assertEqual(tables[0]["headers"], ["Only"])
        self.assertEqual(tables[0]["rows"], [{"Only": "ok"}])


class ScheduleParserTests(unittest.TestCase):
    def test_saved_ics_keeps_line_endings_for_independent_reader(self):
        data = json.loads((FIXTURES / "schedule_valid.json").read_text(encoding="utf-8"))
        data["data"][0]["roomNo"] = "Phòng thử nghiệm"

        with TemporaryDirectory() as temporary, redirect_stderr(io.StringIO()):
            save_output(convert_schedule_to_ics(data), "schedule.ics", temporary, False, is_text=True)
            content = (Path(temporary) / "schedule.ics").read_bytes()

        self.assertNotIn(b"\r\r\n", content)
        self.assertIn("Phòng thử nghiệm".encode("utf-8"), content)
        self.assertEqual(len(IndependentCalendar.from_ical(content).walk("VEVENT")), 1)

    def test_stdout_ics_keeps_line_endings_for_independent_reader(self):
        data = json.loads((FIXTURES / "schedule_valid.json").read_text(encoding="utf-8"))
        expected = convert_schedule_to_ics(data)
        for newline in ("\n", "\r\n"):
            with self.subTest(newline=newline):
                buffer = io.BytesIO()
                with io.TextIOWrapper(buffer, encoding="utf-8", newline=newline) as output:
                    with redirect_stdout(output):
                        save_output(expected, "schedule.ics", None, True, is_text=True)
                    output.flush()
                    content = buffer.getvalue()
                self.assertEqual(content, expected.encode("utf-8"))
                self.assertNotIn(b"\r\r\n", content)
                self.assertEqual(len(IndependentCalendar.from_ical(content).walk("VEVENT")), 1)

    def test_stdout_ics_keeps_crlf_in_text_only_stream(self):
        data = json.loads((FIXTURES / "schedule_valid.json").read_text(encoding="utf-8"))
        expected = convert_schedule_to_ics(data)
        output = io.StringIO()
        with redirect_stdout(output):
            save_output(expected, "schedule.ics", None, True, is_text=True)
        self.assertEqual(output.getvalue(), expected)

    def test_large_synthetic_calendar_imports_with_independent_reader(self):
        base = json.loads((FIXTURES / "schedule_valid.json").read_text(encoding="utf-8"))["data"][0]
        rows = []
        for index in range(250):
            day = datetime(2026, 1, 1) + timedelta(days=index)
            rows.append({**base, "date": day.strftime("%m/%d/%Y") + " 12:00:00 AM", "subjectCode": f"TEST{index}", "isOnline": "False"})

        calendar = IndependentCalendar.from_ical(convert_schedule_to_ics({"data": rows}))
        events = calendar.walk("VEVENT")

        self.assertEqual(len(events), 250)
        self.assertEqual(len({str(event["UID"]) for event in events}), 250)
        for event in events:
            properties = [name for name, _ in event.property_items()]
            self.assertEqual(properties.count("UID"), 1)
            self.assertEqual(properties.count("DTSTAMP"), 1)
            dtstamp = event.decoded("DTSTAMP")
            self.assertIsInstance(dtstamp, datetime)
            self.assertEqual(dtstamp.utcoffset(), timedelta(0))
            self.assertRegex(event["DTSTAMP"].to_ical().decode("ascii"), r"^\d{8}T\d{6}Z$")
            index = int(str(event["SUMMARY"])[4:])
            day = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=index)
            self.assertEqual(event.decoded("DTSTART"), day.replace(hour=0, minute=30))
            self.assertEqual(event.decoded("DTEND"), day.replace(hour=2, minute=50))
            self.assertFalse(event.errors)

    def test_ics_preserves_vietnam_time_and_session_details(self):
        data = json.loads((FIXTURES / "schedule_valid.json").read_text(encoding="utf-8"))

        calendar = Calendar(convert_schedule_to_ics(data))

        self.assertEqual(len(calendar.events), 1)
        event = next(iter(calendar.events))
        self.assertEqual(event.name, "TEST101 (Online)")
        self.assertEqual(event.begin.datetime, datetime(2026, 10, 15, 0, 30, tzinfo=timezone.utc))
        self.assertEqual(event.end.datetime, datetime(2026, 10, 15, 2, 50, tzinfo=timezone.utc))
        self.assertEqual(event.location, "Demo room")
        self.assertEqual(event.description, "\n".join([
            "Group: Demo group", "Session: 1", "Lecturer: Demo lecturer",
            "Room: Demo room", "Meet URL: https://example.invalid/meet",
        ]))

    def test_boolean_is_online_still_marks_online_title(self):
        data = json.loads((FIXTURES / "schedule_valid.json").read_text(encoding="utf-8"))
        data["data"][0]["isOnline"] = True

        event = next(iter(Calendar(convert_schedule_to_ics(data)).events))

        self.assertEqual(event.name, "TEST101 (Online)")

    def test_overnight_slot_wraps_end_to_next_day(self):
        data = json.loads((FIXTURES / "schedule_valid.json").read_text(encoding="utf-8"))
        data["data"][0]["slotTime"] = "(23:30-0:50)"

        event = next(iter(Calendar(convert_schedule_to_ics(data)).events))

        # 23:30 và 0:50 (hôm sau) giờ Việt Nam = 16:30 và 17:50 UTC cùng ngày 15/10.
        self.assertEqual(event.begin.datetime, datetime(2026, 10, 15, 16, 30, tzinfo=timezone.utc))
        self.assertEqual(event.end.datetime, datetime(2026, 10, 15, 17, 50, tzinfo=timezone.utc))
        self.assertEqual((event.end.datetime - event.begin.datetime).total_seconds(), 80 * 60)

    def test_slot_without_separator_raises_clear_message(self):
        data = json.loads((FIXTURES / "schedule_valid.json").read_text(encoding="utf-8"))
        data["data"][0]["slotTime"] = "7:30"

        with self.assertRaises(ValueError) as caught:
            convert_schedule_to_ics(data)
        self.assertIn("slotTime", str(caught.exception))
        self.assertIn("7:30-9:50", str(caught.exception))


class ExamsParserTests(unittest.TestCase):
    @staticmethod
    def fixture_data(**overrides):
        row = {
            "subjectCode": "TEST101", "realSubject": "TEST101", "subjectName": "Môn thử nghiệm",
            "date": "2026-10-20T00:00:00", "slot": "Synthetic slot text (7h30-9h50)", "time": "7h30-9h50",
            "note": "", "roomNo": "SY-101", "dateofPublication": "2026-10-01T00:00:00",
            "kythi": "FE", "note_Attendance": "", "isGraduated": False,
        }
        row.update(overrides)
        return {"code": "200", "data": [row]}

    def setUp(self):
        from myfap.parsers import convert_exams_to_ics
        self.convert = convert_exams_to_ics

    def test_valid_exams_build_calendar_with_uid_dtstamp_and_vietnam_time(self):
        content = self.convert(self.fixture_data()).encode("utf-8")
        calendar = IndependentCalendar.from_ical(content)
        events = calendar.walk("VEVENT")
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(str(event["SUMMARY"]), "TEST101 (FE)")
        self.assertEqual(event.decoded("DTSTART"), datetime(2026, 10, 20, 0, 30, tzinfo=timezone.utc))
        self.assertEqual(event.decoded("DTEND"), datetime(2026, 10, 20, 2, 50, tzinfo=timezone.utc))
        properties = [name for name, _ in event.property_items()]
        self.assertEqual(properties.count("UID"), 1)
        self.assertEqual(properties.count("DTSTAMP"), 1)
        self.assertRegex(event["DTSTAMP"].to_ical().decode("ascii"), r"^\d{8}T\d{6}Z$")
        self.assertIn("Môn thử nghiệm".encode("utf-8"), content)
        self.assertIn(b"\r\n", content)
        self.assertNotIn(b"\r\r\n", content)

    def test_default_ics_includes_room_and_publication_and_hides_slot_uuid(self):
        content = self.convert(self.fixture_data(slot="42409f01-4993-4a0b-9302-2ccf5", roomNo="BE-201")).encode("utf-8")
        event = IndependentCalendar.from_ical(content).walk("VEVENT")[0]
        desc = str(event.get("DESCRIPTION"))
        self.assertIn("Môn: Môn thử nghiệm", desc)
        self.assertIn("Phòng: BE-201", desc)
        self.assertIn("Ngày công bố: 2026-10-01", desc)
        self.assertNotIn("42409f01", desc)
        self.assertNotIn("Mã slot", desc)
        self.assertEqual(str(event.get("LOCATION")), "BE-201")

    def test_full_ics_includes_all_secondary_fields(self):
        content = self.convert(self.fixture_data(
            slot="42409f01-4993-4a0b-9302-2ccf5", roomNo="BE-201",
            note="Mang thẻ SV", note_Attendance="Có mặt", isGraduated=True
        ), full=True).encode("utf-8")
        event = IndependentCalendar.from_ical(content).walk("VEVENT")[0]
        desc = str(event.get("DESCRIPTION"))
        self.assertIn("Môn: Môn thử nghiệm", desc)
        self.assertIn("Ngày công bố: 2026-10-01", desc)
        self.assertIn("Phòng: BE-201", desc)
        self.assertIn("Mã slot: 42409f01-4993-4a0b-9302-2ccf5", desc)
        self.assertIn("Ghi chú: Mang thẻ SV", desc)
        self.assertIn("Ghi chú điểm danh: Có mặt", desc)
        self.assertIn("Đã tốt nghiệp: Có", desc)
        self.assertEqual(str(event.get("LOCATION")), "BE-201")

    def test_time_with_spaces_and_parentheses_is_accepted(self):
        for time in ("7h30 - 9h50", "(7h30-9h50)", " ( 7h30-9h50 ) "):
            with self.subTest(time=time):
                content = self.convert(self.fixture_data(time=time))
                event = IndependentCalendar.from_ical(content).walk("VEVENT")[0]
                self.assertEqual(event.decoded("DTSTART"), datetime(2026, 10, 20, 0, 30, tzinfo=timezone.utc))

    def test_overnight_exam_wraps_end_to_next_day(self):
        content = self.convert(self.fixture_data(time="23h30-0h50"))
        event = IndependentCalendar.from_ical(content).walk("VEVENT")[0]
        self.assertEqual((event.decoded("DTEND") - event.decoded("DTSTART")).total_seconds(), 80 * 60)

    def test_invalid_root_or_rows_are_rejected_with_clear_errors(self):
        cases = (
            (None, "Invalid JSON format"),
            ({}, "Invalid JSON format"),
            ({"data": None}, "Invalid JSON format"),
            ({"data": [None]}, "date, time"),
            ({"data": [{}]}, "date, time"),
            (self.fixture_data(subjectCode=" "), "date, time"),
            (self.fixture_data(date="20/10/2026T00:00:00"), "date"),
            (self.fixture_data(time="7:30-9:50"), "time"),
            (self.fixture_data(time="7h30"), "time"),
            (self.fixture_data(time="7h99-9h50"), "time"),
        )
        for data, message in cases:
            with self.subTest(data=data, message=message):
                with self.assertRaises(ValueError) as caught:
                    self.convert(data)
                self.assertIn(message, str(caught.exception))


class SaveOutputSanitizationTests(unittest.TestCase):
    def test_server_influenced_filename_stays_inside_output_dir(self):
        with TemporaryDirectory() as temporary, redirect_stderr(io.StringIO()):
            save_output({"code": 200, "data": []}, "BangDiem_x/../../evil.json", temporary, False)
            files = sorted(path.name for path in Path(temporary).iterdir())
            self.assertEqual(files, ["BangDiem_x_.._.._evil.json"])
            content = json.loads((Path(temporary) / files[0]).read_text(encoding="utf-8"))
        self.assertEqual(content, {"code": 200, "data": []})

    def test_empty_schedule_returns_valid_empty_calendar(self):
        data = json.loads((FIXTURES / "schedule_empty.json").read_text(encoding="utf-8"))

        self.assertEqual(len(Calendar(convert_schedule_to_ics(data)).events), 0)

    def test_non_list_schedule_is_rejected(self):
        data = json.loads((FIXTURES / "schedule_malformed.json").read_text(encoding="utf-8"))

        with self.assertRaises(ValueError):
            convert_schedule_to_ics(data)

    def test_invalid_root_or_missing_session_fields_are_rejected(self):
        for data in [None, [], {}, {"data": None}, {"data": [None]}, {"data": [{}]}]:
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    convert_schedule_to_ics(data)

    def test_required_session_fields_reject_non_string_and_blank_values(self):
        for field in ("date", "slotTime", "subjectCode"):
            for value in (None, 123, " "):
                with self.subTest(field=field, value=value):
                    data = json.loads((FIXTURES / "schedule_valid.json").read_text(encoding="utf-8"))
                    data["data"][0][field] = value

                    with self.assertRaises(ValueError):
                        convert_schedule_to_ics(data)

    def test_invalid_session_date_or_slot_is_rejected(self):
        for field, value in [("date", "02/30/2026"), ("slotTime", "invalid")]:
            with self.subTest(field=field):
                data = json.loads((FIXTURES / "schedule_valid.json").read_text(encoding="utf-8"))
                data["data"][0][field] = value

                with self.assertRaises(ValueError):
                    convert_schedule_to_ics(data)

    def test_slot_time_allows_spaces_around_separator_and_parentheses(self):
        data = json.loads((FIXTURES / "schedule_valid.json").read_text(encoding="utf-8"))
        for slot in ("(7:30 - 9:50)", "( 7:30-9:50 )", "( 7:30 - 9:50 )", "  (7:30 - 9:50)  ", " 7:30 - 9:50 "):
            with self.subTest(slot=slot):
                data["data"][0]["slotTime"] = slot
                event = next(iter(Calendar(convert_schedule_to_ics(data)).events))
                self.assertEqual(event.begin.datetime, datetime(2026, 10, 15, 0, 30, tzinfo=timezone.utc))
                self.assertEqual(event.end.datetime, datetime(2026, 10, 15, 2, 50, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()
