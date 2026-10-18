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


class ScheduleParserTests(unittest.TestCase):
    def test_saved_ics_keeps_line_endings_for_independent_reader(self):
        data = json.loads((FIXTURES / "schedule_valid.json").read_text(encoding="utf-8"))

        with TemporaryDirectory() as temporary, redirect_stderr(io.StringIO()):
            save_output(convert_schedule_to_ics(data), "schedule.ics", temporary, False, is_text=True)
            content = (Path(temporary) / "schedule.ics").read_bytes()

        self.assertNotIn(b"\r\r\n", content)
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
